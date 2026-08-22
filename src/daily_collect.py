"""
매일 실행용 수집기.  ★ GitHub Actions 가 매일 밤 11시에 자동으로 돌립니다 ★

직접 실행해 보고 싶다면:
    .venv\\Scripts\\python.exe -m src.daily_collect

특정 날짜만 다시 받고 싶다면:
    .venv\\Scripts\\python.exe -m src.daily_collect --date 2026-08-13

하는 일 (순서대로)
  1) 종목 목록 갱신  → 신규 상장 / 상장폐지 반영
  2) 그날의 일반주식 전 종목 시세 저장
  3) 그날의 ETF 전 종목 시세 저장
  4) 비어 있는 등락률 계산해서 채우기
  휴장일이면 아무것도 저장하지 않고 정상 종료합니다.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from .db import get_conn
from .krx import (
    fetch_etf_prices,
    fetch_fundamentals,
    fetch_stock_prices,
    kst_today,
)
from .store import (
    fill_missing_change_pct,
    log_ingest,
    save_fundamentals,
    save_prices,
    summary,
)
from .update_tickers import refresh_tickers


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="오늘자 시세 수집")
    p.add_argument("--date", type=str, help="수집할 날짜 YYYY-MM-DD (기본: 오늘)")
    p.add_argument(
        "--lookback",
        type=int,
        default=0,
        help="지정한 날부터 며칠 전까지 함께 채울지 (기본 0 = 하루만)",
    )
    return p.parse_args()


def collect_one_day(conn, day) -> tuple[int, bool]:
    """하루치를 수집합니다. (저장건수, 휴장여부)를 돌려줍니다."""
    saved = 0
    got_any = False

    print(f"  - 일반주식 시세 요청 중...")
    stock_rows = fetch_stock_prices(day)
    if stock_rows:
        saved += save_prices(conn, stock_rows)
        got_any = True
        log_ingest(conn, day, "STOCK", "done", len(stock_rows))
        print(f"    {len(stock_rows):,}종목 저장")
    else:
        log_ingest(conn, day, "STOCK", "holiday", 0, "자료 없음")
        print("    자료 없음")

    print(f"  - ETF 시세 요청 중...")
    etf_rows = fetch_etf_prices(day)
    if etf_rows:
        saved += save_prices(conn, etf_rows)
        got_any = True
        log_ingest(conn, day, "ETF", "done", len(etf_rows))
        print(f"    {len(etf_rows):,}종목 저장")
    else:
        log_ingest(conn, day, "ETF", "holiday", 0, "자료 없음")
        print("    자료 없음")

    # ── 투자지표(PER/PBR/EPS/BPS/배당) ──
    # 여기서 문제가 생겨도 위에서 저장한 시세는 그대로 남도록
    # 따로 떼어내서 오류를 삼킵니다.
    if got_any:
        print(f"  - 투자지표(PER/PBR 등) 요청 중...")
        try:
            fund_rows = fetch_fundamentals(day)
            if fund_rows:
                save_fundamentals(conn, fund_rows)
                log_ingest(conn, day, "FUNDAMENTAL", "done", len(fund_rows))
                print(f"    {len(fund_rows):,}종목 저장")
            else:
                log_ingest(conn, day, "FUNDAMENTAL", "holiday", 0, "자료 없음")
                print("    자료 없음")
        except Exception as exc:  # noqa: BLE001
            log_ingest(conn, day, "FUNDAMENTAL", "failed", 0, str(exc)[:400])
            print(f"    [!] 투자지표만 실패했습니다: {exc}")
            print("        시세는 정상 저장되었습니다. 나중에 다시 받으면 됩니다.")

    return saved, not got_any


def main() -> None:
    args = parse_args()
    target = (
        datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else kst_today()
    )

    print("=" * 60)
    print(f" 일일 시세 수집  (기준일: {target})")
    print("=" * 60)

    days = [target - timedelta(days=n) for n in range(args.lookback + 1)]
    days = [d for d in days if d.weekday() < 5]  # 주말 제외
    days.sort()

    if not days:
        print("\n  주말입니다. 수집할 것이 없습니다.")
        return

    total_saved = 0
    with get_conn() as conn:
        print("\n[1/3] 종목 목록 갱신")
        refresh_tickers(conn)

        print("\n[2/3] 시세 수집")
        for day in days:
            print(f"\n  === {day} ===")
            saved, is_holiday = collect_one_day(conn, day)
            total_saved += saved
            if is_holiday:
                print("  → 휴장일이었습니다.")

        print("\n[3/3] 등락률 보정")
        filled = fill_missing_change_pct(conn)
        print(f"  {filled:,}건 계산해서 채웠습니다.")

        info = summary(conn)

    print()
    print("=" * 60)
    print(" 완료!")
    print("=" * 60)
    print(f"  이번에 저장한 시세 : {total_saved:,}건")
    print(f"  창고 전체 시세     : {info['price_rows']:,}건")
    print(f"  보유 기간          : {info['first_date']} ~ {info['last_date']}")
    print(f"  등록 종목 수       : {info['ticker_total']:,}개 "
          f"(상장중 {info['ticker_active']:,}개)")


if __name__ == "__main__":
    main()
