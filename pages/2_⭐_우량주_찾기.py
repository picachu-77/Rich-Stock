"""
'투자하기 좋은 회사' 를 점수로 줄 세워 보여주는 화면.

이 화면이 하는 일
  공개된 재무 숫자(ROE·부채비율·PER·PBR·배당 등)를 정해진 계산식에 넣어
  0~100 점을 매기고, 점수가 높은 순으로 보여줍니다.
  그리고 '왜 그 점수인지' 근거를 지표별로 전부 펼쳐 보여줍니다.

점수 기준을 바꾸려면
  src/scoring.py 의 METRICS 숫자만 고치면 이 화면이 자동으로 따라 바뀝니다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.market_data import load_overview
from src.scoring import (
    GROUPS,
    METRICS,
    WEIGHT_PRESETS,
    explain,
    score_table,
    summary_sentence,
)
from src.ui_korean import apply_korean_ui
from src.ui_style import apply_style, mobile_sidebar_button

st.set_page_config(
    page_title="우량주 찾기",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={},
)

apply_style()

# 이 화면에만 필요한 모양 (순위 카드)
st.markdown(
    """
    <style>
      .rank-card {
        border: 1px solid #e2e8f0; border-radius: 14px; background: #fff;
        padding: .8rem .95rem; margin-bottom: .55rem;
      }
      .rank-head { display: flex; align-items: center; gap: .6rem; }
      .rank-no {
        background: #2563eb; color: #fff; font-weight: 800; font-size: .95rem;
        min-width: 34px; height: 34px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
      }
      .rank-no.top { background: #f59e0b; }
      .rank-name { font-weight: 800; font-size: 1.06rem; }
      .rank-code { color: #64748b; font-size: .8rem; font-weight: 600; }
      .rank-total { margin-left: auto; font-weight: 800; font-size: 1.25rem; color: #2563eb; }
      .rank-total span { font-size: .8rem; color: #64748b; font-weight: 600; }
      .rank-sum { margin-top: .5rem; line-height: 1.75; font-size: .95rem; }
      .bar-wrap { display: flex; align-items: center; gap: .5rem; margin: .18rem 0; font-size: .85rem; }
      .bar-label { min-width: 52px; color: #475569; font-weight: 700; }
      .bar-bg { flex: 1; background: #f1f5f9; border-radius: 999px; height: 10px; overflow: hidden; }
      .bar-fill { height: 100%; border-radius: 999px; background: #2563eb; }
      .bar-val { min-width: 34px; text-align: right; font-weight: 700; color: #0f172a; }
      @media (max-width: 640px) {
        .rank-name { font-size: 1rem; }
        .rank-total { font-size: 1.1rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_korean_ui()
mobile_sidebar_button()

st.title("⭐ 우량주 찾기")

st.warning(
    "**이 순위는 투자 추천이 아닙니다.** 공개된 재무 숫자를 정해진 계산식에 넣어 "
    "기계적으로 매긴 점수일 뿐이며, 점수가 높다고 주가가 오른다는 뜻이 아닙니다. "
    "실제 투자 판단은 사업 내용·뉴스·업황을 직접 확인하신 뒤 본인 책임으로 하셔야 합니다."
)

# ── 데이터 ───────────────────────────────────────────────────
try:
    df = load_overview()
except Exception as exc:  # noqa: BLE001
    st.error("데이터베이스에 접속하지 못했습니다.")
    st.code(str(exc))
    st.stop()

if df.empty:
    st.warning("최근 30일 내 시세가 없습니다. 수집기를 먼저 실행해 주세요.")
    st.stop()

# ── 사이드바: 점수 기준 정하기 ────────────────────────────────
with st.sidebar:
    st.header("⚙️ 점수 기준")

    preset_name = st.selectbox(
        "무엇을 중요하게 볼까요?",
        list(WEIGHT_PRESETS.keys()),
        index=0,
        help="고른 항목에 따라 아래 가중치가 바뀝니다. 직접 조절도 가능합니다.",
    )
    base = WEIGHT_PRESETS[preset_name]

    with st.expander("⚖️ 가중치 직접 조절", expanded=False):
        st.caption("네 묶음의 비중을 바꿔 나만의 기준을 만들 수 있습니다.")
        weights = {
            g: st.slider(g, 0, 60, base[g], step=5, key=f"w_{g}_{preset_name}")
            for g in GROUPS
        }

    total_w = sum(weights.values())
    st.caption(
        "현재 비중 — "
        + " · ".join(f"{g} {round(w / total_w * 100) if total_w else 0}%"
                     for g, w in weights.items())
    )

    st.divider()
    with st.expander("🔍 대상 좁히기", expanded=False):
        markets = st.multiselect(
            "시장", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"]
        )
        min_cap = st.number_input(
            "최소 시가총액 (억원)", min_value=0, value=3_000, step=500,
            help="너무 작은 회사는 가격이 크게 흔들리고 정보도 적습니다. "
                 "0 을 넣으면 제한이 없어집니다.",
        )
        min_volume = st.number_input(
            "최소 거래량 (주)", min_value=0, value=10_000, step=1_000,
            help="거래가 거의 없는 종목은 팔고 싶을 때 팔기 어렵습니다.",
        )
        top_n = st.slider("몇 개까지 볼까요?", 5, 50, 10, step=5)

    st.divider()
    if st.button("🔄 최신 데이터 다시 읽기", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ── 점수 계산 ────────────────────────────────────────────────
# ETF 는 재무제표가 없어 애초에 제외합니다.
pool = df[df["종류"] == "주식"].copy()
if markets:
    pool = pool[pool["시장"].isin(markets)]
if min_cap > 0:
    pool = pool[pool["시가총액(억)"].astype("Float64").fillna(-1) >= min_cap]
if min_volume > 0:
    pool = pool[pool["거래량"].astype("Float64").fillna(-1) >= min_volume]

scored = score_table(pool, weights)
ranked = scored[scored["자료충분"]].sort_values("총점", ascending=False)
dropped = int((~scored["자료충분"]).sum())

# ── 요약 ─────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("점수를 매긴 종목", f"{len(ranked):,}개")
c2.metric("자료 부족으로 제외", f"{dropped:,}개",
          help="ROE·부채비율·PER·PBR 중 하나라도 없으면 순위에서 뺍니다. "
               "적자 기업은 PER 이 없어 여기에 포함됩니다.")
c3.metric("기준", preset_name)

if ranked.empty:
    st.warning(
        "조건에 맞는 종목이 없습니다. 왼쪽 **대상 좁히기**에서 "
        "최소 시가총액이나 거래량을 낮춰 보세요."
    )
    st.stop()

st.caption(
    f"아래는 위 기준으로 점수가 높은 순서입니다. 각 회사의 **‘근거 자세히 보기’**를 열면 "
    "지표별 값과 점수, 그리고 그 뜻을 볼 수 있습니다."
)

top = ranked.head(top_n).reset_index(drop=True)


def bar(label: str, score: float | None) -> str:
    """묶음 점수를 막대 하나로 그립니다."""
    if score is None or pd.isna(score):
        return (f"<div class='bar-wrap'><span class='bar-label'>{label}</span>"
                f"<div class='bar-bg'></div><span class='bar-val'>—</span></div>")
    pct = max(0, min(100, float(score)))
    color = "#0e9384" if pct >= 70 else ("#2563eb" if pct >= 45 else "#94a3b8")
    return (
        f"<div class='bar-wrap'><span class='bar-label'>{label}</span>"
        f"<div class='bar-bg'><div class='bar-fill' style='width:{pct:.0f}%;background:{color}'></div></div>"
        f"<span class='bar-val'>{pct:.0f}</span></div>"
    )


for i, row in top.iterrows():
    rank = i + 1
    st.markdown(
        f"""
        <div class="rank-card">
          <div class="rank-head">
            <div class="rank-no {'top' if rank <= 3 else ''}">{rank}</div>
            <div><span class="rank-name">{row['종목명']}</span>
                 <span class="rank-code">{row['종목코드']} · {row['시장']}</span></div>
            <div class="rank-total">{row['총점']:.0f}<span> / 100</span></div>
          </div>
          {''.join(bar(g, row[f'묶음_{g}']) for g in GROUPS)}
          <div class="rank-sum">{summary_sentence(row)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"🔎 {row['종목명']} — 근거 자세히 보기"):
        detail = pd.DataFrame(explain(row))
        st.dataframe(
            detail,
            width="stretch",
            hide_index=True,
            column_config={
                "묶음": st.column_config.TextColumn(width="small"),
                "지표": st.column_config.TextColumn(width="small"),
                "값": st.column_config.TextColumn(width="small"),
                "점수": st.column_config.ProgressColumn(
                    "점수", min_value=0, max_value=100, format="%d",
                    help="0~100 점. 기준은 src/scoring.py 에 적혀 있습니다.",
                ),
            },
        )

        st.caption(
            f"현재 주가 {row['종가']:,}원 · 등락률 {row['등락률(%)']:+.2f}% · "
            f"시가총액 {row['시가총액(억)']:,}억원"
            + (f" · 재무 기준 {row['재무 기준']}" if pd.notna(row.get("재무 기준")) else "")
        )

        # 이 회사의 지표가 전체 평균과 견줘 어디쯤인지 그림으로 봅니다.
        comp = go.Figure()
        labels = [m.label for m in METRICS]
        mine = [row.get(f"점수_{m.label}") for m in METRICS]
        avg = [ranked[f"점수_{m.label}"].mean() for m in METRICS]
        comp.add_trace(go.Bar(name="이 회사", x=labels, y=mine, marker_color="#2563eb"))
        comp.add_trace(go.Bar(name="전체 평균", x=labels, y=avg, marker_color="#cbd5e1"))
        comp.update_layout(
            barmode="group", height=260, margin=dict(l=6, r=6, t=34, b=6),
            plot_bgcolor="white", yaxis=dict(range=[0, 100], title="점수", gridcolor="#eef2f7"),
            title=dict(text="지표별 점수 — 이 회사 vs 전체 평균", font=dict(size=13)),
            legend=dict(orientation="h", y=1.18, x=0),
        )
        st.plotly_chart(comp, width="stretch", config={"displayModeBar": False},
                        key=f"cmp_{row['종목코드']}")

st.divider()

with st.expander("📏 점수를 어떻게 매기나요? (기준 전부 보기)", expanded=False):
    st.markdown(
        "각 지표를 0~100 점으로 바꾼 뒤, 네 묶음(수익성·안정성·가치·배당)의 "
        "평균을 내고 왼쪽에서 정한 비중대로 더해 총점을 만듭니다."
    )
    rule_rows = []
    for m in METRICS:
        scale = " · ".join(
            f"{v:g}{m.unit} → {s:g}점" for v, s in m.points
        )
        rule_rows.append({
            "묶음": m.group,
            "지표": m.label,
            "방향": "높을수록 좋음" if m.higher_is_better else "낮을수록 좋음",
            "점수 눈금": scale,
            "핵심 지표": "예 (없으면 순위 제외)" if m.required else "아니오",
        })
    st.dataframe(pd.DataFrame(rule_rows), width="stretch", hide_index=True)
    st.caption(
        "눈금 사이의 값은 직선으로 이어 계산합니다. "
        "예를 들어 ROE 눈금이 10%→60점, 15%→85점이면 ROE 12.5%는 72점이 됩니다."
    )

with st.expander("⚠️ 이 점수의 한계 (꼭 읽어보세요)", expanded=False):
    st.markdown(
        "- **업종 차이를 반영하지 못합니다.** 지금 데이터에는 업종 정보가 없어 "
        "은행·건설처럼 원래 부채비율이 높은 업종이 불리하게, 소프트웨어처럼 "
        "PBR이 높은 업종이 불리하게 나옵니다. 같은 업종끼리 비교하는 것이 원칙입니다.\n"
        "- **과거 숫자입니다.** 재무제표는 이미 지나간 실적이고, 주가는 앞날의 기대로 "
        "움직입니다. 점수가 높아도 앞으로 실적이 나빠질 수 있습니다.\n"
        "- **싼 데는 이유가 있을 수 있습니다.** PER·PBR이 낮아 점수가 높게 나온 회사가 "
        "사양산업이거나 실적이 꺾이는 중일 수 있습니다(가치 함정).\n"
        "- **적자 기업은 아예 빠집니다.** PER을 계산할 수 없기 때문입니다. "
        "적자라고 다 나쁜 회사는 아니며, 성장 초기 기업이 여기 해당할 수 있습니다.\n"
        "- **일회성 이익·회계 변경을 걸러내지 못합니다.** 부동산을 판 이익으로 ROE가 "
        "한 해만 좋아 보일 수 있습니다.\n"
        "- **사업 내용, 경영진, 뉴스, 지배구조는 전혀 보지 않습니다.**\n\n"
        "용어가 어렵다면 왼쪽 메뉴의 **📖 용어사전**을 함께 보세요."
    )
