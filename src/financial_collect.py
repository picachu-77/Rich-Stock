"""
재무지표 수집기 — DART 전자공시에서 재무제표를 받아 지표를 계산해 저장합니다.

실행 방법
    # 최근 3년치(분기별) 채우기 — 최초 1회
    .venv\\Scripts\\python.exe -m src.financial_collect --years 3

    # 가장 최근 분기만 갱신 — 분기마다 (GitHub Actions 가 자동 실행)
    .venv\\Scripts\\python.exe -m src.financial_collect --latest

★ 시세 수집과 완전히 분리되어 있습니다 ★
  이 스크립트가 실패해도 시세 데이터와 화면은 아무 영향이 없습니다.

═══════════════════════════════════════════════════════════════
 지표 계산식  (모두 DART 재무제표 항목으로 직접 계산합니다)
═══════════════════════════════════════════════════════════════

 ROE (자기자본이익률, %)  =  당기순이익 ÷ 자본총계 × 100
   → 내 돈(자본) 대비 얼마를 벌었는지. 높을수록 돈을 잘 버는 회사.
     예) 자본 100억으로 순이익 15억 → ROE 15%
   ※ 분기 보고서는 그 기간만의 이익이라 연간 기준보다 작게 나옵니다.
     같은 분기끼리(작년 3분기 vs 올해 3분기) 비교하는 게 맞습니다.

 부채비율 (%)  =  부채총계 ÷ 자본총계 × 100
   → 내 돈 대비 빌린 돈이 얼마나 되는지. 낮을수록 안전한 회사.
     100% 면 자기 돈과 빌린 돈이 같다는 뜻.

 영업이익률 (%)  =  영업이익 ÷ 매출액 × 100
   → 물건을 팔아 남긴 비율. 높을수록 장사를 잘하는 회사.
     예) 매출 100억에 영업이익 20억 → 20%

 배당성향 (%)  =  현금배당금총액 ÷ 당기순이익 × 100
   → 번 돈 중 주주에게 나눠준 비율.
     사업보고서(연간)에만 배당 정보가 있으므로 4분기에만 채워집니다.

═══════════════════════════════════════════════════════════════
 DART 호출을 아끼는 방법
═══════════════════════════════════════════════════════════════
  '다중회사 주요계정'(fnlttMultiAcnt) API 는 회사 여러 곳을 한 번에
  조회할 수 있습니다. 한 곳씩 부르면 회사 2,700곳 × 12분기 = 32,400건이라
  하루 한도(20,000건)를 넘지만, 묶음으로 부르면 수백 건으로 끝납니다.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from .config import DART_DAILY_LIMIT
from .dart import (
    REPORT_CODE,
    REPORT_NAME,
    STATUS_OK,
    DartClient,
    DartLimitReached,
    to_amount,
)
from .db import bulk_upsert, fetch_all, get_conn, run_sql

# 한 번에 몇 개 회사를 묶어서 요청할지.
# DART 다중조회는 너무 많이 넣으면 거절하므로 보수적으로 잡습니다.
CHUNK_SIZE = 100

# DART 재무제표에서 우리가 찾을 계정 이름들.
# 회사마다 표기가 조금씩 달라서 후보를 여러 개 둡니다.
ACCOUNT_ALIASES = {
    "revenue": ["매출액", "수익(매출액)", "영업수익", "매출"],
    "operating_profit": ["영업이익", "영업이익(손실)", "영업손익"],
    "net_income": [
        "당기순이익", "당기순이익(손실)", "당기순손익",
        "분기순이익", "반기순이익", "연결당기순이익",
    ],
    "total_assets": ["자산총계"],
    "total_liabilities": ["부채총계"],
    "total_equity": ["자본총계"],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DART 재무지표 수집")
    p.add_argument("--years", type=int, default=3, help="최근 몇 년치를 받을지 (기본 3)")
    p.add_argument(
        "--latest",
        action="store_true",
        help="가장 최근에 나왔을 법한 분기 하나만 갱신 (분기 자동실행용)",
    )
    p.add_argument("--year", type=int, help="특정 연도만")
    p.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], help="특정 분기만")
    p.add_argument(
        "--skip-dividend",
        action="store_true",
        help="배당성향 수집을 건너뜁니다 (호출을 크게 아낍니다)",
    )
    p.add_argument(
        "--redo",
        action="store_true",
        help="이미 받은 분기도 다시 받습니다 (기본은 건너뜁니다)",
    )
    return p.parse_args()


# ── 어느 분기를 받을지 정하기 ─────────────────────────────────
def latest_available_period(today: date | None = None) -> tuple[int, int]:
    """
    '지금 시점에 공시가 나와 있을 법한 가장 최근 분기'를 돌려줍니다.

    공시 마감은 대략 이렇습니다.
      1분기(1~3월)  → 5월 중순
      반기(1~6월)   → 8월 중순
      3분기(1~9월)  → 11월 중순
      사업보고서    → 이듬해 3월 말
    여유를 두고 한 달쯤 뒤를 기준으로 잡습니다.
    """
    today = today or date.today()
    y, m = today.year, today.month

    if m >= 12:
        return y, 3          # 12월 → 올해 3분기
    if m >= 9:
        return y, 2          # 9~11월 → 올해 반기
    if m >= 6:
        return y, 1          # 6~8월 → 올해 1분기
    if m >= 4:
        return y - 1, 4      # 4~5월 → 작년 사업보고서
    return y - 1, 3          # 1~3월 → 작년 3분기


def periods_for_years(years: int, today: date | None = None) -> list[tuple[int, int]]:
    """최근 N년치 (연도, 분기) 목록을 오래된 것부터 돌려줍니다."""
    ly, lq = latest_available_period(today)
    out: list[tuple[int, int]] = []
    y, q = ly, lq
    for _ in range(years * 4):
        out.append((y, q))
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return sorted(out)


# ── DART 응답에서 값 뽑기 ────────────────────────────────────
def _pick(items: list[dict], keys: list[str]) -> int | None:
    """
    계정 목록에서 원하는 항목의 금액을 찾습니다.

    연결재무제표(CFS)를 먼저 쓰고, 없으면 개별재무제표(OFS)를 씁니다.
      연결 = 자회사까지 합친 것 (보통 이쪽을 봅니다)
      개별 = 그 회사만
    """
    for fs_div in ("CFS", "OFS"):
        for item in items:
            if item.get("fs_div") != fs_div:
                continue
            name = (item.get("account_nm") or "").strip()
            if name in keys:
                amount = to_amount(item.get("thstrm_amount"))
                if amount is not None:
                    return amount
    return None


def _ratio(numerator, denominator, scale: float = 100.0):
    """비율을 계산합니다. 나눌 수 없으면 빈칸(None)."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return round(numerator / denominator * scale, 2)


def build_metrics(code: str, year: int, quarter: int, items: list[dict]) -> tuple | None:
    """
    DART 계정 목록 → 지표 한 줄로 바꿉니다.
    필요한 값이 하나도 없으면 None 을 돌려줍니다(저장하지 않음).
    """
    revenue = _pick(items, ACCOUNT_ALIASES["revenue"])
    op_profit = _pick(items, ACCOUNT_ALIASES["operating_profit"])
    net_income = _pick(items, ACCOUNT_ALIASES["net_income"])
    assets = _pick(items, ACCOUNT_ALIASES["total_assets"])
    liabilities = _pick(items, ACCOUNT_ALIASES["total_liabilities"])
    equity = _pick(items, ACCOUNT_ALIASES["total_equity"])

    if all(v is None for v in (revenue, op_profit, net_income, assets, equity)):
        return None

    # 자본총계가 없으면 자산 - 부채로 구합니다.
    if equity is None and assets is not None and liabilities is not None:
        equity = assets - liabilities
    # 부채총계가 없으면 자산 - 자본으로 구합니다.
    if liabilities is None and assets is not None and equity is not None:
        liabilities = assets - equity

    # 자본이 마이너스(자본잠식)면 비율 계산이 의미가 없으므로 비웁니다.
    equity_ok = equity if (equity is not None and equity > 0) else None

    roe = _ratio(net_income, equity_ok)
    debt_ratio = _ratio(liabilities, equity_ok)
    op_margin = _ratio(op_profit, revenue) if (revenue and revenue > 0) else None

    return (
        code, year, quarter,
        roe, debt_ratio, op_margin, None,          # payout_ratio 는 나중에 채움
        revenue, op_profit, net_income,
        equity, liabilities, assets,
        None,                                       # dividend_total
        REPORT_CODE[quarter],
    )


UPSERT_FINANCIAL_SQL = """
INSERT INTO financial (
    code, fiscal_year, fiscal_quarter,
    roe, debt_ratio, op_margin, payout_ratio,
    revenue, operating_profit, net_income,
    total_equity, total_liabilities, total_assets,
    dividend_total, report_code
) VALUES %s
ON CONFLICT (code, fiscal_year, fiscal_quarter) DO UPDATE SET
    roe               = EXCLUDED.roe,
    debt_ratio        = EXCLUDED.debt_ratio,
    op_margin         = EXCLUDED.op_margin,
    revenue           = EXCLUDED.revenue,
    operating_profit  = EXCLUDED.operating_profit,
    net_income        = EXCLUDED.net_income,
    total_equity      = EXCLUDED.total_equity,
    total_liabilities = EXCLUDED.total_liabilities,
    total_assets      = EXCLUDED.total_assets,
    report_code       = EXCLUDED.report_code,
    updated_at        = now();
"""


# ── 한 분기 수집 ─────────────────────────────────────────────
def group_by_corp(companies: list[tuple[str, str]]) -> dict[str, list[str]]:
    """
    DART 회사코드 하나에 매달린 종목코드들을 모읍니다.

    ★ 왜 필요한가 ★
      한 회사에 종목이 여러 개일 수 있습니다.
        현대차(005380) · 현대차우(005385) · 현대차2우B(005387) · 현대차3우B(005389)
      이 넷은 모두 같은 회사(00164742)의 주식이라 재무제표가 하나뿐입니다.
      회사코드 → 종목코드를 1:1 로 다루면 마지막 하나만 남고 나머지가
      사라지므로, 반드시 1:여러 개로 다뤄야 합니다.
      (이 문제로 실제로 삼성전자가 삼성전자우에 덮어써진 적이 있습니다)
    """
    out: dict[str, list[str]] = {}
    for code, corp_code in companies:
        out.setdefault(corp_code, []).append(code)
    return out


def collect_period(dart: DartClient, companies: list[tuple[str, str]],
                   year: int, quarter: int) -> int:
    """
    한 분기의 재무제표를 회사들을 묶어서 받아 저장합니다.
    companies: [(종목코드, DART회사코드), ...]
    """
    saved = 0
    corp_to_codes = group_by_corp(companies)
    corp_list = sorted(corp_to_codes)          # 회사코드 기준(중복 없음)으로 묶습니다
    chunks = [corp_list[i:i + CHUNK_SIZE] for i in range(0, len(corp_list), CHUNK_SIZE)]

    for ci, chunk in enumerate(chunks, start=1):
        data = dart.get(
            "fnlttMultiAcnt",
            corp_code=",".join(chunk),
            bsns_year=str(year),
            reprt_code=REPORT_CODE[quarter],
        )

        if str(data.get("status")) != STATUS_OK:
            # 013(자료 없음)은 흔한 일입니다. 조용히 넘어갑니다.
            print(f"      묶음 {ci}/{len(chunks)}: 자료 없음")
            continue

        # 회사별로 계정을 모읍니다
        grouped: dict[str, list[dict]] = {}
        for item in data.get("list", []):
            grouped.setdefault(item.get("corp_code", ""), []).append(item)

        rows = []
        for corp_code, items in grouped.items():
            # 같은 회사의 보통주·우선주 모두에 같은 재무제표를 넣습니다
            for code in corp_to_codes.get(corp_code, []):
                metrics = build_metrics(code, year, quarter, items)
                if metrics:
                    rows.append(metrics)

        if rows:
            with get_conn() as conn:
                saved += bulk_upsert(conn, UPSERT_FINANCIAL_SQL, rows)

        print(f"      묶음 {ci}/{len(chunks)}: 회사 {len(grouped)}곳 → 종목 {len(rows):,}개 저장 "
              f"(누적 {saved:,}개, API {dart.calls:,}건)")

    return saved


# ── 배당성향 ─────────────────────────────────────────────────
def collect_dividends(dart: DartClient, companies: list[tuple[str, str]],
                      year: int) -> int:
    """
    배당 정보를 받아 배당성향을 계산해 넣습니다.

    배당 정보는 회사를 묶어서 받는 API 가 없어 한 곳씩 불러야 합니다.
    회사 수만큼 호출하므로, 사업보고서(연간)에만 수행합니다.

    배당성향 = 현금배당금총액 ÷ 당기순이익 × 100
    """
    # 같은 회사의 보통주·우선주는 배당 조회를 한 번만 하고,
    # 결과는 그 회사에 딸린 모든 종목에 적용합니다.
    corp_to_codes = group_by_corp(companies)
    targets = sorted(corp_to_codes.items())     # [(회사코드, [종목코드...]), ...]

    updated = 0
    for i, (corp_code, codes) in enumerate(targets, start=1):
        try:
            data = dart.get(
                "alotMatter",
                corp_code=corp_code,
                bsns_year=str(year),
                reprt_code=REPORT_CODE[4],
            )
        except DartLimitReached:
            raise
        except Exception:
            continue

        if str(data.get("status")) != STATUS_OK:
            continue

        # '현금배당금총액' 항목을 찾습니다 (회사마다 표기가 조금씩 다릅니다)
        total = None
        for item in data.get("list", []):
            nm = (item.get("se") or "").replace(" ", "")
            if "현금배당금총액" in nm:
                total = to_amount(item.get("thstrm"))
                if total is not None:
                    break

        if total is None:
            continue

        with get_conn() as conn:
            run_sql(
                conn,
                """
                UPDATE financial
                   SET dividend_total = %s,
                       payout_ratio = CASE
                           WHEN net_income IS NOT NULL AND net_income > 0
                           THEN ROUND(%s::numeric / net_income * 100, 2)
                           ELSE NULL END,
                       updated_at = now()
                 WHERE code = ANY(%s) AND fiscal_year = %s AND fiscal_quarter = 4;
                """,
                (total, total, codes, year),
            )
        updated += len(codes)

        if i % 200 == 0:
            print(f"      배당 {i}/{len(targets)}곳 확인 "
                  f"(적용 {updated}종목, API {dart.calls:,}건)")

    return updated


# ── 본체 ─────────────────────────────────────────────────────
def main() -> None:
    args = parse_args()

    print("=" * 66)
    print(" DART 재무지표 수집")
    print("=" * 66)

    # 1) 회사코드가 연결된 종목 목록 가져오기
    with get_conn() as conn:
        companies = [
            (r[0], r[1])
            for r in fetch_all(
                conn,
                """
                SELECT code, dart_corp_code FROM ticker
                 WHERE is_active = TRUE AND kind = 'STOCK'
                   AND dart_corp_code IS NOT NULL
                 ORDER BY code;
                """,
            )
        ]

    if not companies:
        print("\n[!] DART 회사코드가 연결된 종목이 없습니다.")
        print("    먼저 아래를 실행하세요:")
        print("        .venv\\Scripts\\python.exe -m src.dart_corpcode")
        sys.exit(1)

    print(f"  대상 회사 : {len(companies):,}곳")

    # 2) 받을 분기 정하기
    if args.year and args.quarter:
        periods = [(args.year, args.quarter)]
    elif args.latest:
        periods = [latest_available_period()]
    else:
        periods = periods_for_years(args.years)

    # 이미 받은 분기는 건너뜁니다.
    #
    # ★ 왜 필요한가 ★
    #   3년치는 분기가 12개라 두 시간 안에 못 끝냅니다. 실제로 깃허브
    #   작업이 120분 제한에 걸려 끊겼습니다. 그런데 다시 눌러도 첫 분기부터
    #   다시 시작해서, 영영 3년치를 못 채우는 상태였습니다.
    #
    #   받은 분기를 dart_log 에 적어두는 장치는 원래 있었는데, 적기만 하고
    #   읽지는 않았습니다. 여기서 읽어서 건너뜁니다. 이제 몇 번 나눠 누르면
    #   3년치가 채워집니다.
    if not args.redo:
        with get_conn() as conn:
            done = {
                (r[0], r[1])
                for r in fetch_all(
                    conn,
                    "SELECT fiscal_year, fiscal_quarter FROM dart_log WHERE status = 'done';",
                )
            }
        skipped = [p for p in periods if p in done]
        periods = [p for p in periods if p not in done]
        if skipped:
            print(f"  이미 받은 분기 {len(skipped):,}개는 건너뜁니다.")
            print("  (다시 받으려면 --redo 를 붙이세요)")

    if not periods:
        print("\n  받을 분기가 남지 않았습니다. 이미 전부 받았습니다.")
        print("  다시 받으려면 --redo 를 붙이세요.")
        return

    print(f"  대상 분기 : {len(periods):,}개  "
          f"({periods[0][0]}년 {REPORT_NAME[periods[0][1]]} ~ "
          f"{periods[-1][0]}년 {REPORT_NAME[periods[-1][1]]})")
    print(f"  호출 한도 : {DART_DAILY_LIMIT:,}건에서 자동 중단")
    print()

    dart = DartClient()
    started = time.time()
    total_saved = 0

    try:
        for year, quarter in periods:
            print(f"  ── {year}년 {REPORT_NAME[quarter]} ──")
            saved = collect_period(dart, companies, year, quarter)
            total_saved += saved

            with get_conn() as conn:
                run_sql(
                    conn,
                    """
                    INSERT INTO dart_log
                        (fiscal_year, fiscal_quarter, status, company_count, api_calls)
                    VALUES (%s, %s, 'done', %s, %s)
                    ON CONFLICT (fiscal_year, fiscal_quarter) DO UPDATE SET
                        status = 'done',
                        company_count = EXCLUDED.company_count,
                        api_calls = EXCLUDED.api_calls,
                        updated_at = now();
                    """,
                    (year, quarter, saved, dart.calls),
                )

            # 사업보고서(4분기)에는 배당 정보도 받습니다
            if quarter == 4 and not args.skip_dividend:
                print(f"      배당 정보 수집 중... (회사 {len(companies):,}곳, "
                      f"시간이 걸립니다)")
                n = collect_dividends(dart, companies, year)
                print(f"      배당성향 {n:,}곳 적용")

    except DartLimitReached as exc:
        print(f"\n  [중단] {exc}")
        print("  여기까지 받은 내용은 안전하게 저장되었습니다.")
    except KeyboardInterrupt:
        print("\n\n  [중단됨] 여기까지 받은 내용은 안전하게 저장되었습니다.")

    # 3) 결과 요약
    with get_conn() as conn:
        n_rows, n_codes = fetch_all(
            conn, "SELECT count(*), count(DISTINCT code) FROM financial;"
        )[0]
        have_roe = fetch_all(
            conn, "SELECT count(*) FROM financial WHERE roe IS NOT NULL;"
        )[0][0]

    elapsed = int(time.time() - started)
    print()
    print("=" * 66)
    print(" 완료!")
    print("=" * 66)
    print(f"  소요 시간     : {elapsed // 60}분 {elapsed % 60}초")
    print(f"  DART API 호출 : {dart.calls:,}건 / 하루 한도 20,000건")
    print(f"  저장된 재무   : {n_rows:,}건  (회사 {n_codes:,}곳)")
    print(f"  ROE 계산됨    : {have_roe:,}건")


if __name__ == "__main__":
    main()
