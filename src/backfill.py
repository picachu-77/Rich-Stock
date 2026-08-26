"""
과거 시세를 채우는 초기화 스크립트.  ★ 최초 1회만 실행 ★

실행 방법 (기본 = 최근 3년):
    .venv\\Scripts\\python.exe -m src.backfill

기간을 직접 정하고 싶다면:
    .venv\\Scripts\\python.exe -m src.backfill --years 1
    .venv\\Scripts\\python.exe -m src.backfill --start 2024-01-01 --end 2024-12-31

중요한 특징
  - 오래 걸립니다 (3년치면 대략 1~3시간). 진행 상황이 화면에 계속 표시됩니다.
  - 중간에 멈춰도(Ctrl+C, 컴퓨터 끄기 등) 괜찮습니다.
    다시 실행하면 이미 받은 날짜는 건너뛰고 이어서 받습니다.
  - 하루치씩 나눠서 요청하므로 거래소에 부담을 주지 않습니다.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta

from .db import get_conn
from .krx import fetch_etf_prices, fetch_stock_prices, kst_today, weekdays_between
from .store import (
    clear_bogus_change_pct,
    completed_dates,
    fill_missing_change_pct,
    log_ingest,
    save_prices,
    summary,
)
from .update_tickers import refresh_tickers


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="과거 시세 채우기 (이어받기 지원)")
    p.add_argument("--years", type=int, default=3, help="최근 몇 년치를 받을지 (기본 3)")
    p.add_argument("--start", type=str, help="시작일 YYYY-MM-DD (지정 시 --years 무시)")
    p.add_argument("--end", type=str, help="종료일 YYYY-MM-DD (기본: 오늘)")
    p.add_argument(
        "--skip-tickers",
        action="store_true",
        help="종목 목록 갱신을 건너뜁니다 (이미 했다면 사용)",
    )
    return p.parse_args()


def fmt_eta(seconds: float) -> str:
    """남은 시간을 '1시간 23분' 처럼 보기 좋게 바꿉니다."""
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}시간 {m}분"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


def main() -> None:
    args = parse_args()

    end = (
        datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else kst_today()
    )
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        # ★ 여유분 30일을 더 받습니다 ★
        # 예를 들어 딱 3년치만 받으면, 화면에서 '3년 수익률'을 계산할 때
        # "3년 전 종가"를 찾지 못해 전 종목이 빈칸으로 나옵니다.
        # (윤년 때문에 하루가 모자라거나, 그날이 휴장일일 수 있어서)
        start = end - timedelta(days=365 * args.years + 30)

    print("=" * 66)
    print(" 과거 시세 채우기 (초기화)")
    print("=" * 66)
    print(f"  대상 기간 : {start}  ~  {end}")
    print("  중간에 멈춰도 다시 실행하면 이어서 받습니다.")
    print()

    with get_conn() as conn:
        # 1) 종목 목록 먼저 채웁니다
        if not args.skip_tickers:
            print("[1/2] 종목 목록 준비")
            refresh_tickers(conn)
            print()

        # 2) 이미 받은 날짜 확인 (이어받기)
        done_stock = completed_dates(conn, "STOCK")
        done_etf = completed_dates(conn, "ETF")

    all_days = list(weekdays_between(start, end))
    todo = [d for d in all_days if d not in done_stock or d not in done_etf]

    print(f"[2/2] 일별 시세 수집")
    print(f"  전체 평일 {len(all_days):,}일 중, 아직 안 받은 날 {len(todo):,}일")
    if not todo:
        print("\n  이미 전부 받았습니다. 할 일이 없습니다.")
        return
    print()

    started = time.time()
    total_rows = 0
    failed: list[date] = []

    for i, day in enumerate(todo, start=1):
        elapsed = time.time() - started
        eta = (elapsed / (i - 1) * (len(todo) - i + 1)) if i > 1 else 0
        prefix = f"  [{i:>4}/{len(todo)}] {day}"

        try:
            with get_conn() as conn:
                day_rows = 0
                is_holiday = True

                # ── 일반주식 ──
                if day not in done_stock:
                    rows = fetch_stock_prices(day)
                    if rows:
                        day_rows += save_prices(conn, rows)
                        is_holiday = False
                        log_ingest(conn, day, "STOCK", "done", len(rows))
                    else:
                        log_ingest(conn, day, "STOCK", "holiday", 0, "자료 없음")

                # ── ETF ──
                if day not in done_etf:
                    rows = fetch_etf_prices(day)
                    if rows:
                        day_rows += save_prices(conn, rows)
                        is_holiday = False
                        log_ingest(conn, day, "ETF", "done", len(rows))
                    else:
                        log_ingest(conn, day, "ETF", "holiday", 0, "자료 없음")

            total_rows += day_rows
            if is_holiday:
                print(f"{prefix}  휴장일 (건너뜀)          "
                      f"| 남은 예상시간 {fmt_eta(eta)}")
            else:
                print(f"{prefix}  {day_rows:>5}건 저장  누적 {total_rows:>8,}건 "
                      f"| 남은 예상시간 {fmt_eta(eta)}")

        except KeyboardInterrupt:
            print("\n\n  [중단됨] 여기까지 받은 내용은 안전하게 저장되었습니다.")
            print("  다시 실행하면 이 지점부터 이어서 받습니다.")
            sys.exit(0)

        except Exception as exc:  # noqa: BLE001
            failed.append(day)
            print(f"{prefix}  [실패] {exc}")
            try:
                with get_conn() as conn:
                    log_ingest(conn, day, "STOCK", "failed", 0, str(exc)[:400])
                    log_ingest(conn, day, "ETF", "failed", 0, str(exc)[:400])
            except Exception:
                pass

    # 3) 마무리 — 등락률 정리
    #
    # 종목을 몇백 개씩 나눠서 처리합니다. 한 문장으로 280만 줄을 한꺼번에
    # 훑으면 Supabase 가 2분 제한에 걸려 통째로 실패합니다(실제로 겪었습니다).
    # 나눠 두면 조각마다 저장되므로 도중에 끊겨도 다시 돌리면 이어집니다.
    print("\n  등락률 정리 중...")

    def 진행(done: int, total: int, rows: int) -> None:
        print(f"    {done:,}/{total:,}개 종목  ({rows:,}건)", flush=True)

    with get_conn() as conn:
        # (1) 날짜 간격이 벌어진 상태에서 잘못 계산된 값을 먼저 비웁니다
        print("  (1/2) 잘못된 값 지우는 중...", flush=True)
        cleared = clear_bogus_change_pct(conn, progress=진행)
        # (2) 비어 있는 줄을 바로 전 거래일 종가와 비교해 다시 계산합니다
        print("  (2/2) 빈 값 계산하는 중...", flush=True)
        filled = fill_missing_change_pct(conn, progress=진행)
        info = summary(conn)
    print(f"  잘못된 값 {cleared:,}건 제거, {filled:,}건 새로 계산 완료")

    print()
    print("=" * 66)
    print(" 완료!")
    print("=" * 66)
    print(f"  총 소요시간   : {fmt_eta(time.time() - started)}")
    print(f"  저장된 시세   : {info['price_rows']:,}건")
    print(f"  보유 기간     : {info['first_date']} ~ {info['last_date']}")
    print(f"  등록 종목 수  : {info['ticker_total']:,}개")
    if failed:
        print(f"\n  [!] 실패한 날짜 {len(failed):,}일: {failed[:10]}"
              f"{' ...' if len(failed) > 10 else ''}")
        print("      이 스크립트를 한 번 더 실행하면 실패한 날만 다시 시도합니다.")


if __name__ == "__main__":
    main()
