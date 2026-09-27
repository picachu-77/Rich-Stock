# -*- coding: utf-8 -*-
"""
배당 공시를 읽어 '언제까지 사야 받는지' 를 채우는 수집기.

★ 공시 목록을 다시 받지 않습니다 ★
  배당 공시는 이미 disclosure 표에 들어 있습니다 (disclosure_collect 가
  코스피·코스닥 전체 공시를 날짜 범위로 받아둡니다). 여기서는 그중
  제목에 '배당' 이 든 것만 골라 **원문만** 받습니다.

  덕분에 공시 한 건당 DART 호출이 딱 한 번입니다. 회사마다 목록을
  다시 받으면 2,700번이 더 들었을 일입니다.

쓰는 법
    python -m src.dividend_collect                 # 최근 400일치
    python -m src.dividend_collect --days 1200     # 3년치 (처음 한 번)
    python -m src.dividend_collect --dry-run       # 저장하지 않고 보기만
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import requests

from .config import get_dart_api_key
from .dart import BASE_URL, DartClient, DartLimitReached
from .db import fetch_all, get_conn
from .dividend import parse
from .store import save_dividends


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="배당 공시에서 기준일·배당금을 읽습니다")
    p.add_argument("--days", type=int, default=400,
                   help="며칠 전까지의 공시를 볼지 (기본 400)")
    p.add_argument("--dry-run", action="store_true",
                   help="저장하지 않고 무엇이 읽히는지만 봅니다")
    p.add_argument("--limit", type=int, default=0,
                   help="공시 몇 건만 (0 = 전부). 시험할 때 씁니다")
    return p.parse_args()


def 배당공시(conn, since: date, limit: int) -> list[tuple[str, str, date, str]]:
    """
    아직 안 읽은 배당 공시를 고릅니다.

    이미 dividend 표에 있는 접수번호는 건너뜁니다. 공시 원문은 바뀌지
    않으니 한 번 읽으면 다시 받을 이유가 없습니다 — DART 호출을 아낍니다.
    """
    # LIKE 패턴도 파라미터로 넘깁니다. SQL 안에 % 를 직접 적으면
    # 자리표시자(%s)와 섞여서 psycopg2 가 잘못 읽습니다.
    sql = """
        SELECT d.rcept_no, d.code, d.rcept_dt, d.report_nm
          FROM disclosure d
     LEFT JOIN dividend v ON v.rcept_no = d.rcept_no
         WHERE d.rcept_dt >= %s
           AND d.report_nm LIKE %s
           AND v.rcept_no IS NULL
      ORDER BY d.rcept_dt DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return fetch_all(conn, sql, (since, "%배당%"))


def fetch_document(rcept_no: str, key: str) -> bytes | None:
    """공시 원문(ZIP)을 받습니다."""
    try:
        resp = requests.get(
            f"{BASE_URL}/document.xml",
            params={"crtfc_key": key, "rcept_no": rcept_no},
            timeout=60,
        )
    except requests.RequestException as exc:
        print(f"    ! {rcept_no} 를 받지 못했습니다: {exc}")
        return None
    if resp.status_code != 200:
        print(f"    ! {rcept_no} HTTP {resp.status_code}")
        return None
    return resp.content


def main() -> None:
    args = parse_args()
    since = date.today() - timedelta(days=args.days)

    print("=" * 60)
    print(" 배당 공시 읽기")
    print(f" {since} 이후 공시 · {'보기만 함' if args.dry_run else '저장함'}")
    print("=" * 60)

    key = get_dart_api_key()
    dart = DartClient(api_key=key)   # 호출 수를 세고 쉬어가기 위해 씁니다

    with get_conn() as conn:
        todo = 배당공시(conn, since, args.limit)
        print(f"\n아직 안 읽은 배당 공시 {len(todo):,}건")
        if not todo:
            print("새로 읽을 것이 없습니다.")
            return

        rows = []
        읽음 = 버림 = 0
        구분 = {}
        for i, (rcept_no, code, rcept_dt, report_nm) in enumerate(todo, 1):
            if i % 100 == 0 or i == 1:
                print(f"  · {i:,}/{len(todo):,} 번째 ({rcept_dt} {report_nm[:20]})")
            try:
                dart._check_limit()     # 하루 한도를 같이 셉니다
                dart.calls += 1
            except DartLimitReached as exc:
                print(f"\n! {exc}")
                print("  여기까지 읽은 것만 저장하고 멈춥니다.")
                break

            payload = fetch_document(rcept_no, key)
            dart._sleep()
            if payload is None:
                버림 += 1
                continue

            d = parse(rcept_no, payload)
            if d is None:
                # 배당기준일이 없는 공시입니다. '배당' 이 제목에 들어가도
                # 실제 배당 결정이 아닌 것이 섞입니다 (예: 배당정책 안내).
                버림 += 1
                continue

            읽음 += 1
            구분[d.kind or "구분없음"] = 구분.get(d.kind or "구분없음", 0) + 1
            rows.append((d.rcept_no, code, d.kind, d.per_share, d.per_share_pref,
                         d.yield_pct, d.record_date, d.pay_date, d.decided_at))

        print()
        print(f"  읽음 {읽음:,}건 · 못 읽음 {버림:,}건 · DART 호출 {dart.calls:,}번")
        print(f"  배당 구분: {구분}")
        if rows:
            보기 = rows[:5]
            print("\n  ── 읽어낸 것 (앞 5건) ──")
            for r in 보기:
                print(f"    {r[1]} {r[2] or '-':6} 1주당 {r[3] or '-'}원 · "
                      f"기준일 {r[6]} · 지급 {r[7] or '-'}")

        if args.dry_run:
            print("\n(보기만 했습니다. 저장하지 않았습니다)")
            return

        saved = save_dividends(conn, rows)
        conn.commit()
        print(f"\n{saved:,}건 저장했습니다.")


if __name__ == "__main__":
    main()
