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

# ── 경제 지표 ────────────────────────────────────────────────
# 지수(INDEXES)와 일부러 나눠 둡니다.
#   지수  = "오늘 시장이 오른 날인가 내린 날인가"
#   지표  = "요즘 돈의 사정이 어떤가" — 살지 말지를 정할 때 배경이 되는 값
# 화면에서도 다른 칸에 놓습니다.
#
# ★ 단위가 서로 다릅니다 ★
#   금리는 그 자체가 % 입니다. 4.20% 에서 4.29% 로 오른 것을
#   '+2.1%' 라고 말하면 금리가 두 배쯤 뛴 것처럼 읽히는데, 실제로는
#   0.09%p 입니다. 어느 쪽으로 말할지는 화면 쪽(lib/economy.ts)이
#   정합니다. 여기서는 받은 값을 그대로 저장합니다.
ECONOMY: dict[str, str] = {
    "^TNX": "미국 10년 국채 금리",
    "CL=F": "국제 유가",
    "GC=F": "금",
    "^VIX": "공포지수",
}

# 상식에서 벗어난 값을 걸러내는 범위.
#
#   야후가 ^TNX 를 '4.23'(퍼센트)으로 주는지 '42.3'(십분의 일)로
#   주는지는 시기에 따라 달랐던 적이 있습니다. 틀린 단위로 조용히
#   저장하면 화면에 '미국 금리 42%' 가 뜹니다. 그럴 바엔 저장하지
#   않고 로그에 남기는 편이 낫습니다.
SANE: dict[str, tuple[float, float]] = {
    "^TNX": (0.0, 25.0),
    "^VIX": (5.0, 150.0),
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


# ── 연간 재무 (미국 종목의 '흐름' 을 위해) ────────────────────
#
# ★ 왜 따로 받나 ★
#   회사 정보(.info)가 주는 ROE·부채비율은 '최근 12개월' 한 덩어리입니다.
#   그것만으로는 '지금 어떤가' 는 말해도 '어느 쪽으로 가고 있나' 는
#   말할 수 없습니다. 초보자에게는 뒤쪽이 훨씬 중요합니다.
#
#   연간 재무제표를 받으면 3~4년치가 나옵니다. 한국 종목의 재무 흐름과
#   같은 자리에 같은 모양으로 들어갑니다.
#
# ★ 원본 금액은 저장하지 않습니다 ★
#   financial 표의 금액 칸들은 '원' 단위로 적어둔 곳입니다. 달러 금액을
#   넣으면 단위가 뒤섞입니다. 비율(ROE·부채비율·영업이익률)만 넣습니다.

# 야후가 주는 항목 이름은 판마다 조금씩 다릅니다. 후보를 여러 개 둡니다.
_REVENUE = ("Total Revenue", "Operating Revenue", "TotalRevenue")
_OPINCOME = ("Operating Income", "Total Operating Income As Reported", "OperatingIncome")
_NETINCOME = ("Net Income", "Net Income Common Stockholders", "NetIncome")
_EQUITY = ("Stockholders Equity", "Total Stockholder Equity", "StockholdersEquity")
_LIABILITIES = (
    "Total Liabilities Net Minority Interest",
    "Total Liabilities",
    "TotalLiabilitiesNetMinorityInterest",
)


def _pick(df, names, column):
    """여러 이름 중 먼저 맞는 줄의 값을 꺼냅니다."""
    if df is None or getattr(df, "empty", True):
        return None
    for n in names:
        if n in df.index:
            try:
                v = df.loc[n, column]
            except Exception:
                continue
            if v is None:
                continue
            try:
                x = float(v)
            except (TypeError, ValueError):
                continue
            if x == x:                  # NaN 아님
                return x
    return None


def fetch_annuals(
    symbols: list[str], years: int = 4, pause: float = 1.0
) -> dict[str, list[dict]]:
    """
    종목별 연간 재무 비율을 돌려줍니다.
        [{"year": 2025, "roe": 12.3, "debt_ratio": 145.0, "op_margin": 28.1}, ...]

    한 종목에 두 번씩 부릅니다(손익계산서·재무상태표). 100종목이면
    3~4분 걸립니다. 해마다 한 번만 바뀌는 값이라 매일 받을 필요는
    없습니다.
    """
    import yfinance as yf

    out: dict[str, list[dict]] = {}
    for n, sym in enumerate(symbols, 1):
        try:
            t = yf.Ticker(sym)
            inc = t.income_stmt
            bal = t.balance_sheet
        except Exception as e:
            print(f"    ! {sym} 연간 재무를 받지 못했습니다: {e}")
            _sleep(pause)
            continue

        if inc is None or getattr(inc, "empty", True):
            _sleep(pause)
            continue

        rows: list[dict] = []
        for col in list(inc.columns)[:years]:
            year = getattr(col, "year", None)
            if year is None:
                continue
            revenue = _pick(inc, _REVENUE, col)
            op = _pick(inc, _OPINCOME, col)
            net = _pick(inc, _NETINCOME, col)
            equity = _pick(bal, _EQUITY, col)
            liab = _pick(bal, _LIABILITIES, col)

            roe = net / equity * 100 if net is not None and equity else None
            debt = liab / equity * 100 if liab is not None and equity else None
            margin = op / revenue * 100 if op is not None and revenue else None
            if roe is None and debt is None and margin is None:
                continue
            rows.append({
                "year": int(year),
                "roe": None if roe is None else round(roe, 2),
                "debt_ratio": None if debt is None else round(debt, 2),
                "op_margin": None if margin is None else round(margin, 2),
            })

        if rows:
            out[sym] = rows
        if n % 20 == 0:
            print(f"    · {n}/{len(symbols)}종목 연간 재무")
        _sleep(pause)
    return out
