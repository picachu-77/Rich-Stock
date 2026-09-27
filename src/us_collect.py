"""
미국 종목·지수·환율 수집기.

실행 방법
    python -m src.us_collect              # 최근 7일치 (매일 돌리는 용도)
    python -m src.us_collect --days 365   # 1년치 (처음 한 번)

하는 일 (순서대로)
  1) 지수와 환율을 받습니다  (코스피·코스닥·S&P500·나스닥·원달러)
  2) 회사 정보를 받습니다    (거래소·업종·PER·PBR·배당·ROE·부채비율)
  3) 종목 목록을 저장합니다
  4) 시세를 받아 원으로 바꿔 저장합니다
  5) 최근 1년 재무지표를 저장합니다

★ 값을 원으로 바꿔서 넣는 이유 ★
  화면 전체가 원 단위로 짜여 있습니다. 목록의 시가총액 줄세우기,
  모의투자의 잔고 계산이 전부 그렇습니다. 달러를 그대로 넣으면
  '시총 1,200' 이 억원인지 억달러인지 알 수 없게 되고, 미국 종목이
  줄세우기 맨 아래에 몰립니다.

  그래서 close 에는 그날 환율로 바꾼 원화 값을 넣고, 손대지 않은
  달러 값은 close_local 에 함께 넣습니다. 화면에서는 달러를 보여주고
  원화를 옆에 붙입니다.
"""

from __future__ import annotations

import argparse
import bisect
import sys
from datetime import date, timedelta

from .db import get_conn
from .store import (
    fx_rates,
    log_ingest,
    save_fundamentals,
    save_index_prices,
    save_us_financials,
    save_us_prices,
    save_us_tickers,
    summary,
)
from .us_list import EXCHANGE, SECTOR_KO, US_TICKERS
from .yahoo import (
    ECONOMY,
    FX_SYMBOL,
    INDEXES,
    SANE,
    fetch_annuals,
    fetch_prices,
    fetch_profiles,
    fetch_series,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="미국 종목·지수·환율 수집")
    p.add_argument("--days", type=int, default=7,
                   help="며칠 전까지 받을지 (기본 7. 처음 채울 때는 365)")
    p.add_argument("--skip-profile", action="store_true",
                   help="회사 정보(느림)를 건너뛰고 시세만 받습니다")
    p.add_argument("--with-annuals", action="store_true",
                   help="연간 재무까지 받습니다 (느림. 해마다 한 번이면 충분)")
    return p.parse_args()


# ── 환율 ──────────────────────────────────────────────────────
class Fx:
    """
    날짜를 주면 그날 환율을 돌려줍니다.

    ★ 그날 값이 없으면 그 전 가장 가까운 날 값을 씁니다 ★
      환율은 한국·미국 어느 쪽 휴일이냐에 따라 빠지는 날이 다릅니다.
      미국 장이 열린 날 환율이 없는 경우가 실제로 생깁니다. 그럴 때
      건너뛰면 그날 시세가 통째로 빠지므로, 직전 환율을 씁니다.
    """

    def __init__(self, table: dict):
        self.days = sorted(table)
        self.rates = [table[d] for d in self.days]

    def ok(self) -> bool:
        return bool(self.days)

    def at(self, d: date) -> float | None:
        if not self.days:
            return None
        i = bisect.bisect_right(self.days, d) - 1
        if i < 0:
            # 받아둔 환율보다 더 옛날 날짜입니다. 가장 오래된 값을 씁니다.
            return self.rates[0]
        return self.rates[i]


def collect_indexes(conn, start: date, end: date) -> int:
    """지수·환율과 경제 지표를 받아 저장합니다.

    같은 표(market_index)에 함께 담습니다. 생김새가 똑같기 때문입니다
    — 기호, 날짜, 값, 전날 대비. 무엇을 어느 칸에 보여줄지는 화면
    쪽에서 기호를 보고 정합니다.
    """
    saved = 0
    for symbol, name in {**INDEXES, **ECONOMY}.items():
        print(f"  · {name} ({symbol}) 받는 중...")
        series = fetch_series(symbol, start, end)
        if not series:
            print(f"    ! {name} 은 받지 못했습니다. 다음으로 넘어갑니다.")
            continue

        # 단위가 뒤집힌 채로 들어오는 일을 막습니다. 자세한 사정은
        # yahoo.py 의 SANE 주석에 적어뒀습니다.
        lo, hi = SANE.get(symbol, (float("-inf"), float("inf")))
        last = series[-1][1]
        if not (lo <= last <= hi):
            print(f"    ! {name} 의 마지막 값이 {last:,.4f} 입니다.")
            print(f"      {lo:,.0f} ~ {hi:,.0f} 안에 있어야 합니다.")
            print("      단위가 바뀐 것 같아 저장하지 않고 넘어갑니다.")
            continue

        rows = []
        prev: float | None = None
        for d, close in series:
            pct = None if prev in (None, 0) else round((close / prev - 1) * 100, 4)
            rows.append((symbol, d, round(close, 4), pct))
            prev = close
        saved += save_index_prices(conn, rows)
        print(f"    → {len(rows):,}일치")
    return saved


def collect(conn, days: int, skip_profile: bool, with_annuals: bool = False) -> None:
    end = date.today()
    start = end - timedelta(days=days)
    print(f"\n[1/5] 지수·환율·경제 지표 ({start} ~ {end})")
    collect_indexes(conn, start, end)

    fx = Fx(fx_rates(conn, FX_SYMBOL))
    if not fx.ok():
        print("\n  ! 환율을 한 건도 받지 못했습니다.")
        print("    달러를 원으로 바꿀 수 없어 여기서 멈춥니다.")
        print("    (틀린 값을 넣느니 아무것도 넣지 않는 편이 낫습니다)")
        sys.exit(1)
    print(f"  환율 {len(fx.days):,}일치 확보 · 최근 {fx.rates[-1]:,.2f}원/달러")

    symbols = [t[0] for t in US_TICKERS]

    print(f"\n[2/5] 회사 정보 ({len(symbols)}종목)")
    profiles = {} if skip_profile else fetch_profiles(symbols)
    if skip_profile:
        print("  건너뜁니다 (--skip-profile)")
    else:
        print(f"  {len(profiles):,}종목 정보를 받았습니다")

    print("\n[3/5] 종목 목록 저장")
    tickers = []
    for code, name, market, kind in US_TICKERS:
        info = profiles.get(code, {})
        # 야후가 알려주는 거래소가 있으면 그것을 씁니다. 손으로 적어둔
        # 값은 틀릴 수 있고, 상장 시장은 옮겨가기도 합니다.
        market = EXCHANGE.get(str(info.get("exchange") or ""), market)
        sector = SECTOR_KO.get(str(info.get("sector") or ""))
        tickers.append({"code": code, "name": name, "market": market,
                        "kind": kind, "sector_name": sector})
    saved = save_us_tickers(conn, tickers, end)
    print(f"  {saved:,}종목 저장")

    print(f"\n[4/5] 시세 ({start} ~ {end})")
    prices = fetch_prices(symbols, start, end)
    got = sum(len(v) for v in prices.values())
    print(f"  {len(prices):,}종목 · {got:,}일치를 받았습니다")

    rows = []
    for code, series in prices.items():
        shares = (profiles.get(code) or {}).get("shares")
        last_day = series[-1][0] if series else None
        prev: float | None = None
        for d, close_local, volume in series:
            rate = fx.at(d)
            if rate is None:
                continue
            # 등락률은 달러 기준입니다. 원화로 재면 환율 움직임까지
            # 섞여서 '이 회사가 얼마나 올랐나' 가 흐려집니다.
            pct = None if prev in (None, 0) else round((close_local / prev - 1) * 100, 4)
            prev = close_local

            # 시가총액은 가장 최근 날짜에만 넣습니다. 주식수는 '지금'
            # 값 하나뿐이라, 과거 날짜에 곱하면 그때 시총이 아닙니다.
            cap = None
            if shares and d == last_day:
                cap = int(shares * close_local * rate)

            rows.append((code, d, int(round(close_local * rate)),
                         round(close_local, 4), pct, volume, cap))

    saved = save_us_prices(conn, rows)
    print(f"  {saved:,}줄 저장")

    # PER·PBR·배당수익률은 '지금' 값 하나뿐이라 가장 최근 날짜에만 넣습니다.
    fund_rows = []
    fin_rows = []
    year = end.year
    for code, info in profiles.items():
        series = prices.get(code)
        if series:
            fund_rows.append((code, series[-1][0], info.get("per"), info.get("pbr"),
                              None, None, info.get("div_yield"), None))
        if any(info.get(k) is not None for k in ("roe", "debt_ratio", "op_margin")):
            fin_rows.append((code, year, 0, info.get("roe"), info.get("debt_ratio"),
                             info.get("op_margin"), "yahoo-ttm"))

    print("\n[5/5] 지표 저장")
    print(f"  PER·PBR·배당 {save_fundamentals(conn, fund_rows):,}종목")
    print(f"  ROE·부채비율(최근 1년) {save_us_financials(conn, fin_rows):,}종목")

    # ★ 연간 재무 ★
    #   '최근 1년' 한 덩어리만으로는 '지금 어떤가' 는 말해도 '어느 쪽으로
    #   가고 있나' 는 말할 수 없습니다. 연간 재무를 받아야 재무 흐름 표가
    #   한 칸짜리를 넘어섭니다. (표는 두 칸부터 보여줍니다)
    #
    #   분기는 4(사업보고서)로 넣습니다. 한국 종목의 연간 자리와 같습니다.
    if with_annuals:
        print("\n[덤] 연간 재무 (느립니다)")
        annuals = fetch_annuals([c for c in symbols if c in prices])
        rows_a = []
        for code, years in annuals.items():
            for y in years:
                rows_a.append((code, y["year"], 4, y["roe"], y["debt_ratio"],
                               y["op_margin"], "yahoo-annual"))
        print(f"  {len(annuals):,}종목 · {save_us_financials(conn, rows_a):,}개 연도 저장")

    log_ingest(conn, end, "US", "done", len(rows), f"{len(prices)}종목")


def main() -> None:
    args = parse_args()
    print("=" * 60)
    print(" 미국 종목·지수·환율 수집")
    print("=" * 60)

    with get_conn() as conn:
        collect(conn, args.days, args.skip_profile, args.with_annuals)
        info = summary(conn)

    print()
    print(f"  현재 등록 종목 수 : {info['ticker_total']:,}개")
    print("완료!")


if __name__ == "__main__":
    main()
