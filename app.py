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
    menu_items={},  # 영어로 뜨는 기본 메뉴 항목을 비웁니다
)

# Streamlit 이 자동으로 붙이는 영어 요소들을 화면에서 감춥니다.
# (우측 상단 Deploy 버튼 / 햄버거 메뉴 / 하단 Made with Streamlit 등)
st.markdown(
    """
    <style>
      [data-testid="stToolbar"]      { visibility: hidden; height: 0; position: fixed; }
      [data-testid="stDecoration"]   { display: none; }
      [data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
      #MainMenu                      { visibility: hidden; height: 0; }
      footer                         { visibility: hidden; height: 0; }
      .stDeployButton                { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Streamlit 이 영어로 그리는 표 메뉴 등을 한글로 바꿉니다.
apply_korean_ui()

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
               code, trade_date, close, change_pct, volume, market_cap
          FROM recent
         ORDER BY code, trade_date DESC
    )
    SELECT t.code, t.name, t.market, t.kind, t.is_active,
           c.trade_date, c.close, c.change_pct, c.volume, c.market_cap,
           {select_returns}
      FROM cur c
      JOIN ticker t ON t.code = c.code
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

    # ★ 빈 값이 화면에 'None' 이라는 글자로 찍히지 않게 하는 처리 ★
    # 파이썬의 '숫자 아님(NaN)' 을 그대로 두면 Streamlit 이 None 이라고 적습니다.
    # 아래처럼 '값 없음을 표현할 수 있는 숫자형'으로 바꾸면 깔끔한 빈칸이 됩니다.
    for col in ["종가", "거래량", "시가총액(억)"]:
        df[col] = df[col].astype("Float64").round(0).astype("Int64")
    for col in ["등락률(%)"] + RETURN_COLS:
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
def load_meta() -> dict:
    """창고 현황 요약."""
    from src.store import summary

    with get_conn() as conn:
        return summary(conn)


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
with st.sidebar:
    st.header("🔎 검색 · 필터")

    keyword = st.text_input(
        "종목명 · 종목코드 검색",
        placeholder="예: 삼성, KODEX, 005930",
        help="여러 단어를 띄어쓰기로 넣으면 그중 하나라도 맞는 종목을 찾습니다.",
    )

    kinds = st.multiselect("종류", ["주식", "ETF"], default=["주식", "ETF"])
    markets = st.multiselect("시장", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"])

    st.divider()
    st.markdown("**숫자 조건으로 걸러내기**")

    price_min, price_max = st.slider(
        "주가 범위 (원)",
        min_value=0,
        max_value=1_000_000,
        value=(0, 1_000_000),
        step=1_000,
        help="양쪽 끝에 두면 제한 없음",
    )

    min_cap = st.number_input(
        "최소 시가총액 (억원)",
        min_value=0,
        value=0,
        step=100,
        help="0 이면 제한 없음. ETF 는 거래소가 시가총액을 주지 않아 빈칸이며, "
             "이 값을 1 이상으로 두면 ETF 는 목록에서 빠집니다.",
    )

    min_volume = st.number_input(
        "최소 거래량 (주)",
        min_value=0,
        value=0,
        step=1_000,
        help="거래가 거의 없는 종목을 걸러낼 때 사용하세요. 0 이면 제한 없음.",
    )

    chg_min, chg_max = st.slider(
        "등락률 범위 (%)",
        min_value=-30.0,
        max_value=30.0,
        value=(-30.0, 30.0),
        step=0.5,
        help="양쪽 끝에 두면 제한 없음",
    )

    st.divider()
    st.markdown("**수익률로 걸러내기**")

    ret_period = st.selectbox(
        "기준 기간",
        ["사용 안 함"] + list(PERIODS.keys()),
        index=0,
        help="예: '1년' 을 고르고 최소값을 20 으로 두면, "
             "1년 수익률이 20% 이상인 종목만 남습니다.",
    )
    ret_min, ret_max = st.slider(
        "수익률 범위 (%)",
        min_value=-100.0,
        max_value=300.0,
        value=(-100.0, 300.0),
        step=5.0,
        disabled=(ret_period == "사용 안 함"),
    )

    st.divider()
    sort_options = ["시가총액", "등락률(%)", "거래량", "종가"] + RETURN_COLS
    sort_by = st.selectbox("정렬 기준", sort_options, index=0)
    ascending = st.radio("정렬 방향", ["내림차순(큰 값 먼저)", "오름차순"], index=0) \
        == "오름차순"

    st.divider()
    if st.button("🔄 최신 데이터 다시 읽기", width="stretch"):
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

sort_col = "시가총액(억)" if sort_by == "시가총액" else sort_by
view = view.sort_values(sort_col, ascending=ascending, na_position="last")

display_cols = (
    ["종목코드", "종목명", "시장", "종류", "종가", "등락률(%)", "거래량", "시가총액(억)"]
    + RETURN_COLS
)
table = view[display_cols].reset_index(drop=True)

st.subheader(f"종목 목록  ({len(table):,}개)")
st.caption(
    "표 왼쪽 끝의 네모(☐)를 클릭하거나, 표 아래의 **종목 선택**에서 고르면 "
    "차트와 기간별 수익률이 나타납니다. "
    "열 제목을 클릭하면 그 열 기준으로 정렬됩니다."
)

if table.empty:
    st.warning("조건에 맞는 종목이 없습니다. 왼쪽 필터를 조금 넓혀 보세요.")
    st.stop()

event = st.dataframe(
    table,
    width="stretch",
    hide_index=True,
    height=430,
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
        **{
            c: st.column_config.NumberColumn(c, format="localized")
            for c in RETURN_COLS
        },
    },
)

# ── 어떤 종목을 볼지 정하기 ───────────────────────────────────
# 방법 두 가지를 모두 지원합니다.
#   (1) 위 표에서 줄을 클릭   (2) 아래 '종목 선택' 목록에서 고르기
selected_rows = event.selection.rows if event and event.selection else []

clicked_code = table.iloc[selected_rows[0]]["종목코드"] if selected_rows else None

# 표 클릭은 '방금 새로 클릭했을 때만' 반영합니다.
# (이렇게 하지 않으면 아래 선택창으로 바꿔도 표 클릭이 계속 덮어씁니다)
if clicked_code and clicked_code != st.session_state.get("_last_clicked"):
    st.session_state["_last_clicked"] = clicked_code
    st.session_state["sel_code"] = clicked_code

st.divider()
st.subheader("📊 종목 상세")

codes = table["종목코드"].tolist()
name_of = dict(zip(table["종목코드"], table["종목명"]))

current = st.session_state.get("sel_code")
default_idx = codes.index(current) if current in codes else 0

code = st.selectbox(
    "종목 선택",
    codes,
    index=default_idx,
    format_func=lambda c: f"{name_of.get(c, c)}  ({c})",
    help="이름 일부를 입력하면 바로 찾을 수 있습니다.",
)
st.session_state["sel_code"] = code

row = table[table["종목코드"] == code].iloc[0]
name = row["종목명"]

headline = f"### {name}  `{code}`"
detail_bits = [str(row["시장"]), str(row["종류"])]
if pd.notna(row["종가"]):
    detail_bits.append(f"종가 {int(row['종가']):,}원")
if pd.notna(row["등락률(%)"]):
    detail_bits.append(f"등락률 {float(row['등락률(%)']):+.2f}%")
st.markdown(headline + "\n\n" + "  ·  ".join(detail_bits))

hist = load_history(code)
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

# ── 차트 ─────────────────────────────────────────────────────
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
            hovertemplate="%{x|%Y-%m-%d}<br>종가 %{y:,.0f}원<extra></extra>",
        )
    )

    # 세로축은 0 부터가 아니라 실제 주가 범위에 맞춥니다 (변동이 잘 보이도록).
    lo, hi = float(plot_df["close"].min()), float(plot_df["close"].max())
    pad = max((hi - lo) * 0.10, max(hi * 0.02, 1))

    fig.update_yaxes(
        title_text="주가 (원)",
        tickformat=",.0f",
        range=[max(lo - pad, 0), hi + pad],
    )
    # 가로축은 날짜만 표시 (데이터가 적을 때 시:분:초가 뜨는 것을 막습니다)
    fig.update_xaxes(title_text=None, tickformat="%Y-%m-%d", hoverformat="%Y-%m-%d")
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=46, b=10),
        hovermode="x unified",
        showlegend=False,
        title=dict(
            # 위쪽 '기간별 수익률' 과 헷갈리지 않게 표현을 구분합니다.
            # 이것은 '차트에 그려진 구간의 처음 → 끝' 변동입니다.
            text=(
                f"차트 구간 변동  {period_ret:+.2f}%　"
                f"({plot_df['trade_date'].min():%Y-%m-%d} ~ "
                f"{plot_df['trade_date'].max():%Y-%m-%d}, 거래일 {len(plot_df)}일)"
            ),
            font=dict(size=14),
        ),
    )

    st.plotly_chart(fig, width="stretch")

    # 데이터가 너무 적으면 왜 그런지 알려줍니다.
    if len(plot_df) < 5:
        st.warning(
            f"이 기간에 저장된 거래일이 {len(plot_df)}일뿐이라 그래프가 거의 "
            "비어 보입니다. 과거 데이터 수집이 아직 진행 중이기 때문입니다. "
            "수집이 끝나면 정상적으로 그려집니다."
        )

with st.expander("원본 데이터 보기 (최근 60일)"):
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
        recent[["날짜", "종가(원)", "등락률(%)", "거래량(주)", "시가총액(억원)"]],
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
