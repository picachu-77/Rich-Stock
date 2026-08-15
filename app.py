"""
국내주식 대시보드 (개인용).

실행 방법:
    .venv\\Scripts\\streamlit.exe run app.py

그러면 웹브라우저가 자동으로 열립니다. (주소는 http://localhost:8501)
종료하려면 명령창에서 Ctrl+C 를 누르세요.

이 화면은 인터넷에서 데이터를 새로 받지 않습니다.
수집기가 Neon 창고에 쌓아둔 데이터만 읽어서 보여주고, 수익률도
쌓여 있는 과거 종가로 직접 계산합니다.
"""

from __future__ import annotations

import warnings

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.db import get_conn
from src.ui_korean import apply_korean_ui
from src.ui_style import apply_style, mobile_sidebar_button

# pandas 가 psycopg2 연결을 쓸 때 내는 안내 경고를 숨깁니다.
# (동작에는 문제가 없고, 화면에 노란 경고만 뜨는 것을 막기 위한 것입니다)
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)

# ── 화면 기본 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="국내주식 대시보드",
    page_icon="📈",
    layout="wide",
    # 휴대폰에서는 사이드바가 자동으로 접혀서 본문이 넓게 보입니다.
    initial_sidebar_state="auto",
    menu_items={},  # 영어로 뜨는 기본 메뉴 항목을 비웁니다
)

# 화면 디자인(글자·색·간격·휴대폰 대응)을 적용합니다. → src/ui_style.py
apply_style()

# Streamlit 이 영어로 그리는 표 메뉴 등을 한글로 바꿉니다.
apply_korean_ui()

# 휴대폰에서 화면 아래에 '☰ 필터' 버튼을 띄웁니다.
mobile_sidebar_button()

PERIODS = {
    "1개월": "1 month",
    "3개월": "3 months",
    "6개월": "6 months",
    "1년": "1 year",
    "3년": "3 years",
}
RETURN_COLS = [f"수익률 {label}(%)" for label in PERIODS]


# ── 데이터 읽기 (10분간 결과를 재사용해서 빠르게) ──────────────
@st.cache_data(ttl=600, show_spinner="데이터를 불러오는 중...")
def load_overview() -> pd.DataFrame:
    """
    전 종목의 최신 시세 + 기간별 수익률을 한 번에 계산해서 가져옵니다.

    수익률 계산 방식:
      (최근 종가 ÷ N개월 전 종가 - 1) × 100
      N개월 전이 휴장일이면, 그 이전 가장 가까운 거래일 종가를 씁니다.
    """
    lateral_sql = "\n".join(
        f"""
        LEFT JOIN LATERAL (
            SELECT p.close
              FROM daily_price p
             WHERE p.code = c.code
               AND p.trade_date <= c.trade_date - INTERVAL '{interval}'
             ORDER BY p.trade_date DESC
             LIMIT 1
        ) AS r{i} ON TRUE"""
        for i, interval in enumerate(PERIODS.values())
    )
    select_returns = ", ".join(f"r{i}.close AS past{i}" for i in range(len(PERIODS)))

    sql = f"""
    WITH bound AS (
        SELECT max(trade_date) AS last_d FROM daily_price
    ),
    recent AS (
        SELECT p.*
          FROM daily_price p, bound b
         WHERE p.trade_date >= b.last_d - INTERVAL '30 days'
    ),
    cur AS (
        SELECT DISTINCT ON (code)
               code, trade_date, close, change_pct, volume, market_cap,
               per, pbr, eps, bps, div_yield
          FROM recent
         ORDER BY code, trade_date DESC
    )
    SELECT t.code, t.name, t.market, t.kind, t.is_active,
           c.trade_date, c.close, c.change_pct, c.volume, c.market_cap,
           c.per, c.pbr, c.eps, c.bps, c.div_yield,
           f.roe, f.debt_ratio, f.op_margin, f.payout_ratio,
           f.fiscal_year, f.fiscal_quarter,
           {select_returns}
      FROM cur c
      JOIN ticker t ON t.code = c.code
      -- 재무지표는 '있으면 붙이고 없으면 빈칸'(LEFT JOIN)으로 가져옵니다.
      -- 그래야 재무제표가 없는 ETF 도 목록에서 사라지지 않습니다.
      -- 종목별로 가장 최근 분기 한 줄만 가져옵니다.
      LEFT JOIN LATERAL (
          SELECT fi.roe, fi.debt_ratio, fi.op_margin, fi.payout_ratio,
                 fi.fiscal_year, fi.fiscal_quarter
            FROM financial fi
           WHERE fi.code = c.code
           ORDER BY fi.fiscal_year DESC, fi.fiscal_quarter DESC
           LIMIT 1
      ) AS f ON TRUE
      {lateral_sql}
     WHERE t.is_active = TRUE;
    """

    with get_conn() as conn:
        df = pd.read_sql(sql, conn)

    if df.empty:
        return df

    # 수익률 계산
    for i, label in enumerate(PERIODS):
        past = pd.to_numeric(df[f"past{i}"], errors="coerce")
        cur = pd.to_numeric(df["close"], errors="coerce")
        df[f"수익률 {label}(%)"] = ((cur / past - 1) * 100).round(2)
        df.drop(columns=[f"past{i}"], inplace=True)

    df["종류"] = df["kind"].map({"STOCK": "주식", "ETF": "ETF"}).fillna(df["kind"])
    df["시장"] = df["market"]
    df["시가총액(억)"] = (
        pd.to_numeric(df["market_cap"], errors="coerce") / 100_000_000
    ).round(0)
    df["등락률(%)"] = pd.to_numeric(df["change_pct"], errors="coerce").round(2)
    df["종가"] = pd.to_numeric(df["close"], errors="coerce")
    df["거래량"] = pd.to_numeric(df["volume"], errors="coerce")
    df.rename(columns={"code": "종목코드", "name": "종목명"}, inplace=True)

    # ── 투자지표 (거래소 제공) ──
    df["PER"] = pd.to_numeric(df["per"], errors="coerce").round(2)
    df["PBR"] = pd.to_numeric(df["pbr"], errors="coerce").round(2)
    df["EPS(원)"] = pd.to_numeric(df["eps"], errors="coerce")
    df["BPS(원)"] = pd.to_numeric(df["bps"], errors="coerce")
    df["배당수익률(%)"] = pd.to_numeric(df["div_yield"], errors="coerce").round(2)

    # ── 재무지표 (DART 제공) ──
    df["ROE(%)"] = pd.to_numeric(df["roe"], errors="coerce").round(2)
    df["부채비율(%)"] = pd.to_numeric(df["debt_ratio"], errors="coerce").round(2)
    df["영업이익률(%)"] = pd.to_numeric(df["op_margin"], errors="coerce").round(2)
    df["배당성향(%)"] = pd.to_numeric(df["payout_ratio"], errors="coerce").round(2)

    # 재무지표가 어느 시점 것인지 함께 표시합니다 (예: 2025년 사업(연간))
    q_name = {1: "1분기", 2: "반기", 3: "3분기", 4: "연간"}
    df["재무 기준"] = [
        f"{int(y)}년 {q_name.get(int(q), q)}" if pd.notna(y) and pd.notna(q) else None
        for y, q in zip(df["fiscal_year"], df["fiscal_quarter"])
    ]

    # ★ 빈 값이 화면에 'None' 이라는 글자로 찍히지 않게 하는 처리 ★
    # 파이썬의 '숫자 아님(NaN)' 을 그대로 두면 Streamlit 이 None 이라고 적습니다.
    # 아래처럼 '값 없음을 표현할 수 있는 숫자형'으로 바꾸면 깔끔한 빈칸이 됩니다.
    for col in ["종가", "거래량", "시가총액(억)", "EPS(원)", "BPS(원)"]:
        df[col] = df[col].astype("Float64").round(0).astype("Int64")
    for col in (
        ["등락률(%)", "PER", "PBR", "배당수익률(%)",
         "ROE(%)", "부채비율(%)", "영업이익률(%)", "배당성향(%)"]
        + RETURN_COLS
    ):
        df[col] = df[col].astype("Float64")

    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_history(code: str) -> pd.DataFrame:
    """한 종목의 전체 일별 종가를 가져옵니다."""
    sql = """
        SELECT trade_date, close, change_pct, volume, market_cap
          FROM daily_price
         WHERE code = %(code)s
         ORDER BY trade_date;
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params={"code": code})
    if not df.empty:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_financials(code: str) -> pd.DataFrame:
    """
    한 종목의 분기별 재무지표를 오래된 것부터 가져옵니다.
    재무 데이터가 없으면 빈 표를 돌려주며, 화면은 그 부분만 감춥니다.
    """
    sql = """
        SELECT fiscal_year, fiscal_quarter,
               roe, debt_ratio, op_margin, payout_ratio,
               revenue, operating_profit, net_income,
               total_equity, total_liabilities, total_assets
          FROM financial
         WHERE code = %(code)s
         ORDER BY fiscal_year, fiscal_quarter;
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn, params={"code": code})
    except Exception:
        # 재무지표 쪽에 문제가 생겨도 시세 화면은 계속 동작해야 합니다.
        return pd.DataFrame()

    if df.empty:
        return df

    q_name = {1: "1분기", 2: "반기", 3: "3분기", 4: "연간"}
    df["기간"] = [
        f"{int(y)} {q_name.get(int(q), q)}"
        for y, q in zip(df["fiscal_year"], df["fiscal_quarter"])
    ]
    for c in ["roe", "debt_ratio", "op_margin", "payout_ratio"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_meta() -> dict:
    """창고 현황 요약."""
    from src.store import summary

    with get_conn() as conn:
        return summary(conn)


def _num(value, unit: str = "", digits: int = 0) -> str:
    """숫자를 화면에 보기 좋게 바꿉니다. 값이 없으면 '—' 로 표시합니다."""
    if pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}{unit}"


def make_stock_cards(table: pd.DataFrame, limit: int = 40) -> str:
    """
    휴대폰용 '종목 카드' 목록을 만듭니다.

    왜 필요한가요?
      표는 열이 18개라서 휴대폰에서 옆으로 계속 밀어야 하고,
      밀다 보면 종목명이 화면에서 사라져 어느 줄인지 알 수 없게 됩니다.
      카드 한 장에 중요한 정보만 담으면 옆으로 밀 필요가 없어집니다.
    """
    cards = []
    for _, r in table.head(limit).iterrows():
        chg = r["등락률(%)"]
        cls = "" if pd.isna(chg) else ("up" if float(chg) >= 0 else "down")
        chg_txt = "—" if pd.isna(chg) else f"{float(chg):+.2f}%"

        ret1y = r.get("수익률 1년(%)")
        ret_cls = "" if pd.isna(ret1y) else ("up" if float(ret1y) >= 0 else "down")
        ret_txt = "—" if pd.isna(ret1y) else f"{float(ret1y):+.1f}%"

        cards.append(
            f"""
            <div class="stock-card">
              <div class="sc-top">
                <div><span class="sc-name">{r['종목명']}</span>
                     <span class="sc-code">{r['종목코드']}</span></div>
                <div style="text-align:right">
                  <div class="sc-price">{_num(r['종가'], '원')}</div>
                  <div class="sc-chg {cls}">{chg_txt}</div>
                </div>
              </div>
              <div class="sc-tags">
                <span class="sc-tag">{r['시장']}</span>
                <span class="sc-tag">{r['종류']}</span>
                <span class="sc-tag">시총 {_num(r['시가총액(억)'], '억')}</span>
              </div>
              <div class="sc-grid">
                <div>PER <b>{_num(r['PER'], '', 2)}</b></div>
                <div>PBR <b>{_num(r['PBR'], '', 2)}</b></div>
                <div>ROE <b>{_num(r['ROE(%)'], '%', 1)}</b></div>
                <div>배당 <b>{_num(r['배당수익률(%)'], '%', 2)}</b></div>
                <div>부채비율 <b>{_num(r['부채비율(%)'], '%', 0)}</b></div>
                <div>1년 수익률 <b class="{ret_cls}">{ret_txt}</b></div>
              </div>
            </div>
            """
        )
    return "".join(cards)


def color_updown(value) -> str:
    """표에서 오른 숫자는 빨강, 내린 숫자는 파랑으로 칠합니다 (국내 증시 관행)."""
    if pd.isna(value):
        return ""
    return "color:#d92d20;font-weight:600" if float(value) > 0 else (
        "color:#1570ef;font-weight:600" if float(value) < 0 else ""
    )


def calc_period_returns(hist: pd.DataFrame) -> dict[str, float | None]:
    """
    쌓여 있는 과거 종가로 기간별 수익률을 직접 계산합니다.
    (기준일로부터 정확히 N개월 전 이하의 가장 최근 거래일 종가와 비교)
    """
    if hist.empty:
        return {label: None for label in PERIODS}

    hist = hist.dropna(subset=["close"]).sort_values("trade_date")
    last_row = hist.iloc[-1]
    last_date = last_row["trade_date"]
    last_close = float(last_row["close"])

    months = {"1개월": 1, "3개월": 3, "6개월": 6, "1년": 12, "3년": 36}
    out: dict[str, float | None] = {}
    for label, m in months.items():
        cutoff = last_date - pd.DateOffset(months=m)
        past = hist[hist["trade_date"] <= cutoff]
        if past.empty:
            out[label] = None
        else:
            past_close = float(past.iloc[-1]["close"])
            out[label] = round((last_close / past_close - 1) * 100, 2) if past_close else None
    return out


# ── 본문 ─────────────────────────────────────────────────────
st.title("📈 국내주식 대시보드")

# 첫 화면이 설명글로 꽉 차지 않도록, 자세한 사용법은 접어둡니다.
with st.expander("ⓘ 사용법 (처음이신가요?)", expanded=False):
    st.markdown(
        "1. **필터**로 원하는 조건을 겁니다. "
        "컴퓨터는 화면 왼쪽, 휴대폰은 화면 아래 **`☰ 필터`** 버튼을 누르세요.\n"
        "2. **📋 종목 목록** 탭에서 종목을 고릅니다. "
        "(컴퓨터는 표에서 클릭, 휴대폰은 목록 아래 **종목 선택**에서 고르기)\n"
        "3. **📊 차트** 탭에서 주가 흐름을, **🏦 재무** 탭에서 회사 상태를 봅니다.\n\n"
        "숫자 용어가 어렵다면 왼쪽 메뉴의 **📖 용어사전**을 참고하세요."
    )

try:
    meta = load_meta()
except Exception as exc:  # noqa: BLE001
    st.error("데이터베이스에 접속하지 못했습니다.")
    st.code(str(exc))
    st.info(
        "확인할 점\n\n"
        "1. 내 컴퓨터에서 실행 중이라면 `.env` 파일에 DATABASE_URL 이 들어 있는지\n"
        "2. Streamlit Cloud 에서 실행 중이라면 Settings > Secrets 에 등록했는지\n"
        "3. 표가 아직 없다면 `python -m src.create_tables` 를 먼저 실행"
    )
    st.stop()

if not meta["price_rows"]:
    st.warning(
        "아직 시세 데이터가 없습니다.\n\n"
        "명령창에서 아래를 실행해 과거 데이터를 채운 뒤 다시 열어주세요.\n\n"
        "`.venv\\Scripts\\python.exe -m src.backfill`"
    )
    st.stop()

c1, c2 = st.columns(2)
c1.metric("등록 종목", f"{meta['ticker_active']:,}개")
c2.metric("최신 기준일", str(meta["last_date"]))

df = load_overview()
if df.empty:
    st.warning("최근 30일 내 시세가 없습니다. 수집기를 다시 실행해 주세요.")
    st.stop()

# ── 왼쪽 사이드바: 검색 및 필터 ────────────────────────────────
# 필터가 많으면 화면이 길어져 찾기 어려우므로, 주제별로 '접이식 카드'에 넣었습니다.
# 자주 쓰는 검색과 정렬은 항상 보이게 두고, 나머지는 접어둡니다.
#
# 각 입력칸의 key= 는 '이 값을 부르는 이름표'입니다.
# 아래쪽 '필터 초기화' 버튼이 이 이름표들을 지워서 처음 상태로 되돌립니다.
FILTER_KEYS = [
    "f_kw", "f_kinds", "f_markets", "f_price", "f_cap", "f_vol", "f_chg",
    "f_retp", "f_ret", "f_per", "f_roe", "f_debt", "f_fin", "f_sort",
]

with st.sidebar:
    st.header("🔎 검색 · 필터")

    keyword = st.text_input(
        "종목명 · 종목코드 검색",
        placeholder="예: 삼성, KODEX, 005930",
        key="f_kw",
        help="여러 단어를 띄어쓰기로 넣으면 그중 하나라도 맞는 종목을 찾습니다.",
    )

    # 정렬은 가장 자주 바꾸는 항목이라 접지 않고 항상 보이게 둡니다.
    # '무엇을 크게/작게 볼지'를 이름으로 고르게 했습니다.
    SORT_PRESETS: dict[str, tuple[str, bool]] = {
        "시가총액 큰 순": ("시가총액(억)", False),
        "등락률 높은 순": ("등락률(%)", False),
        "등락률 낮은 순": ("등락률(%)", True),
        "거래량 많은 순": ("거래량", False),
        "PER 낮은 순 (저평가)": ("PER", True),
        "PBR 낮은 순 (저평가)": ("PBR", True),
        "배당수익률 높은 순": ("배당수익률(%)", False),
        "ROE 높은 순 (돈 잘 버는)": ("ROE(%)", False),
        "부채비율 낮은 순 (안전한)": ("부채비율(%)", True),
        "영업이익률 높은 순": ("영업이익률(%)", False),
        **{f"수익률 {p} 높은 순": (f"수익률 {p}(%)", False) for p in PERIODS},
        **{f"수익률 {p} 낮은 순": (f"수익률 {p}(%)", True) for p in PERIODS},
    }
    sort_label = st.selectbox(
        "↕️ 정렬 기준", list(SORT_PRESETS.keys()), index=0, key="f_sort"
    )
    sort_col, ascending = SORT_PRESETS[sort_label]

    st.caption("아래 항목을 눌러 펼치면 조건을 더 자세히 걸 수 있습니다.")

    # ── 접이식 카드 ①: 종류 · 시장 ──
    with st.expander("🏷️ 종류 · 시장", expanded=False):
        kinds = st.multiselect(
            "종류", ["주식", "ETF"], default=["주식", "ETF"], key="f_kinds"
        )
        markets = st.multiselect(
            "시장", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"], key="f_markets"
        )

    # ── 접이식 카드 ②: 가격 · 규모 · 거래량 ──
    with st.expander("💰 가격 · 규모 · 거래량", expanded=False):
        price_min, price_max = st.slider(
            "주가 범위 (원)",
            min_value=0, max_value=1_000_000, value=(0, 1_000_000), step=1_000,
            key="f_price",
            help="양쪽 끝에 두면 제한 없음",
        )
        min_cap = st.number_input(
            "최소 시가총액 (억원)",
            min_value=0, value=0, step=100, key="f_cap",
            help="0 이면 제한 없음. ETF 는 거래소가 시가총액을 주지 않아 빈칸이며, "
                 "이 값을 1 이상으로 두면 ETF 는 목록에서 빠집니다.",
        )
        min_volume = st.number_input(
            "최소 거래량 (주)",
            min_value=0, value=0, step=1_000, key="f_vol",
            help="거래가 거의 없는 종목을 걸러낼 때 사용하세요. 0 이면 제한 없음.",
        )
        chg_min, chg_max = st.slider(
            "등락률 범위 (%)",
            min_value=-30.0, max_value=30.0, value=(-30.0, 30.0), step=0.5,
            key="f_chg",
            help="양쪽 끝에 두면 제한 없음",
        )

    # ── 접이식 카드 ③: 수익률 ──
    with st.expander("📈 수익률", expanded=False):
        ret_period = st.selectbox(
            "기준 기간",
            ["사용 안 함"] + list(PERIODS.keys()), index=0, key="f_retp",
            help="예: '1년' 을 고르고 최소값을 20 으로 두면, "
                 "1년 수익률이 20% 이상인 종목만 남습니다.",
        )
        ret_min, ret_max = st.slider(
            "수익률 범위 (%)",
            min_value=-100.0, max_value=300.0, value=(-100.0, 300.0), step=5.0,
            key="f_ret",
            disabled=(ret_period == "사용 안 함"),
        )

    # ── 접이식 카드 ④: 재무지표 ──
    with st.expander("🏦 재무지표", expanded=False):
        st.caption("DART 전자공시 기준. ETF 는 재무제표가 없어 해당 없음.")
        per_max = st.number_input(
            "PER 최대 (이하만 보기)", min_value=0.0, value=0.0, step=1.0, key="f_per",
            help="0 이면 제한 없음. 예: 10 을 넣으면 PER 10 이하인 저평가 종목만.",
        )
        roe_min = st.number_input(
            "ROE 최소 (%, 이상만 보기)", value=0.0, step=1.0, key="f_roe",
            help="0 이면 제한 없음. 예: 15 를 넣으면 ROE 15% 이상인 알짜 회사만.",
        )
        debt_max = st.number_input(
            "부채비율 최대 (%, 이하만 보기)",
            min_value=0.0, value=0.0, step=10.0, key="f_debt",
            help="0 이면 제한 없음. 예: 100 을 넣으면 빚이 자기 돈보다 적은 회사만.",
        )
        only_with_fin = st.checkbox(
            "재무지표가 있는 종목만 보기", value=False, key="f_fin",
            help="켜면 ETF 와 재무제표가 없는 종목이 목록에서 빠집니다.",
        )

    # 지금 몇 개의 조건이 걸려 있는지 알려줍니다.
    # (접어두면 안 보이기 때문에, 조건이 걸린 줄 모르고 헤매는 일을 막아줍니다)
    active = sum([
        bool(keyword.strip()),
        set(kinds) != {"주식", "ETF"},
        set(markets) != {"KOSPI", "KOSDAQ"},
        (price_min, price_max) != (0, 1_000_000),
        min_cap > 0,
        min_volume > 0,
        (chg_min, chg_max) != (-30.0, 30.0),
        ret_period != "사용 안 함",
        per_max > 0,
        roe_min != 0,
        debt_max > 0,
        only_with_fin,
    ])
    if active:
        st.success(f"조건 {active}개 적용 중")
    else:
        st.caption("조건 없음 — 전체 종목을 보고 있습니다.")

    st.divider()
    b1, b2 = st.columns(2)
    if b1.button("↩️ 필터 초기화", width="stretch", help="모든 조건을 처음 상태로"):
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)
        st.rerun()
    if b2.button("🔄 새로 읽기", width="stretch", help="최신 데이터를 다시 불러옵니다"):
        st.cache_data.clear()
        st.rerun()

# ── 필터 적용 ────────────────────────────────────────────────
view = df.copy()

if keyword.strip():
    words = [w for w in keyword.strip().split() if w]
    hit = pd.Series(False, index=view.index)
    for w in words:
        hit |= view["종목명"].str.contains(w, case=False, na=False)
        hit |= view["종목코드"].str.contains(w, case=False, na=False)
    view = view[hit]

if kinds:
    view = view[view["종류"].isin(kinds)]
if markets:
    view = view[view["시장"].isin(markets)]

# 주가 범위 (양쪽 끝이면 제한 없음)
if price_min > 0 or price_max < 1_000_000:
    close = view["종가"].astype("Float64")
    view = view[(close >= price_min) & (close <= price_max)]

if min_cap > 0:
    view = view[view["시가총액(억)"].astype("Float64").fillna(-1) >= min_cap]

if min_volume > 0:
    view = view[view["거래량"].astype("Float64").fillna(-1) >= min_volume]

if chg_min > -30.0 or chg_max < 30.0:
    chg = view["등락률(%)"].astype("Float64")
    view = view[(chg >= chg_min) & (chg <= chg_max)]

if ret_period != "사용 안 함":
    col = f"수익률 {ret_period}(%)"
    ret = view[col].astype("Float64")
    view = view[(ret >= ret_min) & (ret <= ret_max)]

# ── 재무지표 필터 ──
# 값이 없는 종목(ETF 등)은 조건을 걸면 자연스럽게 빠집니다.
if per_max > 0:
    view = view[view["PER"].astype("Float64").notna() & (view["PER"] <= per_max)]
if roe_min != 0:
    view = view[view["ROE(%)"].astype("Float64").notna() & (view["ROE(%)"] >= roe_min)]
if debt_max > 0:
    view = view[
        view["부채비율(%)"].astype("Float64").notna() & (view["부채비율(%)"] <= debt_max)
    ]
if only_with_fin:
    view = view[view["ROE(%)"].notna() | view["부채비율(%)"].notna()]

view = view.sort_values(sort_col, ascending=ascending, na_position="last")

display_cols = (
    ["종목코드", "종목명", "시장", "종류", "종가", "등락률(%)", "거래량", "시가총액(억)"]
    + ["PER", "PBR", "배당수익률(%)"]
    + ["ROE(%)", "부채비율(%)", "영업이익률(%)"]
    + RETURN_COLS
)
table = view[display_cols].reset_index(drop=True)

if table.empty:
    st.warning("조건에 맞는 종목이 없습니다. 왼쪽 필터를 조금 넓혀 보세요.")
    st.stop()

# ── 화면을 세 칸(탭)으로 나눕니다 ─────────────────────────────
# 예전에는 목록·차트·재무가 위아래로 길게 이어져서 휴대폰에서 한참 스크롤해야
# 했습니다. 탭으로 나누면 한 번 눌러 바로 이동할 수 있습니다.
tab_list, tab_chart, tab_fin = st.tabs(["📋 종목 목록", "📊 차트", "🏦 재무"])

with tab_list:
    st.subheader(f"종목 목록  ({len(table):,}개)")

    # '종목 선택' 칸의 자리를 목록 위에 미리 잡아둡니다.
    # (휴대폰에서 카드 40장을 지나 맨 아래까지 내려가지 않아도 되도록,
    #  내용은 나중에 채우고 위치만 여기로 정해두는 방식입니다)
    sel_slot = st.container()

    # ── 휴대폰: 카드 목록 (옆으로 밀 필요 없음) ──
    # st.container(key="only_mobile") 안에 넣으면 휴대폰에서만 보입니다. → src/ui_style.py
    with st.container(key="only_mobile"):
        st.markdown(make_stock_cards(table), unsafe_allow_html=True)
        if len(table) > 40:
            st.caption(
                f"조건에 맞는 {len(table):,}개 중 앞의 40개만 카드로 보여줍니다. "
                "왼쪽 필터로 범위를 좁히거나 정렬 기준을 바꿔 보세요."
            )

    # ── 컴퓨터: 지금까지의 표 그대로 ──
    with st.container(key="only_desktop"):
        st.caption(
            "표 왼쪽 끝의 네모(☐)를 누르거나, 표 아래의 **종목 선택**에서 고르면 "
            "차트와 재무 탭에 그 종목이 나타납니다. "
            "열 제목을 누르면 그 열 기준으로 정렬됩니다."
        )
        event = st.dataframe(
            # 오른 값은 빨강, 내린 값은 파랑으로 칠해 한눈에 보이게 합니다.
            table.style.map(color_updown, subset=["등락률(%)"] + RETURN_COLS),
            width="stretch",
            hide_index=True,
            height=400,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "종목코드": st.column_config.TextColumn("종목코드", width="small"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "종가": st.column_config.NumberColumn("종가(원)", format="localized"),
                "거래량": st.column_config.NumberColumn("거래량(주)", format="localized"),
                "시가총액(억)": st.column_config.NumberColumn(
                    "시가총액(억원)",
                    format="localized",
                    help="ETF 는 거래소가 시가총액을 제공하지 않아 빈칸입니다.",
                ),
                "등락률(%)": st.column_config.NumberColumn("등락률(%)", format="localized"),
                "PER": st.column_config.NumberColumn(
                    "PER", format="localized",
                    help="주가수익비율 = 주가 ÷ 주당순이익. 낮을수록 이익 대비 주가가 쌉니다. "
                         "적자 기업은 계산이 안 되어 빈칸입니다.",
                ),
                "PBR": st.column_config.NumberColumn(
                    "PBR", format="localized",
                    help="주가순자산비율 = 주가 ÷ 주당순자산. 1보다 낮으면 장부가치보다 쌉니다.",
                ),
                "배당수익률(%)": st.column_config.NumberColumn(
                    "배당수익률(%)", format="localized",
                    help="1년 배당금 ÷ 주가 × 100. 은행 이자율과 비교해 보세요.",
                ),
                "ROE(%)": st.column_config.NumberColumn(
                    "ROE(%)", format="localized",
                    help="자기자본이익률 = 당기순이익 ÷ 자본총계 × 100. "
                         "높을수록 내 돈으로 돈을 잘 버는 회사입니다. (DART 최신 분기 기준)",
                ),
                "부채비율(%)": st.column_config.NumberColumn(
                    "부채비율(%)", format="localized",
                    help="부채총계 ÷ 자본총계 × 100. 낮을수록 빚이 적은 회사입니다. "
                         "100% 면 자기 돈과 빌린 돈이 같다는 뜻입니다.",
                ),
                "영업이익률(%)": st.column_config.NumberColumn(
                    "영업이익률(%)", format="localized",
                    help="영업이익 ÷ 매출액 × 100. 높을수록 장사를 잘하는 회사입니다.",
                ),
                **{
                    c: st.column_config.NumberColumn(c, format="localized")
                    for c in RETURN_COLS
                },
            },
        )

    # ── 어떤 종목을 볼지 정하기 ───────────────────────────────
    # 방법 두 가지를 모두 지원합니다.
    #   (1) 표에서 줄을 클릭(컴퓨터)   (2) 아래 '종목 선택' 목록에서 고르기
    selected_rows = event.selection.rows if event and event.selection else []
    clicked_code = table.iloc[selected_rows[0]]["종목코드"] if selected_rows else None

    # 표 클릭은 '방금 새로 클릭했을 때만' 반영합니다.
    # (이렇게 하지 않으면 아래 선택창으로 바꿔도 표 클릭이 계속 덮어씁니다)
    if clicked_code and clicked_code != st.session_state.get("_last_clicked"):
        st.session_state["_last_clicked"] = clicked_code
        st.session_state["sel_code"] = clicked_code

    codes = table["종목코드"].tolist()
    name_of = dict(zip(table["종목코드"], table["종목명"]))

    current = st.session_state.get("sel_code")
    default_idx = codes.index(current) if current in codes else 0

    # 위에서 자리를 잡아둔 곳(sel_slot)에 선택 칸을 채워 넣습니다.
    with sel_slot:
        code = st.selectbox(
            "🔎 종목 선택 — 고른 종목이 📊 차트 · 🏦 재무 탭에 나타납니다",
            codes,
            index=default_idx,
            format_func=lambda c: f"{name_of.get(c, c)}  ({c})",
            help="이름 일부를 입력하면 바로 찾을 수 있습니다.",
        )
    st.session_state["sel_code"] = code

row = table[table["종목코드"] == code].iloc[0]
name = row["종목명"]

# 고른 종목이 무엇인지 탭마다 위에 다시 보여줍니다 (탭을 옮겨도 헷갈리지 않게).
detail_bits = [str(row["시장"]), str(row["종류"])]
if pd.notna(row["종가"]):
    detail_bits.append(f"종가 {int(row['종가']):,}원")
if pd.notna(row["등락률(%)"]):
    detail_bits.append(f"등락률 {float(row['등락률(%)']):+.2f}%")
headline = f"### {name}  `{code}`\n\n" + "  ·  ".join(detail_bits)

hist = load_history(code)

# ── 차트 탭 ──────────────────────────────────────────────────
with tab_chart:
    st.markdown(headline)

    if hist.empty:
        st.warning("이 종목의 과거 시세가 아직 없습니다.")
        st.stop()

    # 기간별 수익률 — 데이터베이스에 쌓인 종가로 직접 계산
    returns = calc_period_returns(hist)
    cols = st.columns(len(PERIODS))
    for col, (label, value) in zip(cols, returns.items()):
        if value is None:
            col.metric(label, "—", help="해당 기간만큼의 과거 데이터가 아직 없습니다")
        else:
            col.metric(label, f"{value:+.2f}%")

    range_label = st.radio(
        "차트 기간",
        ["1개월", "3개월", "6개월", "1년", "3년", "전체"],
        index=3,
        horizontal=True,
    )

    months_map = {"1개월": 1, "3개월": 3, "6개월": 6, "1년": 12, "3년": 36}
    plot_df = hist
    if range_label in months_map:
        cutoff = hist["trade_date"].max() - pd.DateOffset(months=months_map[range_label])
        plot_df = hist[hist["trade_date"] >= cutoff]

    if plot_df.empty:
        st.info("이 기간에는 아직 데이터가 없습니다. 더 긴 기간을 골라 보세요.")
    else:
        first_close = float(plot_df["close"].iloc[0])
        last_close = float(plot_df["close"].iloc[-1])
        period_ret = (last_close / first_close - 1) * 100 if first_close else 0.0
        # 오르면 빨강, 내리면 파랑 (국내 증시 표기 관행)
        line_color = "#d92d20" if period_ret >= 0 else "#1570ef"

        # 점이 몇 개 없으면 선이 안 보이므로 점도 함께 찍습니다.
        mode = "lines+markers" if len(plot_df) <= 40 else "lines"

        fig = go.Figure(
            go.Scatter(
                x=plot_df["trade_date"],
                y=plot_df["close"],
                mode=mode,
                line=dict(width=2, color=line_color),
                marker=dict(size=6, color=line_color),
                fill="tozeroy",
                fillcolor=("rgba(217,45,32,.08)" if period_ret >= 0
                           else "rgba(21,112,239,.08)"),
                hovertemplate="%{x|%Y-%m-%d}<br>종가 %{y:,.0f}원<extra></extra>",
            )
        )

        # 세로축은 0 부터가 아니라 실제 주가 범위에 맞춥니다 (변동이 잘 보이도록).
        lo, hi = float(plot_df["close"].min()), float(plot_df["close"].max())
        pad = max((hi - lo) * 0.10, max(hi * 0.02, 1))

        fig.update_yaxes(
            title_text=None,
            tickformat=",.0f",
            range=[max(lo - pad, 0), hi + pad],
            gridcolor="#eef2f7",
        )
        # 가로축은 날짜만 표시 (데이터가 적을 때 시:분:초가 뜨는 것을 막습니다)
        fig.update_xaxes(
            title_text=None, tickformat="%y.%m", hoverformat="%Y-%m-%d",
            gridcolor="#f5f7fa",
        )
        fig.update_layout(
            # 휴대폰에서 화면을 덜 차지하도록 430 → 340 으로 낮췄습니다.
            height=340,
            margin=dict(l=6, r=6, t=44, b=6),
            hovermode="x unified",
            showlegend=False,
            plot_bgcolor="white",
            title=dict(
                # 위쪽 '기간별 수익률' 과 헷갈리지 않게 표현을 구분합니다.
                # 이것은 '차트에 그려진 구간의 처음 → 끝' 변동입니다.
                text=(
                    f"차트 구간 변동  {period_ret:+.2f}%　"
                    f"({plot_df['trade_date'].min():%Y-%m-%d} ~ "
                    f"{plot_df['trade_date'].max():%Y-%m-%d}, 거래일 {len(plot_df)}일)"
                ),
                font=dict(size=13),
            ),
        )

        # displayModeBar=False : 차트 위에 뜨는 작은 도구막대를 없앱니다.
        # (휴대폰에서 손가락에 눌려 확대·저장이 잘못 실행되는 것을 막습니다)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # 데이터가 너무 적으면 왜 그런지 알려줍니다.
        if len(plot_df) < 5:
            st.warning(
                f"이 기간에 저장된 거래일이 {len(plot_df)}일뿐이라 그래프가 거의 "
                "비어 보입니다. 과거 데이터 수집이 아직 진행 중이기 때문입니다. "
                "수집이 끝나면 정상적으로 그려집니다."
            )

    with st.expander("시세 원본 데이터 보기 (최근 60일)"):
        recent = hist.sort_values("trade_date", ascending=False).head(60).copy()
        recent["날짜"] = recent["trade_date"].dt.strftime("%Y-%m-%d")
        recent["종가(원)"] = pd.to_numeric(recent["close"], errors="coerce").astype("Int64")
        recent["등락률(%)"] = pd.to_numeric(
            recent["change_pct"], errors="coerce"
        ).astype("Float64").round(2)
        recent["거래량(주)"] = pd.to_numeric(
            recent["volume"], errors="coerce"
        ).astype("Int64")
        # 시가총액은 원 단위 그대로 두면 자릿수가 너무 길어 억원으로 바꿉니다.
        recent["시가총액(억원)"] = (
            pd.to_numeric(recent["market_cap"], errors="coerce") / 100_000_000
        ).round(0).astype("Float64").astype("Int64")

        st.dataframe(
            recent[["날짜", "종가(원)", "등락률(%)", "거래량(주)", "시가총액(억원)"]]
            .style.map(color_updown, subset=["등락률(%)"]),
            width="stretch",
            hide_index=True,
            column_config={
                "종가(원)": st.column_config.NumberColumn(format="localized"),
                "등락률(%)": st.column_config.NumberColumn(format="localized"),
                "거래량(주)": st.column_config.NumberColumn(format="localized"),
                "시가총액(억원)": st.column_config.NumberColumn(
                    format="localized",
                    help="ETF 는 거래소가 시가총액을 제공하지 않아 빈칸입니다.",
                ),
            },
        )


# ── 재무 탭 (DART 전자공시) ──────────────────────────────────
# 이 부분은 시세와 완전히 분리되어 있습니다.
# 재무 데이터가 없거나 문제가 생겨도 차트 탭은 정상 동작합니다.
with tab_fin:
    st.markdown(headline)

    fin = load_financials(code)

    if fin.empty:
        st.info(
            "이 종목은 재무지표가 없습니다.\n\n"
            "ETF·리츠 등은 재무제표를 내지 않거나, 아직 수집되지 않았을 수 있습니다. "
            "수집은 `python -m src.financial_collect` 로 실행합니다."
        )
    else:
        latest = fin.iloc[-1]
        st.caption(f"가장 최근 기준: **{latest['기간']}** · 출처: DART 전자공시")

        m1, m2, m3, m4 = st.columns(4)

        def _show(col, label, value, suffix="%", help_text=None):
            if pd.isna(value):
                col.metric(label, "—", help=help_text)
            else:
                col.metric(label, f"{float(value):,.2f}{suffix}", help=help_text)

        _show(m1, "ROE", latest["roe"],
              help_text="당기순이익 ÷ 자본총계 × 100. 높을수록 돈을 잘 버는 회사")
        _show(m2, "부채비율", latest["debt_ratio"],
              help_text="부채총계 ÷ 자본총계 × 100. 낮을수록 빚이 적은 회사")
        _show(m3, "영업이익률", latest["op_margin"],
              help_text="영업이익 ÷ 매출액 × 100. 높을수록 장사를 잘하는 회사")
        _show(m4, "배당성향", latest["payout_ratio"],
              help_text="현금배당금총액 ÷ 당기순이익 × 100. 연간 보고서에만 있습니다")

        # 분기별 추이 차트
        metric_choice = st.radio(
            "추이로 볼 지표",
            ["ROE", "부채비율", "영업이익률", "배당성향"],
            index=0,
            horizontal=True,
        )
        col_map = {
            "ROE": ("roe", "#d92d20"),
            "부채비율": ("debt_ratio", "#7839ee"),
            "영업이익률": ("op_margin", "#0e9384"),
            "배당성향": ("payout_ratio", "#dc6803"),
        }
        col_name, color = col_map[metric_choice]
        series = fin[["기간", col_name]].dropna()

        if series.empty:
            st.info(f"{metric_choice} 데이터가 아직 없습니다.")
        else:
            fig_fin = go.Figure(
                go.Bar(
                    x=series["기간"],
                    y=series[col_name],
                    marker=dict(color=color),
                    hovertemplate="%{x}<br>" + metric_choice + " %{y:,.2f}%<extra></extra>",
                )
            )
            fig_fin.update_yaxes(
                title_text=f"{metric_choice} (%)", tickformat=",.1f", gridcolor="#eef2f7"
            )
            fig_fin.update_layout(
                height=300,
                margin=dict(l=6, r=6, t=30, b=6),
                showlegend=False,
                plot_bgcolor="white",
                title=dict(text=f"분기별 {metric_choice} 추이", font=dict(size=13)),
            )
            st.plotly_chart(fig_fin, width="stretch", config={"displayModeBar": False})

        st.caption(
            "⚠️ 분기 보고서는 그 기간만의 실적이라 연간(사업보고서)보다 값이 작게 나옵니다. "
            "같은 분기끼리(작년 3분기 vs 올해 3분기) 비교하시는 게 맞습니다."
        )

        with st.expander("재무제표 원본 금액 보기"):
            raw = fin.copy()
            for c, label in [
                ("revenue", "매출액(억원)"),
                ("operating_profit", "영업이익(억원)"),
                ("net_income", "당기순이익(억원)"),
                ("total_equity", "자본총계(억원)"),
                ("total_liabilities", "부채총계(억원)"),
                ("total_assets", "자산총계(억원)"),
            ]:
                raw[label] = (
                    pd.to_numeric(raw[c], errors="coerce") / 100_000_000
                ).round(0).astype("Float64").astype("Int64")
            show_cols = ["기간", "매출액(억원)", "영업이익(억원)", "당기순이익(억원)",
                         "자본총계(억원)", "부채총계(억원)", "자산총계(억원)"]
            st.dataframe(
                raw[show_cols].iloc[::-1],
                width="stretch",
                hide_index=True,
                column_config={
                    c: st.column_config.NumberColumn(format="localized")
                    for c in show_cols[1:]
                },
            )
