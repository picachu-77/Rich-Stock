"""
야후 파이낸스(yfinance)에서 미국 시세·지수·환율을 받아옵니다.

★ 왜 야후인가 ★
  한국 시세는 pykrx(거래소 공식)를 그대로 씁니다. 바꾸지 않습니다.
  야후는 pykrx 가 아예 못 주는 것만 맡습니다 — 미국 종목, 그리고
  지수와 환율입니다.

★ 조심할 것 ★
  야후는 공식 창구가 아니라 화면을 긁어오는 방식입니다. 한꺼번에
  많이 부르면 막힙니다(429). 그래서
    - 시세는 여러 종목을 한 번에 묶어서 부르고 (20개씩)
    - 회사 정보는 한 종목씩 부르되 사이에 쉬고
    - 실패하면 시간을 늘려가며 다시 시도합니다
  그래도 몇 종목이 빠질 수 있습니다. 빠지면 다음 날 다시 채웁니다 —
  한 번에 다 받아야만 하는 구조로 만들지 않았습니다.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd

# 지수와 환율. 왼쪽이 야후 기호, 오른쪽이 화면에 쓸 이름입니다.
INDEXES: dict[str, str] = {
    "^KS11": "코스피",
    "^KQ11": "코스닥",
    "^GSPC": "S&P 500",
    "^IXIC": "나스닥",
    "KRW=X": "원달러 환율",
}

FX_SYMBOL = "KRW=X"

CHUNK = 20          # 한 번에 묶어 부를 종목 수
PAUSE = 1.5         # 묶음 사이에 쉬는 시간(초)
RETRY = 3           # 실패했을 때 다시 해보는 횟수


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _download(symbols: list[str], start: date, end: date) -> pd.DataFrame:
    """
    yfinance 로 여러 기호를 한 번에 받아옵니다.

    auto_adjust=False 로 두는 이유: 액면분할·배당을 반영해 과거 가격을
    고쳐 쓰면, 사람이 그날 실제로 본 가격과 달라집니다. 이 사이트는
    '그날 얼마였나' 를 보여주는 곳이라 손대지 않은 종가를 씁니다.
    """
    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(RETRY):
        try:
            df = yf.download(
                symbols,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
                progress=False,
                threads=False,
                group_by="column",
            )
            if df is not None and len(df):
                return df
            last_err = RuntimeError("빈 응답")
        except Exception as e:      # 연결 끊김·429 등
            last_err = e
        wait = PAUSE * (2 ** attempt)
        print(f"    · 다시 시도합니다 ({attempt + 1}/{RETRY}, {wait:.0f}초 뒤) — {last_err}")
        _sleep(wait)
    print(f"    ! 받지 못했습니다: {last_err}")
    return pd.DataFrame()


def _column(df: pd.DataFrame, field: str, symbol: str) -> pd.Series | None:
    """
    yfinance 가 돌려주는 표에서 (항목, 종목) 칸 하나를 꺼냅니다.

    종목이 하나면 칸 이름이 그냥 'Close', 여럿이면 ('Close','AAPL') 로
    2층이 됩니다. 두 경우를 모두 받습니다.
    """
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if (field, symbol) not in df.columns:
                return None
            return df[(field, symbol)]
        if field not in df.columns:
            return None
        return df[field]
    except Exception:
        return None


def fetch_prices(
    symbols: list[str], start: date, end: date
) -> dict[str, list[tuple[date, float, int | None]]]:
    """
    종목별 (날짜, 종가, 거래량) 목록을 돌려줍니다. 종가는 상장된 나라의
    돈 단위 그대로입니다 (미국 종목이면 달러).
    """
    out: dict[str, list[tuple[date, float, int | None]]] = {}
    for i in range(0, len(symbols), CHUNK):
        batch = symbols[i : i + CHUNK]
        print(f"  · {i + 1}~{i + len(batch)}번째 종목 시세 요청 중...")
        df = _download(batch, start, end)
        if df.empty:
            continue
        for sym in batch:
            closes = _column(df, "Close", sym)
            if closes is None:
                continue
            volumes = _column(df, "Volume", sym)
            rows: list[tuple[date, float, int | None]] = []
            for ts, close in closes.items():
                if pd.isna(close):
                    continue
                d = ts.date() if isinstance(ts, (pd.Timestamp, datetime)) else ts
                vol = None
                if volumes is not None:
                    v = volumes.get(ts)
                    if v is not None and not pd.isna(v):
                        vol = int(v)
                rows.append((d, float(close), vol))
            if rows:
                out[sym] = sorted(rows)
        _sleep(PAUSE)
    return out


def fetch_series(symbol: str, start: date, end: date) -> list[tuple[date, float]]:
    """지수·환율처럼 종목 하나짜리를 받아옵니다."""
    df = _download([symbol], start, end)
    closes = _column(df, "Close", symbol)
    if closes is None:
        return []
    out: list[tuple[date, float]] = []
    for ts, close in closes.items():
        if pd.isna(close):
            continue
        d = ts.date() if isinstance(ts, (pd.Timestamp, datetime)) else ts
        out.append((d, float(close)))
    return sorted(out)


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def _as_pct(v) -> float | None:
    """
    소수로 오는 비율(0.147)을 % (14.7)로 바꿉니다.

    ★ '1보다 작으면 소수' 같은 눈치 규칙을 쓰지 않습니다 ★
      ROE 가 1.2 로 왔을 때 그것이 1.2% 인지 120% 인지 값만 봐서는
      알 수 없습니다. 야후는 항목마다 단위가 정해져 있으니
      (returnOnEquity·operatingMargins 는 늘 소수,
       debtToEquity 는 늘 %) 항목별로 맞는 함수를 씁니다.
    """
    x = _num(v)
    return None if x is None else x * 100


def _div_yield(info: dict) -> float | None:
    """
    배당수익률(%)을 고릅니다.

    ★ dividendYield 를 그대로 믿지 않는 이유 ★
      yfinance 는 판이 바뀌면서 이 값의 단위를 바꿨습니다. 예전에는
      소수(0.0044)였고 지금은 %(0.44)입니다. 값만 봐서는 0.44 가
      0.44% 인지 44% 인지 알 수 없습니다.

      trailingAnnualDividendYield 는 줄곧 소수라서 흔들리지 않습니다.
      그것을 먼저 쓰고, 없을 때만 dividendYield 를 % 로 봅니다.
    """
    x = _num(info.get("trailingAnnualDividendYield"))
    if x is not None:
        return x * 100
    return _num(info.get("dividendYield"))


def fetch_profiles(symbols: list[str], pause: float = 0.8) -> dict[str, dict]:
    """
    종목 하나하나의 지금 상태를 받아옵니다.
      거래소·업종·PER·PBR·배당수익률·주식수, 그리고
      ROE·부채비율·영업이익률 (최근 1년 기준)

    한 종목씩 부르기 때문에 100종목이면 2분 남짓 걸립니다. 시세와 달리
    묶어서 부를 방법이 없습니다.
    """
    import yfinance as yf

    out: dict[str, dict] = {}
    for n, sym in enumerate(symbols, 1):
        info: dict = {}
        for attempt in range(RETRY):
            try:
                info = yf.Ticker(sym).get_info() or {}
                break
            except Exception as e:
                if attempt == RETRY - 1:
                    print(f"    ! {sym} 회사 정보를 받지 못했습니다: {e}")
                _sleep(pause * (2 ** attempt))
        if not info:
            continue

        div = _div_yield(info)
        if div is not None and (div < 0 or div > 30):
            div = None              # 말이 안 되는 값은 버립니다

        out[sym] = {
            "exchange": info.get("exchange"),
            "sector": info.get("sector"),
            "shares": _num(info.get("sharesOutstanding")),
            "market_cap": _num(info.get("marketCap")),
            "per": _num(info.get("trailingPE")),
            "pbr": _num(info.get("priceToBook")),
            "div_yield": div,
            "roe": _as_pct(info.get("returnOnEquity")),
            # 야후의 debtToEquity 는 이미 % 입니다 (145.0 = 145%).
            # 여기에 100을 곱하면 안 됩니다.
            "debt_ratio": _num(info.get("debtToEquity")),
            "op_margin": _as_pct(info.get("operatingMargins")),
        }
        if n % 20 == 0:
            print(f"    · {n}/{len(symbols)}종목 정보 수집")
        _sleep(pause)
    return out
