"""
실수익 계산기 + ETF 비교 화면.

여기서 하는 일
  1) 세금·수수료를 뺀 '진짜 손에 쥐는 돈'을 계산합니다.
     화면에 보이는 수익률은 세금 전 숫자라, 실제로는 이보다 적게 남습니다.
  2) ETF 끼리 수익률·거래량을 비교합니다.
     ETF 는 재무제표가 없어 '우량주 찾기' 점수에서 빠지므로 여기서 따로 봅니다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.market_data import PERIODS, RETURN_COLS, load_overview
from src.ui_korean import apply_korean_ui
from src.ui_style import apply_style

st.set_page_config(
    page_title="계산기 · ETF 비교",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={},
)

apply_style()
apply_korean_ui()

st.title("🧮 계산기 · ETF 비교")

tab_calc, tab_etf = st.tabs(["🧮 실수익 계산기", "📦 ETF 비교"])

# ══════════════════════════════════════════════════════════════
#  1) 실수익 계산기
# ══════════════════════════════════════════════════════════════
with tab_calc:
    st.subheader("세금·수수료를 뺀 진짜 수익 계산")
    st.caption(
        "화면에 보이는 수익률은 **세금과 수수료를 빼기 전** 숫자입니다. "
        "실제로 통장에 남는 돈은 이보다 적습니다. 특히 자주 사고팔수록 차이가 커집니다."
    )

    c1, c2 = st.columns(2)
    buy_price = c1.number_input("산 가격 (1주당, 원)", min_value=0, value=50_000, step=100)
    sell_price = c2.number_input("판 가격 (1주당, 원)", min_value=0, value=60_000, step=100)

    c3, c4 = st.columns(2)
    qty = c3.number_input("수량 (주)", min_value=1, value=100, step=1)
    fee_rate = c4.number_input(
        "증권사 수수료 (%)", min_value=0.0, value=0.015, step=0.005, format="%.3f",
        help="살 때와 팔 때 각각 붙습니다. 온라인 기준 보통 0.01~0.02% 입니다. "
             "정확한 값은 쓰시는 증권사 앱에서 확인하세요.",
    )

    c5, c6 = st.columns(2)
    tax_rate = c5.number_input(
        "증권거래세 (%)", min_value=0.0, value=0.18, step=0.01, format="%.2f",
        help="팔 때만 냅니다. 이익이 났든 손해가 났든 무조건 붙습니다. "
             "세율은 해마다 바뀔 수 있으니 증권사 공지를 확인하세요.",
    )
    holding_years = c6.number_input(
        "보유 기간 (년)", min_value=0.0, value=1.0, step=0.5,
        help="연 단위 수익률(연환산)을 계산하는 데 씁니다. 0 이면 계산하지 않습니다.",
    )

    # ── 계산 ──
    buy_amount = buy_price * qty                 # 산 금액
    sell_amount = sell_price * qty               # 판 금액
    buy_fee = buy_amount * fee_rate / 100        # 살 때 수수료
    sell_fee = sell_amount * fee_rate / 100      # 팔 때 수수료
    tax = sell_amount * tax_rate / 100           # 거래세 (팔 때만)

    cost = buy_amount + buy_fee                  # 실제로 나간 돈
    proceeds = sell_amount - sell_fee - tax      # 실제로 들어온 돈
    profit = proceeds - cost                     # 진짜 손익
    gross_profit = sell_amount - buy_amount      # 세금 전 손익

    gross_rate = (gross_profit / buy_amount * 100) if buy_amount else 0.0
    net_rate = (profit / cost * 100) if cost else 0.0
    total_cost = buy_fee + sell_fee + tax

    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("화면에 보이는 수익률", f"{gross_rate:+.2f}%",
              help="세금·수수료를 빼기 전 숫자입니다.")
    m2.metric("실제 수익률", f"{net_rate:+.2f}%",
              delta=f"{net_rate - gross_rate:+.2f}%p",
              help="세금과 수수료를 모두 뺀 뒤의 수익률입니다.")
    m3.metric("빠져나가는 비용", f"{total_cost:,.0f}원",
              help="수수료(살 때+팔 때) + 증권거래세")

    detail = pd.DataFrame([
        {"항목": "① 산 금액", "금액(원)": buy_amount, "설명": f"{buy_price:,}원 × {qty:,}주"},
        {"항목": "② 살 때 수수료", "금액(원)": -buy_fee, "설명": f"산 금액의 {fee_rate}%"},
        {"항목": "③ 판 금액", "금액(원)": sell_amount, "설명": f"{sell_price:,}원 × {qty:,}주"},
        {"항목": "④ 팔 때 수수료", "금액(원)": -sell_fee, "설명": f"판 금액의 {fee_rate}%"},
        {"항목": "⑤ 증권거래세", "금액(원)": -tax,
         "설명": f"판 금액의 {tax_rate}% (손해를 봐도 냅니다)"},
        {"항목": "실제 손익", "금액(원)": profit, "설명": "③-④-⑤ 에서 ①+② 를 뺀 값"},
    ])
    st.dataframe(
        detail, width="stretch", hide_index=True,
        column_config={"금액(원)": st.column_config.NumberColumn(format="localized")},
    )

    # 본전이 되려면 얼마에 팔아야 하는지 (초보자가 자주 놓치는 부분)
    breakeven = cost / (qty * (1 - (fee_rate + tax_rate) / 100)) if qty else 0
    st.info(
        f"**본전 가격은 {breakeven:,.0f}원입니다.** "
        f"{buy_price:,}원에 샀더라도 세금·수수료 때문에 "
        f"{breakeven:,.0f}원 이상에 팔아야 손해를 보지 않습니다. "
        f"(1주당 약 {breakeven - buy_price:,.0f}원)"
    )

    if holding_years > 0:
        # 연환산 수익률: 같은 수익률이라도 1년에 낸 것과 5년에 낸 것은 다릅니다.
        annual = ((1 + net_rate / 100) ** (1 / holding_years) - 1) * 100
        st.caption(
            f"보유 {holding_years:g}년 기준 **연환산 수익률은 {annual:+.2f}%** 입니다. "
            "예금 이자율과 비교할 때는 이 값을 쓰세요."
        )

    with st.expander("📌 알아두면 좋은 것", expanded=False):
        st.markdown(
            "- **증권거래세는 손해를 봐도 냅니다.** 파는 금액 기준으로 무조건 떼갑니다.\n"
            "- **배당금에는 따로 15.4% 세금**이 붙어 그만큼 뗀 뒤 입금됩니다.\n"
            "- 1년간 이자+배당이 **2,000만원을 넘으면** 금융소득종합과세 대상이 됩니다.\n"
            "- 자주 사고팔수록 비용이 쌓입니다. 위 계산기에서 수량은 그대로 두고 "
            "매매를 10번 반복한다고 생각하면 비용도 10배가 됩니다.\n"
            "- 세율과 수수료는 바뀔 수 있습니다. 정확한 값은 증권사 앱에서 확인하세요."
        )

# ══════════════════════════════════════════════════════════════
#  2) ETF 비교
# ══════════════════════════════════════════════════════════════
with tab_etf:
    st.subheader("ETF 비교")
    st.caption(
        "ETF 는 여러 종목을 한 바구니에 담은 상품이라 **재무제표가 없습니다.** "
        "그래서 '우량주 찾기' 점수에서는 빠집니다. 여기서 ETF 끼리 수익률과 "
        "거래량을 비교해 보세요."
    )

    try:
        df = load_overview()
    except Exception as exc:  # noqa: BLE001
        st.error("데이터베이스에 접속하지 못했습니다.")
        st.code(str(exc))
        st.stop()

    etf = df[df["종류"] == "ETF"].copy()
    if etf.empty:
        st.warning("저장된 ETF 가 없습니다. 수집기를 먼저 실행해 주세요.")
        st.stop()

    e1, e2, e3 = st.columns([2, 2, 2])
    keyword = e1.text_input("ETF 이름 검색", placeholder="예: KODEX, 반도체, 배당")
    period = e2.selectbox("비교 기간", list(PERIODS.keys()), index=3)
    min_vol = e3.number_input(
        "최소 거래량 (주)", min_value=0, value=10_000, step=1_000,
        help="거래가 거의 없는 ETF 는 사고팔기 어려워 기본으로 걸러냅니다.",
    )

    if keyword.strip():
        etf = etf[etf["종목명"].str.contains(keyword.strip(), case=False, na=False)]
    if min_vol > 0:
        etf = etf[etf["거래량"].astype("Float64").fillna(-1) >= min_vol]

    ret_col = f"수익률 {period}(%)"
    etf = etf.sort_values(ret_col, ascending=False, na_position="last")

    if etf.empty:
        st.warning("조건에 맞는 ETF 가 없습니다. 검색어나 거래량 조건을 낮춰 보세요.")
        st.stop()

    st.caption(f"조건에 맞는 ETF {len(etf):,}개 · **{period} 수익률** 높은 순")

    top_n = st.slider("그래프에 몇 개까지 볼까요?", 5, 30, 15, step=5)
    chart_df = etf.head(top_n).iloc[::-1]      # 가로 막대는 아래부터 그려집니다

    fig = go.Figure(
        go.Bar(
            x=chart_df[ret_col].astype("Float64"),
            y=chart_df["종목명"],
            orientation="h",
            marker=dict(
                color=[
                    "#d92d20" if pd.notna(v) and float(v) >= 0 else "#1570ef"
                    for v in chart_df[ret_col]
                ]
            ),
            hovertemplate="%{y}<br>" + period + " 수익률 %{x:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(280, 26 * len(chart_df)),
        margin=dict(l=6, r=6, t=34, b=6),
        plot_bgcolor="white",
        xaxis=dict(title=f"{period} 수익률 (%)", gridcolor="#eef2f7", zerolinecolor="#cbd5e1"),
        yaxis=dict(title=None),
        title=dict(text=f"{period} 수익률 비교 (상위 {len(chart_df)}개)", font=dict(size=13)),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    show_cols = ["종목코드", "종목명", "시장", "종가", "등락률(%)", "거래량"] + RETURN_COLS
    st.dataframe(
        etf[show_cols].reset_index(drop=True),
        width="stretch", hide_index=True, height=380,
        column_config={
            "종가": st.column_config.NumberColumn("종가(원)", format="localized"),
            "거래량": st.column_config.NumberColumn("거래량(주)", format="localized"),
            "등락률(%)": st.column_config.NumberColumn(format="localized"),
            **{c: st.column_config.NumberColumn(c, format="localized") for c in RETURN_COLS},
        },
    )

    with st.expander("📌 ETF 를 고를 때 확인할 점", expanded=False):
        st.markdown(
            "- **과거 수익률이 앞날을 보장하지 않습니다.** 지난 1년 성적이 좋았다는 "
            "것은 그 기간에 그 분야가 좋았다는 뜻일 뿐입니다.\n"
            "- **무엇을 담고 있는지** 꼭 보세요. 이름만으로는 알 수 없습니다. "
            "증권사 앱이나 운용사 홈페이지에서 구성 종목을 확인할 수 있습니다.\n"
            "- **운용보수**(연 0.05~1%)가 매년 빠져나갑니다. 이 화면에는 그 정보가 "
            "없으니 상품 설명서에서 확인하세요.\n"
            "- **거래량이 적은 ETF** 는 사고팔 때 불리한 가격에 체결될 수 있습니다.\n"
            "- **레버리지·인버스**(2X, 곱버스 등)는 하루 단위로 움직임을 따라가도록 "
            "설계되어 장기 보유 시 예상과 크게 달라집니다. 초보자에게는 권하지 않습니다."
        )
