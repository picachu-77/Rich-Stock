"""
창고에 뭐가 얼마나 들어 있고, 자리가 얼마나 남았는지 봅니다.

    python -m src.db_status

왜 필요한가:
  Supabase 무료 한도는 500MB 입니다. 시세는 하루 4,000줄씩 계속 쌓이고
  공시도 1년치를 받으면 13만 줄이 넘습니다. 언제 한도에 닿는지 모르면
  어느 날 갑자기 저장이 안 되기 시작합니다.
  깃허브 Actions 에서 '창고 현황 보기' 를 눌러 휴대폰으로도 볼 수 있습니다.
"""

from __future__ import annotations

from .db import fetch_all, get_conn

# Supabase 무료 한도.
FREE_LIMIT_MB = 500

# 하루에 늘어나는 시세 줄 수 (거래일 기준, 최근 실적에서 나온 값).
ROWS_PER_DAY = 4_000


def _mb(v: float) -> str:
    """숫자는 모두 자릿수 구분기호를 넣습니다."""
    return f"{v:,.0f}MB"


def main() -> None:
    with get_conn() as conn:
        (db_bytes,) = fetch_all(
            conn, "SELECT pg_database_size(current_database());"
        )[0]

        # 표 목록과 크기.
        #
        # 줄 수를 pg_class.reltuples(어림값)로 읽지 않습니다. 방금 만든
        # 표는 이 값이 -1 이라 화면에 '-1건' 이 찍힙니다. 여기서는
        # 정확히 셉니다. 손으로 가끔 눌러보는 명령이라 몇십 초는 괜찮고,
        # 용량을 판단하는 자리에 어림값이 섞이면 곤란합니다.
        tables = fetch_all(
            conn,
            """
            SELECT relname,
                   pg_total_relation_size(c.oid) AS total,
                   pg_relation_size(c.oid)       AS heap,
                   pg_indexes_size(c.oid)        AS idx
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
             ORDER BY pg_total_relation_size(c.oid) DESC;
            """,
        )
        counts = {}
        for (name, *_rest) in tables:
            # 표 이름은 우리가 만든 목록에서만 오므로 그대로 넣어도 됩니다.
            (n,) = fetch_all(conn, f'SELECT count(*) FROM "{name}";')[0]
            counts[name] = n

        # 시세 표가 한 줄에 몇 바이트를 차지하는지. 언제 꽉 차는지
        # 셈하는 데 씁니다. (색인까지 포함한 값)
        (price_total_bytes,) = fetch_all(
            conn, "SELECT pg_total_relation_size('daily_price');"
        )[0]

        (price_rows, days, first_d, last_d) = fetch_all(
            conn,
            """
            SELECT count(*), count(DISTINCT trade_date), min(trade_date), max(trade_date)
              FROM daily_price;
            """,
        )[0]

        (blank,) = fetch_all(
            conn, "SELECT count(*) FROM daily_price WHERE change_pct IS NULL;"
        )[0]

    used_mb = db_bytes / 1024 / 1024
    left_mb = FREE_LIMIT_MB - used_mb
    pct = used_mb / FREE_LIMIT_MB * 100

    print("=" * 62)
    print(" 창고 현황")
    print("=" * 62)
    print(f"  쓰는 중 : {_mb(used_mb)} / {FREE_LIMIT_MB:,}MB   ({pct:.1f}%)")
    print(f"  남은 자리: {_mb(left_mb)}")

    # 막대 하나로 한눈에.
    filled = int(min(pct, 100) / 2)
    print(f"  [{'#' * filled}{'.' * (50 - filled)}]")
    print()

    print("  표별 크기")
    print(f"    {'이름':<14}{'합계':>10}{'자료':>10}{'색인':>10}{'줄 수':>14}")
    for name, total, heap, idx in tables:
        rows = counts[name]
        print(
            f"    {name:<14}{total / 1024 / 1024:>8,.0f}MB"
            f"{heap / 1024 / 1024:>8,.0f}MB{idx / 1024 / 1024:>8,.0f}MB"
            f"{rows:>14,}"
        )
    print()

    print("  시세")
    print(f"    보유 기간 : {first_d} ~ {last_d}  (거래일 {days:,}일)")
    print(f"    줄 수     : {price_rows:,}건")
    print(f"    등락률 빈칸: {blank:,}건")
    print()

    # 언제 꽉 차는가. 지금까지 쌓인 것으로 한 줄당 무게를 역산합니다.
    if price_rows > 0 and left_mb > 0:
        # 시세 표가 실제로 차지하는 무게로 셈합니다. 데이터베이스 전체
        # 크기를 시세 줄 수로 나누면, 공시·재무 몫까지 시세에 얹혀서
        # 남은 날이 터무니없이 짧게 나옵니다.
        mb_per_row = (price_total_bytes / 1024 / 1024) / price_rows
        days_left = left_mb / (mb_per_row * ROWS_PER_DAY)
        print("  언제 꽉 차나 (지금 속도로 시세만 쌓일 때)")
        print(f"    하루 {ROWS_PER_DAY:,}줄씩 늘면 약 {days_left:,.0f}일 뒤")
        print(f"    (거래일 기준이라 실제로는 약 {days_left / 21:,.1f}개월)")
        if days_left < 90:
            print()
            print("    [!] 얼마 남지 않았습니다. 줄일 방법:")
            print("        · 오래된 시세를 지우기 (3년치 → 2년치)")
            print("        · 공시를 1년치만 남기기")
    elif left_mb <= 0:
        print("  [!] 한도를 넘었습니다. 저장이 실패하기 시작합니다.")
    print("=" * 62)


if __name__ == "__main__":
    main()
