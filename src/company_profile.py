# -*- coding: utf-8 -*-
"""
회사 기본정보(업종·대표이사·설립일·홈페이지)를 DART 에서 받아 저장하는 스크립트.

실행 방법:
    .venv\\Scripts\\python.exe -m src.company_profile              # 아직 없는 종목만
    .venv\\Scripts\\python.exe -m src.company_profile --all        # 전부 다시 받기
    .venv\\Scripts\\python.exe -m src.company_profile --limit 100  # 100곳만 (시험용)

왜 필요한가요?
    '우량주 찾기' 화면에서 같은 업종끼리 비교하려면 회사가 어느 업종인지
    알아야 합니다. DART 기업개황(company) 에 업종코드와 대표이사가 들어 있습니다.

호출량
    회사 1곳당 1건이라 상장사 전체는 약 2,600건입니다.
    DART 하루 한도는 20,000건이므로 여유롭습니다.
    한 번 받아두면 자주 바뀌지 않으니 분기에 한 번만 갱신하면 충분합니다.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from .dart import DartClient
from .db import bulk_upsert, fetch_all, get_conn
from .ksic import sector_name

STATUS_OK = "000"


def parse_est_date(text: str | None):
    """DART 가 주는 설립일 '19690113' 을 날짜로 바꿉니다. 이상하면 None."""
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())
    if len(digits) != 8:
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d").date()
    except ValueError:
        return None


def clean_url(text: str | None) -> str | None:
    """홈페이지 주소를 정리합니다. 빈 값이면 None."""
    url = (text or "").strip()
    if not url or url in {"-", "없음"}:
        return None
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url[:300]


def fetch_profile(dart: DartClient, corp_code: str) -> dict | None:
    """
    DART 기업개황을 한 곳 받아옵니다.

    돌려주는 값: 업종코드 / 업종명 / 대표이사 / 설립일 / 홈페이지
    실패하면 None 을 돌려주고, 부르는 쪽에서 건너뜁니다.
    """
    try:
        data = dart.get("company", corp_code=corp_code)
    except Exception:  # noqa: BLE001
        # 한 회사가 실패해도 전체 수집은 계속되어야 합니다.
        return None

    if str(data.get("status")) != STATUS_OK:
        return None

    induty = (data.get("induty_code") or "").strip()
    return {
        "sector_code": induty or None,
        "sector_name": sector_name(induty),
        "ceo_name": (data.get("ceo_nm") or "").strip()[:100] or None,
        "est_date": parse_est_date(data.get("est_dt")),
        "homepage": clean_url(data.get("hm_url")),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="회사 기본정보(업종·대표이사) 수집")
    ap.add_argument("--all", action="store_true",
                    help="이미 받은 종목도 전부 다시 받습니다")
    ap.add_argument("--limit", type=int, default=0,
                    help="이 개수만 처리합니다 (0 이면 제한 없음)")
    args = ap.parse_args()

    print("=" * 62)
    print(" 회사 기본정보(업종·대표이사·설립일) 수집")
    print("=" * 62)

    dart = DartClient()

    # ★ 데이터베이스 연결은 '쓸 때만 잠깐' 엽니다 ★
    #   DART 에서 2,600곳을 받아오는 데 30분 넘게 걸립니다.
    #   그동안 연결을 열어두면 Neon 이 '노는 연결'로 보고 끊어버려서
    #   막상 저장할 때 실패합니다. 그래서 읽기·저장 때만 잠깐씩 엽니다.
    #   (기존 재무지표 수집기도 같은 방식입니다)
    with get_conn() as conn:
        # 우선주는 보통주와 같은 회사코드를 쓰므로 같은 정보가 채워집니다.
        where = "WHERE is_active = TRUE AND dart_corp_code IS NOT NULL"
        if not args.all:
            where += " AND sector_name IS NULL"

        rows = fetch_all(
            conn,
            f"SELECT code, name, dart_corp_code FROM ticker {where} ORDER BY code;",
        )

    if args.limit > 0:
        rows = rows[: args.limit]

    total = len(rows)
    if total == 0:
        print("\n받아올 종목이 없습니다. (이미 다 받았거나 회사코드가 없습니다)")
        print("회사코드가 없다면 먼저 `python -m src.dart_corpcode` 를 실행하세요.")
        return

    print(f"\n대상 {total:,}곳 — DART 호출 {total:,}건 예정 (하루 한도 20,000건)")

    UPDATE_SQL = """
        UPDATE ticker AS t
           SET sector_code = v.sector_code,
               sector_name = v.sector_name,
               ceo_name    = v.ceo_name,
               est_date    = v.est_date::date,
               homepage    = v.homepage,
               profile_updated_at = now(),
               updated_at  = now()
          FROM (VALUES %s) AS v(code, sector_code, sector_name,
                                ceo_name, est_date, homepage)
         WHERE t.code = v.code;
    """

    def flush(batch: list[tuple]) -> int:
        """모아둔 것을 저장합니다. 저장할 때만 연결을 잠깐 엽니다."""
        if not batch:
            return 0
        with get_conn() as conn:
            return bulk_upsert(conn, UPDATE_SQL, batch)

    # 같은 회사코드를 여러 종목(보통주·우선주)이 함께 쓰므로,
    # 회사코드당 한 번만 받아 API 호출을 아낍니다.
    cache: dict[str, dict | None] = {}
    batch: list[tuple] = []
    saved = 0
    ok = 0
    failed = 0

    for i, (code, name, corp_code) in enumerate(rows, start=1):
        if corp_code not in cache:
            cache[corp_code] = fetch_profile(dart, corp_code)

        info = cache[corp_code]
        if info is None:
            failed += 1
        else:
            ok += 1
            batch.append((
                code, info["sector_code"], info["sector_name"],
                info["ceo_name"], info["est_date"], info["homepage"],
            ))

        # 300곳마다 중간 저장합니다.
        # 중간에 멈추더라도 여기까지는 남으므로, 다시 실행하면 이어서 받습니다.
        if len(batch) >= 300:
            saved += flush(batch)
            batch = []

        if i % 200 == 0 or i == total:
            print(f"  {i:,}/{total:,} 진행 "
                  f"(성공 {ok:,} · 실패 {failed:,} · 저장 {saved:,} · "
                  f"호출 {dart.calls:,}건)", flush=True)

    saved += flush(batch)

    with get_conn() as conn:
        stats = fetch_all(
            conn,
            """
            SELECT sector_name, count(*)
              FROM ticker
             WHERE is_active = TRUE AND sector_name IS NOT NULL
             GROUP BY sector_name
             ORDER BY count(*) DESC
             LIMIT 10;
            """,
        )

    print(f"\n  {saved:,}건 저장 완료 (실패 {failed:,}건)")
    print("\n업종별 종목 수 (상위 10)")
    for sector, cnt in stats:
        print(f"  {sector:<20} {cnt:>5,}개")

    print()
    print("=" * 62)
    print(f" 완료!  DART 호출 {dart.calls:,}건")
    print("=" * 62)


if __name__ == "__main__":
    main()
