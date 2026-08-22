"""
종목 목록을 최신 상태로 갱신하는 스크립트.

실행 방법:
    .venv\\Scripts\\python.exe -m src.update_tickers

하는 일
  - 오늘 기준 코스피/코스닥 일반주식 + ETF 전 종목 목록을 가져옵니다.
  - ticker 표에 저장합니다. (새로 상장된 종목은 추가됩니다)
  - 목록에서 사라진 종목은 is_active=FALSE 로 표시합니다. (상장폐지)
    ※ 지우지 않습니다. 과거 시세는 그대로 남습니다.
"""

from __future__ import annotations

from datetime import date, timedelta

from .db import get_conn
from .krx import fetch_ticker_master, kst_today
from .store import mark_delisted, save_tickers, summary


def refresh_tickers(conn, as_of: date | None = None) -> int:
    """종목 목록을 가져와 저장하고, 저장한 개수를 돌려줍니다."""
    as_of = as_of or kst_today()

    # 주말·휴장일에는 목록이 비어 있을 수 있으므로 최대 7일 전까지 거슬러 올라갑니다.
    tickers: list[dict] = []
    probe = as_of
    for _ in range(8):
        print(f"  기준일 {probe} 종목 목록을 가져옵니다...")
        tickers = fetch_ticker_master(probe)
        if tickers:
            break
        print("    → 해당일 자료 없음(휴장일로 보임). 하루 앞으로 이동합니다.")
        probe -= timedelta(days=1)

    if not tickers:
        raise RuntimeError("최근 8일 동안 종목 목록을 한 건도 가져오지 못했습니다.")

    saved = save_tickers(conn, tickers, probe)

    stock_cnt = sum(1 for t in tickers if t["kind"] == "STOCK")
    etf_cnt = sum(1 for t in tickers if t["kind"] == "ETF")
    print(f"  저장 완료: 총 {saved}종목 (일반주식 {stock_cnt} / ETF {etf_cnt})")

    delisted = mark_delisted(conn, probe)
    if delisted:
        print(f"  목록에서 사라진 {delisted}종목을 '상장폐지'로 표시했습니다.")

    return saved


def main() -> None:
    print("=" * 60)
    print(" 종목 목록 갱신")
    print("=" * 60)

    with get_conn() as conn:
        refresh_tickers(conn)
        info = summary(conn)

    print()
    print(f"  현재 등록 종목 수 : {info['ticker_total']:,}개 "
          f"(상장중 {info['ticker_active']:,}개)")
    print("완료!")


if __name__ == "__main__":
    main()
