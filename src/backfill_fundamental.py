"""
과거 투자지표(PER/PBR/EPS/BPS/배당수익률)를 채우는 스크립트.  ★ 1회 실행 ★

실행 방법:
    .venv\\Scripts\\python.exe -m src.backfill_fundamental

이미 저장된 시세는 건드리지 않고, 그 줄의 지표 칸만 채웁니다.
시세 수집(backfill.py)과 완전히 별개로 동작하므로, 이것이 실패해도
시세 데이터는 아무 영향을 받지 않습니다.

특징
  - 이미 채운 날짜는 건너뜁니다 (중단 후 이어받기 가능)
  - 하루치씩 나눠서 요청하고, 실패하면 다시 시도합니다
  - ETF 는 거래소가 투자지표를 주지 않으므로 대상이 아닙니다
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime

from .db import fetch_all, get_conn
from .krx import fetch_fundamentals
from .store import completed_dates, log_ingest, save_fundamentals


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="과거 투자지표 채우기 (이어받기 지원)")
    p.add_argument("--start", type=str, help="시작일 YYYY-MM-DD (기본: 보유 시세의 첫날)")
    p.add_argument("--end", type=str, help="종료일 YYYY-MM-DD (기본: 보유 시세의 마지막날)")
    return p.parse_args()


def fmt_eta(seconds: float) -> str:
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

    # 대상 날짜는 '이미 시세가 저장되어 있는 거래일'로 한정합니다.
    # 휴장일에 헛되이 요청하는 일이 없어집니다.
    with get_conn() as conn:
        sql = "SELECT DISTINCT trade_date FROM daily_price"
        params: list = []
        conds = []
        if args.start:
            conds.append("trade_date >= %s")
            params.append(datetime.strptime(args.start, "%Y-%m-%d").date())
        if args.end:
            conds.append("trade_date <= %s")
            params.append(datetime.strptime(args.end, "%Y-%m-%d").date())
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY trade_date"

        all_days = [r[0] for r in fetch_all(conn, sql, tuple(params) if params else None)]
        done = completed_dates(conn, "FUNDAMENTAL")

    todo = [d for d in all_days if d not in done]

    print("=" * 66)
    print(" 과거 투자지표(PER/PBR/EPS/BPS/배당) 채우기")
    print("=" * 66)
    if all_days:
        print(f"  보유 거래일 : {all_days[0]} ~ {all_days[-1]}  ({len(all_days)}일)")
    print(f"  받을 날짜   : {len(todo)}일")
    print("  중간에 멈춰도 다시 실행하면 이어서 받습니다.")
    print()

    if not todo:
        print("  이미 전부 받았습니다. 할 일이 없습니다.")
        return

    started = time.time()
    total = 0
    failed: list[date] = []

    for i, day in enumerate(todo, start=1):
        elapsed = time.time() - started
        eta = (elapsed / (i - 1) * (len(todo) - i + 1)) if i > 1 else 0
        prefix = f"  [{i:>4}/{len(todo)}] {day}"

        try:
            rows = fetch_fundamentals(day)
            with get_conn() as conn:
                if rows:
                    save_fundamentals(conn, rows)
                    log_ingest(conn, day, "FUNDAMENTAL", "done", len(rows))
                else:
                    log_ingest(conn, day, "FUNDAMENTAL", "holiday", 0, "자료 없음")
            total += len(rows)
            print(f"{prefix}  {len(rows):>5}종목  누적 {total:>9,}건 "
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
                    log_ingest(conn, day, "FUNDAMENTAL", "failed", 0, str(exc)[:400])
            except Exception:
                pass

    # 결과 확인
    with get_conn() as conn:
        filled, total_rows = fetch_all(
            conn,
            "SELECT count(*) FILTER (WHERE per IS NOT NULL OR bps IS NOT NULL), count(*) "
            "FROM daily_price;",
        )[0]

    print()
    print("=" * 66)
    print(" 완료!")
    print("=" * 66)
    print(f"  소요 시간      : {fmt_eta(time.time() - started)}")
    print(f"  지표가 있는 줄 : {filled:,}건 / 전체 {total_rows:,}건")
    print("  (ETF 는 거래소가 지표를 주지 않아 빈칸입니다 — 정상입니다)")
    if failed:
        print(f"\n  [!] 실패한 날짜 {len(failed)}일. 다시 실행하면 그 날만 재시도합니다.")


if __name__ == "__main__":
    main()
