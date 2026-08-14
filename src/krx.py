"""
한국거래소(KRX) 데이터를 가져오는 담당 파일.

여기서 신경 쓴 점 3가지
  1) 한 번에 3년치를 몰아서 요청하지 않고, "하루치씩" 나눠서 요청합니다.
  2) 요청과 요청 사이에 잠깐 쉽니다 (거래소 서버에 부담을 주지 않기 위해).
  3) 요청이 실패하면 시간을 점점 늘려가며 최대 4번까지 다시 시도합니다.
"""

from __future__ import annotations

import random
import time
from datetime import date, datetime, timedelta

# ★ 순서 중요 ★
# .config 를 먼저 불러와야 .env 의 KRX_ID / KRX_PW 가 환경변수에 올라가고,
# 그 다음에 pykrx 가 그 값으로 거래소에 로그인할 수 있습니다.
from .config import MAX_RETRY, REQUEST_DELAY_SEC, get_krx_credentials

import pandas as pd
from pykrx import stock

MARKETS = ("KOSPI", "KOSDAQ")

_logged_in = False


def ensure_login() -> None:
    """
    한국거래소에 로그인합니다. (프로그램 실행 중 딱 한 번만 수행)

    거래소가 2025년부터 시세 조회에 회원 로그인을 요구하도록 바뀌어서
    이 단계가 반드시 필요합니다. 로그인에 실패하면 여기서 멈춥니다.
    """
    global _logged_in
    if _logged_in:
        return

    krx_id, _ = get_krx_credentials()

    from pykrx.website.comm import auth as krx_auth

    # pykrx 를 불러올 때 이미 로그인이 끝났으면 그대로 재사용합니다.
    existing = krx_auth.get_auth_session()
    if existing is not None and existing.is_valid():
        _logged_in = True
        return

    print(f"  한국거래소 로그인 중... (아이디: {krx_id})")
    session = krx_auth.build_krx_session()
    if session is None:
        raise RuntimeError(
            "[!] 한국거래소 로그인에 실패했습니다.\n"
            "    - .env 의 KRX_ID / KRX_PW 값이 정확한지 확인하세요.\n"
            "    - https://data.krx.co.kr 에 웹브라우저로 직접 로그인이 되는지\n"
            "      확인해 보세요 (비밀번호 변경 요구 화면이 뜨면 먼저 변경해야 합니다)."
        )
    krx_auth.set_auth_session(session)
    _logged_in = True
    print("  한국거래소 로그인 완료.")


# ── 공통 도구 ────────────────────────────────────────────────
def ymd(d: date) -> str:
    """날짜를 pykrx 가 이해하는 '20250814' 형태 글자로 바꿉니다."""
    return d.strftime("%Y%m%d")


def polite_sleep() -> None:
    """다음 요청까지 잠깐 쉽니다."""
    time.sleep(REQUEST_DELAY_SEC + random.uniform(0, 0.25))


def retry(func, *args, what: str = "요청", **kwargs):
    """
    func 를 실행하다 실패하면 다시 시도합니다.
    기다리는 시간은 1.5초 → 3초 → 6초 … 로 점점 늘어납니다(서버가 바쁠 때를 대비).
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == MAX_RETRY:
                break
            wait = 1.5 * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"      ! {what} 실패({attempt}/{MAX_RETRY}): {exc}")
            print(f"        {wait:.1f}초 후 다시 시도합니다...")
            time.sleep(wait)
    raise RuntimeError(f"{what} 을(를) {MAX_RETRY}번 시도했지만 모두 실패했습니다") from last_error


def _col(df: pd.DataFrame, *candidates: str):
    """
    표에서 원하는 칸을 찾습니다.
    pykrx 버전에 따라 칸 이름이 조금씩 달라서, 후보를 여러 개 두고 찾습니다.
    없으면 None 을 돌려줍니다.
    """
    for name in candidates:
        if name in df.columns:
            return df[name]
    return None


def _to_int(value):
    """숫자로 바꿉니다. 비어 있거나 이상한 값이면 None."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _to_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


# ── 종목 목록 가져오기 ────────────────────────────────────────
def fetch_ticker_master(on: date) -> list[dict]:
    """
    기준일(on) 시점의 전 종목 목록을 가져옵니다.
    일반주식(코스피/코스닥) + ETF 를 모두 합쳐서 돌려줍니다.

    돌려주는 값: [{code, name, market, kind}, ...]
    """
    ensure_login()
    day = ymd(on)
    result: list[dict] = []
    seen: set[str] = set()

    # 1) 일반주식 — 시장별로 나눠서 요청
    for market in MARKETS:
        codes = retry(
            stock.get_market_ticker_list, day, market=market,
            what=f"{market} 종목목록",
        )
        polite_sleep()
        print(f"    - {market} 일반주식 {len(codes)}종목")
        for code in codes:
            if code in seen:
                continue
            seen.add(code)
            try:
                name = stock.get_market_ticker_name(code)
            except Exception:
                name = code
            result.append(
                {"code": code, "name": str(name), "market": market, "kind": "STOCK"}
            )

    # 2) ETF — ETF 는 모두 유가증권시장(KOSPI)에 상장됩니다
    etf_codes = retry(stock.get_etf_ticker_list, day, what="ETF 종목목록")
    polite_sleep()
    print(f"    - ETF {len(etf_codes)}종목")
    for code in etf_codes:
        if code in seen:
            continue
        seen.add(code)
        try:
            name = stock.get_etf_ticker_name(code)
        except Exception:
            name = code
        result.append(
            {"code": code, "name": str(name), "market": "KOSPI", "kind": "ETF"}
        )

    return result


# ── 하루치 시세 가져오기 ──────────────────────────────────────
def fetch_stock_prices(on: date) -> list[tuple]:
    """
    특정 하루의 '일반주식 전 종목' 시세를 가져옵니다.
    시세표와 시가총액표를 각각 받아서 종목코드 기준으로 합칩니다.

    돌려주는 값: [(종목코드, 날짜, 종가, 등락률, 거래량, 시가총액), ...]
    휴장일이면 빈 목록을 돌려줍니다.
    """
    ensure_login()
    day = ymd(on)

    ohlcv = retry(stock.get_market_ohlcv, day, market="ALL", what=f"{day} 주식시세")
    polite_sleep()
    if ohlcv is None or ohlcv.empty:
        return []

    cap = retry(stock.get_market_cap, day, market="ALL", what=f"{day} 시가총액")
    polite_sleep()

    close = _col(ohlcv, "종가")
    change = _col(ohlcv, "등락률")
    volume = _col(ohlcv, "거래량")
    market_cap = _col(cap, "시가총액") if cap is not None and not cap.empty else None

    rows: list[tuple] = []
    for code in ohlcv.index:
        c = _to_int(close.get(code)) if close is not None else None
        # 종가가 0이거나 없으면 거래 자체가 없었던 날 → 저장하지 않음
        if not c:
            continue
        rows.append(
            (
                str(code),
                on,
                c,
                _to_float(change.get(code)) if change is not None else None,
                _to_int(volume.get(code)) if volume is not None else None,
                _to_int(market_cap.get(code)) if market_cap is not None else None,
            )
        )
    return rows


def fetch_fundamentals(on: date) -> list[tuple]:
    """
    특정 하루의 '일반주식 전 종목' 투자지표를 가져옵니다.
    (ETF 는 이 지표가 없습니다 — 거래소가 제공하지 않습니다)

    가져오는 값
      PER  주가수익비율   : 주가 ÷ 주당순이익
      PBR  주가순자산비율 : 주가 ÷ 주당순자산
      EPS  주당순이익 (원)
      BPS  주당순자산 (원)
      DIV  배당수익률 (%)
      DPS  주당배당금 (원)

    ★ 중요 ★
      적자 기업은 PER 이 0 으로 옵니다. 이를 그대로 저장하면
      'PER 낮은순' 정렬에서 적자 기업이 1등이 되는 엉뚱한 일이 생기므로,
      0 은 '계산 불가'로 보고 빈칸(None)으로 저장합니다.
      PBR 도 마찬가지입니다.
      반면 배당수익률(DIV)/주당배당금(DPS)의 0 은 '배당을 안 준다'는
      실제 정보이므로 0 그대로 저장합니다.

    돌려주는 값:
      [(종목코드, 날짜, PER, PBR, EPS, BPS, DIV, DPS), ...]
    """
    ensure_login()
    day = ymd(on)

    df = retry(
        stock.get_market_fundamental, day, market="ALL", what=f"{day} 투자지표"
    )
    polite_sleep()
    if df is None or df.empty:
        return []

    per = _col(df, "PER")
    pbr = _col(df, "PBR")
    eps = _col(df, "EPS")
    bps = _col(df, "BPS")
    div = _col(df, "DIV")
    dps = _col(df, "DPS")

    def _positive_or_none(series, code):
        """0 이하는 '계산 불가'로 보고 빈칸 처리합니다."""
        if series is None:
            return None
        value = _to_float(series.get(code))
        return value if value and value > 0 else None

    rows: list[tuple] = []
    for code in df.index:
        rows.append(
            (
                str(code),
                on,
                _positive_or_none(per, code),
                _positive_or_none(pbr, code),
                _to_int(eps.get(code)) if eps is not None else None,
                _to_int(bps.get(code)) if bps is not None else None,
                _to_float(div.get(code)) if div is not None else None,
                _to_int(dps.get(code)) if dps is not None else None,
            )
        )
    return rows


def fetch_etf_prices(on: date) -> list[tuple]:
    """
    특정 하루의 'ETF 전 종목' 시세를 가져옵니다.
    ETF 는 pykrx 버전에 따라 등락률/시가총액 칸이 없을 수 있는데,
    없으면 None 으로 두고 나중에 데이터베이스에서 직접 계산합니다.
    """
    ensure_login()
    day = ymd(on)

    df = retry(stock.get_etf_ohlcv_by_ticker, day, what=f"{day} ETF시세")
    polite_sleep()
    if df is None or df.empty:
        return []

    close = _col(df, "종가")
    change = _col(df, "등락률")
    volume = _col(df, "거래량")
    market_cap = _col(df, "시가총액", "순자산총액")

    rows: list[tuple] = []
    for code in df.index:
        c = _to_int(close.get(code)) if close is not None else None
        if not c:
            continue
        rows.append(
            (
                str(code),
                on,
                c,
                _to_float(change.get(code)) if change is not None else None,
                _to_int(volume.get(code)) if volume is not None else None,
                _to_int(market_cap.get(code)) if market_cap is not None else None,
            )
        )
    return rows


# ── 날짜 도구 ────────────────────────────────────────────────
def weekdays_between(start: date, end: date):
    """
    start 부터 end 까지의 '평일'을 하나씩 돌려줍니다.
    (토·일은 건너뜁니다. 명절 같은 휴장일은 실제로 요청해 보고 판단합니다)
    """
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 0=월 ... 4=금
            yield cur
        cur += timedelta(days=1)


def kst_today() -> date:
    """한국 시간 기준 오늘 날짜."""
    from datetime import timezone

    return (datetime.now(timezone.utc) + timedelta(hours=9)).date()
