"""
창고 자리 만들기 — 오래된 시세를 성기게, 안 쓰는 공시를 정리.

실행 방법
    python -m src.trim                 # 숫자만 보여줍니다 (아무것도 안 지움)
    python -m src.trim --apply         # 실제로 정리합니다
    python -m src.trim --apply --with-정기보고   # 정기보고서까지 함께 정리

★ 왜 '지우기' 가 아니라 '성기게' 인가 ★
  3년치를 2년치로 줄이면 3년 수익률과 3년 그래프가 사라집니다. 그런데
  초보자가 3년 그래프에서 보는 것은 '그때 얼마였나' 가 아니라 '어떤
  모양이었나' 입니다. 2023년 9월 14일 종가가 정확히 얼마였는지는
  아무도 안 봅니다.

  그래서 기간은 그대로 두고 촘촘함만 줄입니다.
      최근 180일 : 매일 (그대로)
      그 이전    : 주 1회 (그 주의 마지막 거래일만)
  3년 그래프도, 3년 수익률도 그대로 나옵니다.

★ 수익률이 틀어지지 않는 이유 ★
  기간 수익률은 '몇 개월 전 종가' 를 찾는데, 자료가 그보다 멀면
  빈칸으로 둡니다(NEAR_DAYS = 14일). 주 1회면 사이가 최대 7일이라
  14일 안에 늘 걸립니다. 1개월·3개월은 애초에 매일 남는 구간입니다.

★ 오래된 줄의 등락률 ★
  그대로 둡니다. '그 전 거래일 대비' 값이라 주 1회로 성겨지면 뜻이
  달라지지만, 화면 어디에서도 과거 등락률은 쓰지 않습니다
  (목록·상세 모두 가장 최근 하루치만 씁니다). 고치려고 57만 줄을
  건드리면 오히려 자리를 더 먹습니다.

★ 파일 크기는 바로 줄지 않습니다 ★
  PostgreSQL 은 지운 줄을 파일에서 잘라내지 않고 '다시 써도 되는 자리'
  로 표시합니다. 그래서 Supabase 화면의 '쓰는 중' 숫자는 그대로입니다.
  대신 새로 쌓이는 시세가 그 자리를 먼저 쓰기 때문에, 파일이 다시
  커지기 시작할 때까지 아주 오래 걸립니다. 그게 우리가 원하는 것입니다.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from .db import get_conn, fetch_all, run_sql

# 최근 며칠까지 매일 그대로 둘지
KEEP_DAILY_DAYS = 180

# 한 번에 다루는 종목 수. 한꺼번에 하면 2분 제한에 걸립니다.
CHUNK = 200

STATEMENT_TIMEOUT = "10min"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="창고 자리 만들기")
    p.add_argument("--apply", action="store_true",
                   help="실제로 정리합니다 (없으면 숫자만 보여줍니다)")
    p.add_argument("--days", type=int, default=KEEP_DAILY_DAYS,
                   help=f"최근 며칠을 매일 그대로 둘지 (기본 {KEEP_DAILY_DAYS})")
    p.add_argument("--with-regular", action="store_true",
                   help="정기보고서 공시도 함께 정리합니다")
    return p.parse_args()


def _relax_timeout(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}';")
    conn.commit()


def _mb(v: float) -> str:
    return f"{v:,.0f}MB"


def _price_stats(conn) -> tuple[int, float]:
    """(줄 수, 한 줄당 MB) — 색인까지 포함한 무게입니다."""
    (rows,) = fetch_all(conn, "SELECT count(*) FROM daily_price;")[0]
    (total,) = fetch_all(conn, "SELECT pg_total_relation_size('daily_price');")[0]
    return rows, (total / 1024 / 1024) / rows if rows else 0.0


def survey(conn, cutoff: date) -> dict:
    """무엇이 얼마나 사라지는지 먼저 셉니다. 아무것도 고치지 않습니다."""
    (keep_daily,) = fetch_all(
        conn, "SELECT count(*) FROM daily_price WHERE trade_date >= %s;", (cutoff,)
    )[0]
    (old_all,) = fetch_all(
        conn, "SELECT count(*) FROM daily_price WHERE trade_date < %s;", (cutoff,)
    )[0]
    # 주마다 마지막 거래일 하나씩만 남깁니다.
    (old_keep,) = fetch_all(
        conn,
        """
        SELECT count(*) FROM (
          SELECT code, date_trunc('week', trade_date) AS wk
            FROM daily_price WHERE trade_date < %s
           GROUP BY 1, 2
        ) t;
        """,
        (cutoff,),
    )[0]
    return {
        "keep_daily": keep_daily,
        "old_all": old_all,
        "old_keep": old_keep,
        "doomed": old_all - old_keep,
    }


def _codes_with_old(conn, cutoff: date) -> list[str]:
    return [
        r[0]
        for r in fetch_all(
            conn,
            "SELECT DISTINCT code FROM daily_price WHERE trade_date < %s ORDER BY code;",
            (cutoff,),
        )
    ]


THIN_SQL = """
WITH doomed AS (
  SELECT code, trade_date FROM (
    SELECT code, trade_date,
           row_number() OVER (
             PARTITION BY code, date_trunc('week', trade_date)
             ORDER BY trade_date DESC
           ) AS rn
      FROM daily_price
     WHERE code = ANY(%s) AND trade_date < %s
  ) t WHERE rn > 1
)
DELETE FROM daily_price d
 USING doomed x
 WHERE d.code = x.code AND d.trade_date = x.trade_date;
"""


def thin_prices(conn, cutoff: date, progress=None) -> int:
    """오래된 시세를 주 1회로 성기게 만듭니다."""
    _relax_timeout(conn)
    codes = _codes_with_old(conn, cutoff)
    removed = 0
    for i in range(0, len(codes), CHUNK):
        batch = codes[i : i + CHUNK]
        with conn.cursor() as cur:
            cur.execute(THIN_SQL, (batch, cutoff))
            removed += cur.rowcount
        conn.commit()
        if progress:
            progress(min(i + CHUNK, len(codes)), len(codes), removed)
    return removed


def drop_regular_reports(conn) -> int:
    """정기보고서 공시를 지웁니다."""
    _relax_timeout(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM disclosure WHERE category = '정기보고';")
        n = cur.rowcount
    conn.commit()
    return n


def vacuum(conn, table: str) -> None:
    old = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"VACUUM (ANALYZE) {table};")
    finally:
        conn.autocommit = old


def main() -> None:
    args = parse_args()
    cutoff = date.today() - timedelta(days=args.days)

    print("=" * 62)
    print(" 창고 자리 만들기" + ("" if args.apply else "   [살펴보기만 — 아무것도 안 지웁니다]"))
    print("=" * 62)

    with get_conn() as conn:
        rows, mb_per_row = _price_stats(conn)
        s = survey(conn, cutoff)

        print(f"  기준일 : {cutoff} (최근 {args.days:,}일은 매일 그대로)")
        print()
        print("  시세")
        print(f"    지금             {rows:,}줄")
        print(f"      최근 {args.days}일     {s['keep_daily']:,}줄  (그대로)")
        print(f"      그 이전         {s['old_all']:,}줄")
        print(f"        남길 것       {s['old_keep']:,}줄  (주 1회)")
        print(f"        지울 것       {s['doomed']:,}줄")
        print()
        print(f"    정리 후          {rows - s['doomed']:,}줄 "
              f"({(rows - s['doomed']) / rows * 100:.0f}%)")
        print(f"    비는 자리        약 {_mb(s['doomed'] * mb_per_row)}")

        reg = fetch_all(
            conn, "SELECT count(*) FROM disclosure WHERE category = '정기보고';"
        )[0][0]
        (d_rows,) = fetch_all(conn, "SELECT count(*) FROM disclosure;")[0]
        (d_total,) = fetch_all(conn, "SELECT pg_total_relation_size('disclosure');")[0]
        d_mb = (d_total / 1024 / 1024) / d_rows if d_rows else 0
        print()
        print("  공시 (정기보고서)")
        print(f"    지울 수 있는 것  {reg:,}건  ≈ {_mb(reg * d_mb)}")
        print("    ※ 종목 화면에는 사업·분기보고서 링크로 보입니다.")
        print("       지우면 그 줄이 사라집니다. --with-regular 를 붙여야 지웁니다.")

        if not args.apply:
            print()
            print("  아무것도 건드리지 않았습니다.")
            print("  실제로 정리하려면 --apply 를 붙여 주세요.")
            print("=" * 62)
            return

        print()
        print("  정리를 시작합니다...")

        def show(done: int, total: int, removed: int) -> None:
            print(f"    · 종목 {done:,}/{total:,} · 지운 줄 {removed:,}")

        removed = thin_prices(conn, cutoff, progress=show)
        print(f"  시세 {removed:,}줄을 정리했습니다.")

        if args.with_regular:
            n = drop_regular_reports(conn)
            print(f"  정기보고서 공시 {n:,}건을 정리했습니다.")

        print("  자리 정리(VACUUM) 중...")
        vacuum(conn, "daily_price")
        if args.with_regular:
            vacuum(conn, "disclosure")

        after, _ = _price_stats(conn)
        print()
        print(f"  시세 줄 수 : {rows:,} → {after:,}")
        print("  ※ Supabase 화면의 '쓰는 중' 숫자는 바로 줄지 않습니다.")
        print("    지운 자리는 파일 안에서 '다시 써도 되는 자리' 가 되고,")
        print("    새로 쌓이는 시세가 그 자리를 먼저 씁니다.")
    print("=" * 62)


if __name__ == "__main__":
    main()
