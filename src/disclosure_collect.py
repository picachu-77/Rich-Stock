# -*- coding: utf-8 -*-
"""
DART 공시 목록을 모아 창고(disclosure 표)에 쌓는 수집기.

실행 방법
    python -m src.disclosure_collect              # 최근 7일치
    python -m src.disclosure_collect --days 90    # 최근 90일치 (처음 채울 때)
    python -m src.disclosure_collect --days 365   # 최근 1년치

왜 이렇게 받나요? (종목별로 안 받고 날짜별로 받는 이유)
  DART 는 '이 회사 공시 주세요' 도 되고 '이 기간 공시 전부 주세요' 도 됩니다.
  종목마다 따로 부르면 2,800번을 불러야 하지만, 날짜로 부르면 하루치가
  보통 1,000건 안팎이라 100건씩 10번이면 끝납니다.
  DART 하루 한도(20,000건)를 아끼려면 날짜로 받는 쪽이 훨씬 낫습니다.

  받아온 공시 중에서 우리 창고에 있는 종목의 것만 골라 저장합니다.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from .dart import DartClient, DartLimitReached
from .db import bulk_upsert, get_conn
from .disclosure import classify

PAGE_COUNT = 100          # 한 번에 받는 건수 (DART 최대)
MAX_PAGE = 100            # 하루에 이보다 많으면 그만 (무한 반복 방지)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DART 공시 목록 수집")
    p.add_argument("--days", type=int, default=7,
                   help="오늘로부터 며칠 전까지 받을지 (기본 7일)")
    return p.parse_args()


def load_corp_map(conn) -> dict[str, str]:
    """
    DART 고유번호 → 종목코드 대응표를 만듭니다.

    이 표에 없는 회사의 공시는 저장하지 않습니다.
    (비상장사 공시까지 다 담으면 창고만 커지고 쓸 일이 없습니다)
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT dart_corp_code, code FROM ticker "
            " WHERE dart_corp_code IS NOT NULL AND is_active = TRUE;"
        )
        return {corp: code for corp, code in cur.fetchall()}


UPSERT_SQL = """
INSERT INTO disclosure
    (rcept_no, code, corp_code, rcept_dt, report_nm, category, remark)
VALUES %s
ON CONFLICT (rcept_no) DO UPDATE SET
    report_nm = EXCLUDED.report_nm,
    category  = EXCLUDED.category,
    remark    = EXCLUDED.remark;
"""


def fetch_range(dart: DartClient, corp_map: dict[str, str],
                bgn: date, end: date) -> list[tuple]:
    """
    한 기간의 공시를 모두 받아옵니다. (100건씩 넘겨가며)

    DART 는 결과가 많으면 여러 쪽으로 나눠 줍니다. total_page 를 보고
    마지막 쪽까지 돌되, 혹시 몰라 MAX_PAGE 에서 멈춥니다.
    """
    rows: list[tuple] = []
    page = 1
    total_page = 1

    while page <= min(total_page, MAX_PAGE):
        data = dart.get(
            "list",
            bgn_de=bgn.strftime("%Y%m%d"),
            end_de=end.strftime("%Y%m%d"),
            corp_cls="Y",            # Y = 유가증권(코스피). 아래에서 K 도 받습니다.
            page_no=page,
            page_count=PAGE_COUNT,
        )
        rows += _pick_rows(data, corp_map)
        total_page = int(data.get("total_page") or 1)
        page += 1

    # 코스닥(K) 도 같은 방식으로 받습니다.
    page, total_page = 1, 1
    while page <= min(total_page, MAX_PAGE):
        data = dart.get(
            "list",
            bgn_de=bgn.strftime("%Y%m%d"),
            end_de=end.strftime("%Y%m%d"),
            corp_cls="K",
            page_no=page,
            page_count=PAGE_COUNT,
        )
        rows += _pick_rows(data, corp_map)
        total_page = int(data.get("total_page") or 1)
        page += 1

    return rows


def _pick_rows(data: dict, corp_map: dict[str, str]) -> list[tuple]:
    """받아온 응답에서 우리 종목의 공시만 골라 저장할 모양으로 바꿉니다."""
    if str(data.get("status")) == "013":       # 해당 기간 자료 없음 (정상)
        return []

    out = []
    for item in data.get("list", []) or []:
        corp = item.get("corp_code")
        code = corp_map.get(corp)
        if not code:
            continue                            # 우리가 안 보는 회사

        rcept_no = item.get("rcept_no")
        rcept_dt = item.get("rcept_dt")         # YYYYMMDD
        report_nm = (item.get("report_nm") or "").strip()
        if not (rcept_no and rcept_dt and report_nm):
            continue

        out.append((
            rcept_no,
            code,
            corp,
            f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}",
            report_nm,
            classify(report_nm),                # 저장할 때 미리 나눠 둡니다
            (item.get("rm") or "").strip() or None,
        ))
    return out


def main() -> None:
    args = parse_args()
    end = date.today()
    bgn = end - timedelta(days=max(args.days, 1))

    print("=" * 60)
    print(f" DART 공시 수집  ({bgn} ~ {end})")
    print("=" * 60)

    dart = DartClient()

    with get_conn() as conn:
        corp_map = load_corp_map(conn)
        if not corp_map:
            print("\n[!] ticker 표에 dart_corp_code 가 비어 있습니다.")
            print("    먼저 아래를 실행해 주세요.")
            print("      python -m src.dart_corpcode")
            return
        print(f"  대상 종목 {len(corp_map):,}개")

        # 기간이 길면 한 달씩 끊어서 받습니다.
        # 한 번에 넓게 잡으면 쪽 수가 너무 많아져 중간에 끊겼을 때 손해가 큽니다.
        total = 0
        cursor = bgn
        try:
            while cursor <= end:
                chunk_end = min(cursor + timedelta(days=30), end)
                rows = fetch_range(dart, corp_map, cursor, chunk_end)
                if rows:
                    saved = bulk_upsert(conn, UPSERT_SQL, rows)
                    total += saved
                    print(f"  {cursor} ~ {chunk_end}  {saved:,}건 저장")
                else:
                    print(f"  {cursor} ~ {chunk_end}  없음")
                cursor = chunk_end + timedelta(days=1)
        except DartLimitReached as exc:
            print(f"\n[!] {exc}")

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM disclosure;")
            kept = cur.fetchone()[0]

    print()
    print(f"완료! 이번에 {total:,}건 저장 · 창고에 모두 {kept:,}건 "
          f"(DART 호출 {dart.calls:,}건)")


if __name__ == "__main__":
    main()
