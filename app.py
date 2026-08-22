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
from src.fin_trend import (
    QUARTER_NAME,
    QUARTER_SPAN,
    available_kinds,
    load_financials,
    profit_figure,
    revenue_figure,
    same_kind,
    summary_lines,
    yoy_figure,
)
from src.market_data import (
    PERIODS,
    RETURN_COLS,
    load_52w,
    load_overview,
    load_track_record,
)
from src.risk import FLAGS, add_flags, badges_html
from src.search import search
from src.ui_table import as_text, color_map, text_columns
from src.valuation import (
    BAND_METRICS,
    band_figure,
    band_html,
    band_stats,
    load_band_history,
    read_sentence,
)
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


# 재무 데이터를 읽는 load_financials() 는 src/fin_trend.py 로 옮겼습니다.
# 대시보드와 '종목 비교' 화면이 같은 함수를 쓰기 위해서입니다.


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


def w52_bar(r: pd.Series) -> str:
    """
    최근 1년 주가 범위에서 지금이 어디쯤인지 막대로 보여줍니다.

    왜 필요한가요?
      '많이 떨어졌으니 싸다'는 판단은 위험합니다. 지금 값이 1년 범위의
      어디쯤인지, 고점에서 얼마나 내려왔는지를 함께 봐야 판단이 됩니다.
    """
    pos = r.get("52주위치(%)")
    if pd.isna(pos):
        return ""
    pos = max(0.0, min(100.0, float(pos)))
    drop = r.get("고점대비(%)")
    drop_txt = "" if pd.isna(drop) else f"고점 대비 {float(drop):+.0f}%"
    return (
        "<div class='w52'>"
        f"<div class='w52-head'><span>52주 위치 {pos:.0f}%</span>"
        f"<span>{drop_txt}</span></div>"
        "<div class='w52-bar'>"
        f"<div class='w52-dot' style='left:{pos:.0f}%'></div></div>"
        f"<div class='w52-ends'><span>저 {_num(r.get('52주최저'), '원')}</span>"
        f"<span>고 {_num(r.get('52주최고'), '원')}</span></div>"
        "</div>"
    )


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
              {w52_bar(r)}
              <div class="sc-risk">{badges_html(r.get('위험신호'))}</div>
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
# (한 번 읽으면 되는 내용이라 접힌 상태가 기본입니다)
with st.expander("ⓘ 사용법 — 처음이신가요?", expanded=False):
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

# 등록 종목 수와 기준일은 매번 확인할 값이 아닙니다.
# 큰 카드 두 개로 두면 정작 봐야 할 종목 목록이 화면 아래로 밀려납니다.
st.caption(
    f"등록 종목 **{meta['ticker_active']:,}개**　·　"
    f"최신 기준일 **{meta['last_date']}**"
)

df = load_overview()
if df.empty:
    st.warning("최근 30일 내 시세가 없습니다. 수집기를 다시 실행해 주세요.")
    st.stop()

# ── 실적 이력과 52주 최고·최저를 붙입니다 ─────────────────────
# (위험 신호 판단과 '1년 범위 어디쯤인지' 표시에 씁니다)
track = load_track_record()
if not track.empty:
    df = df.merge(track, on="종목코드", how="left")
else:
    for col in ["흑자비율(%)", "최근자본", "최근순이익"]:
        df[col] = pd.NA

w52 = load_52w()
if not w52.empty:
    df = df.merge(w52, on="종목코드", how="left")
else:
    df["52주최고"] = pd.NA
    df["52주최저"] = pd.NA

close = df["종가"].astype("Float64")
high = df["52주최고"].astype("Float64")
low = df["52주최저"].astype("Float64")

# 고점 대비 얼마나 내려왔는지 (0% = 신고가, -50% = 고점의 반값)
df["고점대비(%)"] = ((close / high - 1) * 100).round(1).astype("Float64")
# 1년 범위에서 지금 위치 (0% = 최저가, 100% = 최고가)
span = (high - low)
df["52주위치(%)"] = (
    ((close - low) / span.where(span > 0) * 100).round(0).astype("Float64")
)

# 위험 신호 (자본잠식·적자·빚 과다·거래 부족 등) → src/risk.py
df = add_flags(df)

# ── 왼쪽 사이드바: 검색 및 필터 ────────────────────────────────
# 필터가 많으면 화면이 길어져 찾기 어려우므로, 주제별로 '접이식 카드'에 넣었습니다.
# 자주 쓰는 검색과 정렬은 항상 보이게 두고, 나머지는 접어둡니다.
#
# 각 입력칸의 key= 는 '이 값을 부르는 이름표'입니다.
# 아래쪽 '필터 초기화' 버튼이 이 이름표들을 지워서 처음 상태로 되돌립니다.
FILTER_KEYS = [
    "f_kw", "f_kinds", "f_markets", "f_price", "f_cap", "f_vol", "f_chg",
    "f_retp", "f_ret", "f_per", "f_roe", "f_debt", "f_fin", "f_sortcol",
]

with st.sidebar:
    st.header("🔎 검색 · 필터")

    keyword = st.text_input(
        "이름으로 목록 좁히기",
        placeholder="예: 삼성, KODEX, 005930",
        key="f_kw",
        help="여기는 **목록을 좁히는** 칸입니다. 여러 단어를 띄어쓰기로 넣으면 "
             "그중 하나라도 맞는 종목만 남습니다.\n\n"
             "종목 하나만 찾아 바로 보고 싶다면, 화면 위쪽의 "
             "**🔎 종목 바로 찾기** 를 쓰시는 편이 빠릅니다.",
    )

    st.caption("종목 하나만 찾으실 땐 화면 위쪽 **🔎 종목 바로 찾기** 가 빠릅니다.")

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
        # 정렬 방향은 기준마다 따로 기억하므로 한꺼번에 지웁니다.
        for k in [k for k in st.session_state if str(k).startswith("f_sortdir_")]:
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

# ── 표에 보여줄 열 묶음 ────────────────────────────────────────
# 열 19개를 한 번에 늘어놓으면 화면 밖으로 잘려서, 정작 보려던 숫자가
# 안 보입니다. 목적별로 묶어 두고 필요한 묶음만 보여줍니다.
BASE_COLS = ["종목코드", "종목명", "종가", "등락률(%)"]

COLUMN_SETS: dict[str, list[str]] = {
    "기본": BASE_COLS + ["시가총액(억)", "PER", "PBR", "ROE(%)", "배당수익률(%)"],
    "수익률": BASE_COLS + RETURN_COLS + ["52주위치(%)", "고점대비(%)"],
    "재무": BASE_COLS + ["PER", "PBR", "ROE(%)", "부채비율(%)",
                        "영업이익률(%)", "배당수익률(%)"],
    "전체": (
        ["종목코드", "종목명", "시장", "종류", "종가", "등락률(%)", "고점대비(%)",
         "거래량", "시가총액(억)"]
        + ["PER", "PBR", "배당수익률(%)"]
        + ["ROE(%)", "부채비율(%)", "영업이익률(%)"]
        + RETURN_COLS
    ),
}

# 정렬·카드에는 모든 열이 필요하므로 전체 목록도 따로 둡니다.
display_cols = COLUMN_SETS["전체"]

if view.empty:
    st.warning("조건에 맞는 종목이 없습니다. 왼쪽 필터를 조금 넓혀 보세요.")
    st.stop()

# ── 종목 바로 찾기 ───────────────────────────────────────────
# 사이드바 검색은 '목록을 좁히는' 기능이라, 휴대폰에서는 ☰ 필터를 열어야
# 보입니다. 하지만 대부분은 "이 종목 하나만 보고 싶다" 입니다.
# 그래서 화면 맨 위에 항상 보이는 검색칸을 따로 뒀습니다.
#
# ★ 필터에 걸려 목록에서 빠진 종목도 여기서는 찾을 수 있습니다 ★
#   전체 종목(df)에서 찾기 때문입니다. 필터를 풀지 않아도 됩니다.
st.markdown("#### 🔎 종목 바로 찾기")

jump_query = st.text_input(
    "종목 바로 찾기",
    key="q_jump",
    placeholder="삼성전자 · 005930 · ㅅㅅㅈㅈ",
    label_visibility="collapsed",
)


def _jump_to(code: str) -> None:
    """검색 결과를 누르면 그 종목을 '지금 보는 종목' 으로 정합니다."""
    st.session_state["sel_code"] = code
    # 표 클릭 기록을 지워야, 아래 표가 예전 선택으로 되돌리지 않습니다.
    st.session_state["_last_clicked"] = None


if jump_query.strip():
    hits = search(df, jump_query, limit=8)

    if hits.empty:
        st.info(
            f"**'{jump_query}'** 로 찾은 종목이 없습니다.\n\n"
            "이름의 일부만 넣거나(예: 삼성), 6자리 종목코드를 넣어 보세요. "
            "초성으로도 찾을 수 있습니다 (예: ㅅㅅㅈㅈ)."
        )
    else:
        st.caption(f"{len(hits)}개를 찾았습니다. 눌러서 바로 보세요.")
        cols = st.columns(min(len(hits), 4))
        for i, (_, hrow) in enumerate(hits.iterrows()):
            price = hrow.get("종가")
            price_txt = "" if pd.isna(price) else f"  {int(price):,}원"
            cols[i % len(cols)].button(
                f"{hrow['종목명']}  `{hrow['종목코드']}`{price_txt}",
                key=f"jump_{hrow['종목코드']}",
                on_click=_jump_to,
                args=(hrow["종목코드"],),
                width="stretch",
            )

st.divider()


# ── 화면을 네 칸(탭)으로 나눕니다 ─────────────────────────────
# 예전에는 목록·차트·재무가 위아래로 길게 이어져서 휴대폰에서 한참 스크롤해야
# 했습니다. 탭으로 나누면 한 번 눌러 바로 이동할 수 있습니다.
#
# 탭의 순서는 판단하는 순서와 같습니다.
#   목록에서 고르고 → 주가 흐름을 보고 → 지금 싼지 보고 → 회사 상태를 봅니다.
tab_list, tab_chart, tab_val, tab_fin = st.tabs(
    ["📋 종목 목록", "📊 차트", "📉 싼가 비싼가", "🏦 재무"]
)

with tab_list:
    st.subheader(f"종목 목록  ({len(view):,}개)")

    # ── 정렬: 무엇을 기준으로, 높은 순인지 낮은 순인지 ──
    # 목록 바로 위에 두어 휴대폰에서도 바로 보이고 바꾸기 쉽게 했습니다.
    SORT_COLUMNS: dict[str, str] = {
        "시가총액": "시가총액(억)",
        "등락률": "등락률(%)",
        "고점대비 (52주 최고 대비)": "고점대비(%)",
        "52주 위치": "52주위치(%)",
        "거래량": "거래량",
        "종가": "종가",
        "PER (주가수익비율)": "PER",
        "PBR (주가순자산비율)": "PBR",
        "배당수익률": "배당수익률(%)",
        "ROE (자기자본이익률)": "ROE(%)",
        "부채비율": "부채비율(%)",
        "영업이익률": "영업이익률(%)",
        **{f"수익률 {p}": f"수익률 {p}(%)" for p in PERIODS},
    }
    # 이 지표들은 '낮을수록 좋다'고 보는 것이 일반적이라 기본을 낮은 순으로 둡니다.
    LOWER_IS_BETTER = {"PER", "PBR", "부채비율(%)"}

    # 정렬 기준 · 순서 · 열 묶음을 한 줄에 둡니다.
    # 세 줄로 늘어놓으면 그만큼 표가 화면 아래로 밀려납니다.
    s1, s2, s3 = st.columns([4, 3, 5])

    sort_name = s1.selectbox(
        "↕️ 무엇을 기준으로", list(SORT_COLUMNS.keys()), index=0, key="f_sortcol",
        help="이 항목을 기준으로 목록을 줄 세웁니다.",
    )
    sort_col = SORT_COLUMNS[sort_name]

    default_dir = 1 if sort_col in LOWER_IS_BETTER else 0
    direction = s2.radio(
        "어느 쪽부터",
        ["높은 순 ↓", "낮은 순 ↑"],
        index=default_dir,
        horizontal=True,
        key=f"f_sortdir_{sort_col}",
        help="PER·PBR·부채비율은 낮을수록 좋다고 보는 것이 일반적이라 "
             "기본이 낮은 순입니다.",
    )
    ascending = direction.startswith("낮은")

    # 어떤 열을 볼지 고릅니다. (열을 다 펼치면 화면 밖으로 잘립니다)
    #
    # 휴대폰에서는 표 대신 카드로 보여주므로 이 칸이 쓸모없습니다.
    # 그런데도 놔두면 알약 4개가 세로로 쌓여 화면을 세 줄이나 먹습니다.
    # 그래서 컴퓨터에서만 보이게 감춥니다. (값은 그대로 계산됩니다)
    with s3.container(key="only_desktop_cols"):
        col_set = st.radio(
            "숫자 묶음",
            list(COLUMN_SETS.keys()),
            index=0,
            horizontal=True,
            key="f_colset",
            help="열을 한 번에 다 보여주면 화면 밖으로 잘려 읽기 어렵습니다. "
                 "보시려는 묶음만 고르세요. '전체' 는 옆으로 밀어서 봅니다.",
        )

    # 값이 없는 종목(빈칸)은 항상 맨 뒤로 보냅니다.
    view = view.sort_values(sort_col, ascending=ascending, na_position="last")
    table = view[display_cols].reset_index(drop=True)
    # 화면에 그릴 열 (없는 열은 건너뜁니다)
    shown_cols = [c for c in COLUMN_SETS[col_set] if c in table.columns]

    st.caption(
        f"**{sort_name}** {'낮은' if ascending else '높은'} 순으로 정렬했습니다. "
        f"1위 **{table.iloc[0]['종목명']}** "
        f"({'—' if pd.isna(table.iloc[0][sort_col]) else f'{float(table.iloc[0][sort_col]):,.2f}'})"
    )

    # '종목 선택' 칸의 자리를 목록 위에 미리 잡아둡니다.
    # (휴대폰에서 카드 40장을 지나 맨 아래까지 내려가지 않아도 되도록,
    #  내용은 나중에 채우고 위치만 여기로 정해두는 방식입니다)
    sel_slot = st.container()

    # ── 휴대폰: 카드 목록 (옆으로 밀 필요 없음) ──
    # st.container(key="only_mobile") 안에 넣으면 휴대폰에서만 보입니다. → src/ui_style.py
    with st.container(key="only_mobile"):
        st.markdown(make_stock_cards(view), unsafe_allow_html=True)
        if len(table) > 40:
            st.caption(
                f"조건에 맞는 {len(table):,}개 중 앞의 40개만 카드로 보여줍니다. "
                "왼쪽 필터로 범위를 좁히거나 정렬 기준을 바꿔 보세요."
            )

    # ── 컴퓨터: 지금까지의 표 그대로 ──
    with st.container(key="only_desktop"):
        # ── 표 그리기 ────────────────────────────────────────
        # 숫자를 미리 글자로 바꿔서 넘깁니다. 값이 없는 칸에 Streamlit 이
        # 'None' 이라고 영어로 적는 것을 없애기 위해서입니다. → src/ui_table.py
        #
        # 대신 열 제목을 누르면 글자순으로 정렬되므로, 숫자 순서로 보시려면
        # 위쪽 '무엇을 기준으로' 칸을 쓰셔야 합니다. (표 사용법에도 적어뒀습니다)
        HELPS = {
            "시가총액(억)": "ETF 는 거래소가 시가총액을 제공하지 않아 빈칸입니다.",
            "고점대비(%)": "최근 1년 최고가 대비 지금 주가가 몇 % 떨어져 있는지. "
                          "0 에 가까우면 1년 중 가장 비싼 구간입니다. "
                          "많이 떨어졌다고 싼 것은 아니니 이유를 꼭 확인하세요.",
            "PER": "주가수익비율 = 주가 ÷ 주당순이익. 낮을수록 이익 대비 주가가 쌉니다. "
                   "적자 기업이나 ETF 는 값이 없어 빈칸입니다.",
            "PBR": "주가순자산비율 = 주가 ÷ 주당순자산. 1보다 낮으면 장부가치보다 쌉니다.",
            "배당수익률(%)": "1년 배당금 ÷ 주가 × 100. 은행 이자율과 비교해 보세요.",
            "ROE(%)": "자기자본이익률 = 당기순이익 ÷ 자본총계 × 100. "
                      "높을수록 내 돈으로 돈을 잘 버는 회사입니다. (DART 최신 분기 기준)",
            "부채비율(%)": "부채총계 ÷ 자본총계 × 100. 낮을수록 빚이 적은 회사입니다. "
                          "100% 면 자기 돈과 빌린 돈이 같다는 뜻입니다.",
            "영업이익률(%)": "영업이익 ÷ 매출액 × 100. 높을수록 장사를 잘하는 회사입니다.",
            "52주위치(%)": "최근 1년 범위에서 지금 주가의 위치. 0 이면 1년 최저, 100 이면 최고입니다.",
        }
        LABELS = {"종가": "종가(원)", "거래량": "거래량(주)", "시가총액(억)": "시가총액(억원)"}

        numeric_src = table[shown_cols]
        shown_text = as_text(numeric_src, shown_cols)
        updown = [c for c in ["등락률(%)"] + RETURN_COLS if c in shown_cols]

        event = st.dataframe(
            shown_text.style.apply(
                lambda _: color_map(numeric_src, shown_cols, updown), axis=None
            ),
            width="stretch",
            hide_index=True,
            height=520,   # 한 화면에 더 많은 종목이 보이도록
            on_select="rerun",
            selection_mode="single-row",
            column_config=text_columns(
                numeric_src, shown_cols, helps=HELPS, labels=LABELS
            ),
        )

        # 사용법은 표 '아래' 에 둡니다. 위에 두면 그만큼 표가 밀려 내려갑니다.
        with st.expander("표 사용법", expanded=False):
            st.markdown(
                "- 표 왼쪽 끝의 네모(☐)를 누르면 그 종목이 **📊 차트 · 🏦 재무** 탭에 나타납니다\n"
                "- 표 위의 **종목 선택** 칸에서 골라도 됩니다\n"
                "- 숫자 순서로 줄 세우려면 표 위의 **무엇을 기준으로** 를 쓰세요\n"
                "  (열 제목을 눌러도 정렬되지만 글자순이라 숫자 크기와 다를 수 있습니다)\n"
                "- 열이 부족하면 위의 **숫자 묶음** 에서 다른 묶음을 고르세요"
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
    # 이름표는 전체 종목에서 가져옵니다.
    # (검색으로 고른 종목이 필터에 걸려 목록에 없어도 이름을 보여줘야 합니다)
    name_of = dict(zip(df["종목코드"], df["종목명"]))

    current = st.session_state.get("sel_code")

    # ★ 검색으로 고른 종목이 지금 필터에 걸려 목록에 없다면, 맨 앞에 끼워 넣습니다 ★
    #   이렇게 하지 않으면 선택이 목록 첫 종목으로 되돌아가서,
    #   검색해서 눌러도 엉뚱한 종목이 열리게 됩니다.
    outside = bool(current) and current not in codes
    if outside:
        codes = [current] + codes

    default_idx = codes.index(current) if current in codes else 0

    # 위에서 자리를 잡아둔 곳(sel_slot)에 선택 칸을 채워 넣습니다.
    with sel_slot:
        code = st.selectbox(
            "🔎 자세히 볼 종목",
            codes,
            index=default_idx,
            format_func=lambda c: f"{name_of.get(c, c)}  ({c})",
            help="이름 일부를 입력하면 바로 찾을 수 있습니다.",
        )
        if outside and code == current:
            st.caption(
                f"⚠️ **{name_of.get(current, current)}** 는 지금 걸어둔 필터 조건에 "
                "맞지 않아 아래 목록에는 없습니다. 검색으로 고르셨기 때문에 "
                "차트·재무 탭에서는 정상적으로 보입니다."
            )
    st.session_state["sel_code"] = code

# 고른 종목의 값은 '전체 종목(df)' 에서 가져옵니다.
# 걸러진 목록(table)에서 가져오면, 검색으로 고른 종목이 필터 밖일 때
# 찾지 못해 화면이 멈춥니다.
#
# df 에는 위험신호·52주 값까지 모두 들어 있어서, 예전처럼 원본을 한 번 더
# 뒤질 필요가 없습니다. (row 와 row_full 이 같은 줄을 가리킵니다)
_found = df[df["종목코드"] == code]
row = _found.iloc[0] if not _found.empty else df.iloc[0]
row_full = row
code = row["종목코드"]
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

    # ── 이 종목에 붙은 위험 신호를 먼저 보여줍니다 ──
    # (차트를 보기 전에 '조심할 점'을 먼저 알리는 것이 순서상 맞습니다)
    flags = row_full.get("위험신호") if row_full is not None else None
    if isinstance(flags, (list, tuple)) and flags:
        st.markdown(
            f"<div class='risk-box'>{badges_html(flags)}</div>",
            unsafe_allow_html=True,
        )
        with st.expander("⚠️ 이 신호들이 무슨 뜻인가요?", expanded=False):
            for label in flags:
                flag = next((f for f in FLAGS.values() if f.label == label), None)
                if flag:
                    st.markdown(f"**{flag.label}** ({flag.level}) — {flag.why}")
            st.caption(
                "이 신호는 '사지 말라'는 뜻이 아니라 '사기 전에 이유를 꼭 "
                "확인하라'는 표시입니다. 반대로 신호가 없다고 안전하다는 뜻도 아닙니다."
            )

    # ── 최근 1년 어디쯤인지 ──
    if row_full is not None and pd.notna(row_full.get("52주위치(%)")):
        st.markdown(w52_bar(row_full), unsafe_allow_html=True)

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


# ── 싼가 비싼가 탭 (밸류에이션 밴드) ─────────────────────────
# 'PER 12배' 라는 숫자 하나로는 초보자가 판단할 수 없습니다.
# 그 회사가 지난 3년 동안 받아온 자기 PER 과 비교해서 보여줍니다.
with tab_val:
    st.markdown(headline)

    st.caption(
        "다른 회사와 비교하지 않습니다. **이 회사가 지난 3년 동안 받아온 자기 값**과 "
        "비교합니다. 업종마다 적정 수준이 완전히 다르기 때문입니다."
    )

    band_hist = load_band_history(code)

    if band_hist.empty:
        st.info("이 종목은 과거 지표가 아직 없습니다. 수집이 끝나면 표시됩니다.")
    else:
        drawn = 0
        for metric in BAND_METRICS:
            stats = band_stats(band_hist, metric)
            if stats is None:
                continue
            drawn += 1

            st.markdown(band_html(stats), unsafe_allow_html=True)
            st.markdown(read_sentence(stats))

            with st.expander(f"{metric} 3년 흐름 그래프로 보기"):
                fig_band = band_figure(band_hist, metric, stats)
                if fig_band is None:
                    st.info("그래프를 그릴 자료가 부족합니다.")
                else:
                    st.plotly_chart(
                        fig_band, width="stretch", config={"displayModeBar": False}
                    )
                st.caption(
                    f"{BAND_METRICS[metric]['what']} · "
                    f"비교에 쓴 거래일 {stats['일수']:,}일"
                )
            st.divider()

        if drawn == 0:
            st.info(
                "이 종목은 비교할 지표가 없습니다.\n\n"
                "ETF 는 PER·PBR 이 제공되지 않고, 적자가 이어진 회사는 PER 을 "
                "계산할 수 없습니다. 이런 경우 이 화면 대신 **🏦 재무 탭**에서 "
                "매출·이익 추세를 보시는 편이 낫습니다."
            )
        else:
            st.warning(
                "**이 화면을 믿으면 안 되는 경우**\n\n"
                "1. 회사가 하는 사업이 3년 사이에 크게 바뀌었다면, 과거와 비교하는 것 "
                "자체가 의미 없습니다.\n"
                "2. 적자가 난 기간은 PER 을 계산할 수 없어 비교에서 빠졌습니다. "
                "적자가 잦은 회사일수록 이 막대는 부정확합니다.\n"
                "3. **싸다 = 사도 된다가 아닙니다.** 시장이 그 회사의 앞날을 나쁘게 "
                "보기 때문에 싼 경우가 훨씬 많습니다. 왜 싼지는 직접 확인하셔야 합니다."
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

        st.divider()

        # ══════════════════════════════════════════════════════
        #  실적 추세 — 숫자 하나가 아니라 '방향' 을 봅니다
        # ══════════════════════════════════════════════════════
        st.subheader("📈 실적이 좋아지는 중인가요?")

        kinds = available_kinds(fin)
        if not kinds:
            st.info(
                "추세를 그리려면 같은 종류의 보고서가 2개 이상 필요합니다. "
                "(예: 2024년 연간 + 2025년 연간)\n\n"
                "아직 한 개뿐이라 방향을 판단할 수 없습니다."
            )
        else:
            # ★ 왜 보고서 종류를 고르게 하나요? ★
            #   분기 보고서는 3개월치, 사업보고서는 1년치입니다. 이 둘을 나란히
            #   그리면 회사가 그대로여도 연간 막대만 네 배쯤 커 보입니다.
            #   그래서 같은 종류끼리만 모아 비교합니다.
            kind_labels = {
                q: f"{QUARTER_NAME.get(q, q)} ({QUARTER_SPAN.get(q, '')})" for q in kinds
            }
            picked_label = st.radio(
                "어떤 보고서끼리 비교할까요",
                [kind_labels[q] for q in kinds],
                index=0,
                horizontal=True,
                help="연간 보고서끼리 비교하는 것이 가장 정확합니다. "
                     "분기(3개월치)와 연간(1년치)은 담는 기간이 달라 "
                     "섞어서 비교하면 안 됩니다.",
            )
            kind = next(q for q in kinds if kind_labels[q] == picked_label)
            same = same_kind(fin, kind)

            # 말로 먼저 요약해 줍니다 (그래프를 못 읽어도 알 수 있게)
            for line in summary_lines(same, kind):
                st.markdown(f"- {line}")

            fig_rev = revenue_figure(same, kind)
            if fig_rev is not None:
                st.plotly_chart(
                    fig_rev, width="stretch", config={"displayModeBar": False}
                )
                st.caption(
                    "매출(막대)은 느는데 영업이익률(선)이 떨어지면, 싸게 팔아 덩치만 "
                    "키우는 중일 수 있습니다. 반대로 매출이 그대로여도 이익률이 오르면 "
                    "좋아지는 중입니다."
                )

            fig_profit = profit_figure(same, kind)
            if fig_profit is not None:
                st.plotly_chart(
                    fig_profit, width="stretch", config={"displayModeBar": False}
                )

            fig_yoy = yoy_figure(same, kind)
            if fig_yoy is not None:
                with st.expander("작년 같은 기간과 비교한 증감률 보기"):
                    st.plotly_chart(
                        fig_yoy, width="stretch", config={"displayModeBar": False}
                    )
                    st.caption(
                        "작년 실적이 적자였던 해는 증감률을 계산할 수 없어 빈칸입니다. "
                        "(적자에서 흑자로 바뀐 것은 % 로 표현되지 않습니다)"
                    )

        st.divider()

        # 분기별 비율 지표 추이 차트
        st.subheader("📊 비율 지표 추이")
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
