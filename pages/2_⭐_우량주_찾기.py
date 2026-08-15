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

from urllib.parse import quote_plus

from src.market_data import load_overview, load_track_record
from src.scoring import (
    GROUPS,
    METRICS,
    MIN_PEERS,
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
      .sector-row { margin: .45rem 0 .5rem 0; }
      .sector-tag {
        display: inline-block; font-size: .75rem; font-weight: 700; color: #1e40af;
        background: #eff6ff; border: 1px solid #bfdbfe;
        border-radius: 999px; padding: .12rem .55rem; margin-right: .3rem;
      }
      /* 업종 비교를 못 쓴 경우의 안내 태그는 눈에 덜 띄는 회색으로 */
      .sector-tag.plain { color: #64748b; background: #f1f5f9; border-color: #e2e8f0; }
      .link-row { display: flex; flex-wrap: wrap; gap: .4rem; margin: .6rem 0; }
      .link-row a {
        display: inline-block; text-decoration: none; font-weight: 700; font-size: .88rem;
        border: 1px solid #e2e8f0; background: #f8fafc; color: #0f172a;
        border-radius: 999px; padding: .45rem .85rem; min-height: 38px; line-height: 1.6;
      }
      .link-row a:hover { background: #eef2f7; border-color: #cbd5e1; }
      .fact-grid {
        display: grid; grid-template-columns: repeat(2, 1fr); gap: .25rem .8rem;
        font-size: .9rem; color: #475569; margin: .3rem 0 .2rem 0;
      }
      .fact-grid b { color: #0f172a; }
      @media (max-width: 640px) {
        .link-row a { flex: 1 1 46%; text-align: center; }
      }
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

# 실적 꾸준함(여러 분기의 흑자·매출 흐름)을 붙입니다.
track = load_track_record()
if not track.empty:
    df = df.merge(track, on="종목코드", how="left")
else:
    for col in ["흑자비율(%)", "매출성장(%)", "흑자분기수", "보고서수", "배당지속"]:
        df[col] = pd.NA

# 업종 정보를 아직 한 번도 수집하지 않았다면 알려줍니다.
has_sector = (df["업종"] != "업종 미상").any()
if not has_sector:
    st.info(
        "**업종 정보가 아직 없습니다.** 지금은 업종과 상관없이 같은 잣대로만 비교합니다.\n\n"
        "업종별 비교를 켜려면 GitHub 저장소 → **Actions** 탭 → "
        "**분기별 재무지표 수집** → **Run workflow** 를 한 번 눌러주세요. "
        "회사 업종·대표이사 정보를 받아옵니다(약 5~10분)."
    )

# ── 사이드바: 점수 기준 정하기 ────────────────────────────────
with st.sidebar:
    st.header("⚙️ 점수 기준")

    mode = st.radio(
        "비교 방식",
        ["같은 업종끼리 비교", "업종 상관없이 비교"],
        index=0 if has_sector else 1,
        disabled=not has_sector,
        help="업종마다 정상 범위가 다릅니다. 은행은 원래 부채비율이 수백 %이고 "
             "소프트웨어는 원래 PBR 이 높습니다. '같은 업종끼리 비교'를 고르면 "
             "그 업종 안에서 몇 등인지로 점수를 매겨 공정해집니다.",
    )
    score_mode = "같은 업종 비교" if mode == "같은 업종끼리 비교" else "절대 기준"

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
        sector_options = sorted(
            s for s in df["업종"].dropna().unique() if s != "업종 미상"
        )
        chosen_sectors = st.multiselect(
            "업종 (비워두면 전체)",
            sector_options,
            default=[],
            disabled=not has_sector,
            help="특정 업종 안에서만 좋은 회사를 찾고 싶을 때 쓰세요.",
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
if chosen_sectors:
    pool = pool[pool["업종"].isin(chosen_sectors)]
if min_cap > 0:
    pool = pool[pool["시가총액(억)"].astype("Float64").fillna(-1) >= min_cap]
if min_volume > 0:
    pool = pool[pool["거래량"].astype("Float64").fillna(-1) >= min_volume]

scored = score_table(pool, weights, mode=score_mode)
ranked = scored[scored["자료충분"]].sort_values("총점", ascending=False)
dropped = int((~scored["자료충분"]).sum())

# 업종 안에서 몇 등인지도 함께 계산합니다.
# (점수를 매길 때 실제로 쓴 묶음을 기준으로 세어야 앞뒤가 맞습니다)
if not ranked.empty and "업종" in ranked.columns:
    basis = (
        ranked["비교기준업종"].fillna(ranked["업종"])
        if "비교기준업종" in ranked.columns else ranked["업종"]
    )
    ranked = ranked.assign(비교묶음=basis)
    ranked["업종내순위"] = ranked.groupby("비교묶음")["총점"].rank(
        ascending=False, method="min"
    )
    ranked["업종내총수"] = ranked.groupby("비교묶음")["총점"].transform("count")

# ── 요약 ─────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("점수를 매긴 종목", f"{len(ranked):,}개")
c2.metric("자료 부족으로 제외", f"{dropped:,}개",
          help="ROE·부채비율·PER·PBR 중 하나라도 없으면 순위에서 뺍니다. "
               "적자 기업은 PER 이 없어 여기에 포함됩니다.")
c3.metric("비교 방식", "같은 업종끼리" if score_mode == "같은 업종 비교" else "업종 무관")

if score_mode == "같은 업종 비교" and "업종비교적용" in scored.columns:
    applied = int(scored["업종비교적용"].sum())
    st.caption(
        f"**점수 = 같은 업종 안에서의 등수**입니다. 100점이면 그 업종에서 1등, "
        f"50점이면 딱 중간이라는 뜻입니다. "
        f"적용된 종목 {applied:,}개 · 업종을 모르거나 같은 업종이 {MIN_PEERS}곳 "
        "미만인 종목은 공통 기준으로 점수를 매겼습니다."
    )
else:
    st.caption(
        "**점수 = 정해진 눈금에 따른 절대 점수**입니다. 업종과 상관없이 같은 잣대로 "
        "재기 때문에, 원래 빚이 많은 은행·건설은 낮게 나오는 점을 감안하세요."
    )

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

    # 업종과 업종 내 순위를 함께 보여줍니다.
    sector = row.get("업종") or "업종 미상"
    tag = f"<span class='sector-tag'>{sector}</span>"

    # 업종 비교가 실제로 적용된 종목에만 '업종 내 O위'를 붙입니다.
    # (같은 업종 회사가 몇 곳뿐이라 공통 기준으로 점수를 매긴 종목에
    #  '업종 내 1위'라고 적으면 오해를 주기 때문입니다)
    applied_here = bool(row.get("업종비교적용")) and score_mode == "같은 업종 비교"
    if applied_here and pd.notna(row.get("업종내순위")):
        basis = row.get("비교묶음") or sector
        # 자세한 업종에 회사가 적어 큰 묶음으로 비교했다면 그 이름을 함께 적습니다.
        where = "업종 내" if basis == sector else f"{basis} 내"
        tag += (f"<span class='sector-tag'>{where} "
                f"{int(row['업종내순위'])}위 / {int(row['업종내총수'])}개</span>")
    elif score_mode == "같은 업종 비교":
        tag += ("<span class='sector-tag plain'>같은 업종 회사가 적어 "
                "공통 기준으로 채점</span>")

    st.markdown(
        f"""
        <div class="rank-card">
          <div class="rank-head">
            <div class="rank-no {'top' if rank <= 3 else ''}">{rank}</div>
            <div><span class="rank-name">{row['종목명']}</span>
                 <span class="rank-code">{row['종목코드']} · {row['시장']}</span></div>
            <div class="rank-total">{row['총점']:.0f}<span> / 100</span></div>
          </div>
          <div class="sector-row">{tag}</div>
          {''.join(bar(g, row[f'묶음_{g}']) for g in GROUPS)}
          <div class="rank-sum">{summary_sentence(row)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"🔎 {row['종목명']} — 근거 자세히 보기"):
        # ── 회사 정보 (DART 기업개황) ──
        st.markdown("**🏢 회사 정보**")
        est_years = row.get("업력(년)")
        track_txt = "자료 없음"
        if pd.notna(row.get("보고서수")) and row.get("보고서수"):
            track_txt = (f"최근 {int(row['보고서수'])}개 보고서 중 "
                         f"{int(row['흑자분기수'])}개 흑자")
        st.markdown(
            f"""
            <div class="fact-grid">
              <div>업종 <b>{sector}</b></div>
              <div>대표이사 <b>{row.get('대표이사') or '정보 없음'}</b></div>
              <div>업력 <b>{f'{int(est_years)}년' if pd.notna(est_years) else '정보 없음'}</b></div>
              <div>실적 이력 <b>{track_txt}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 사업내용·뉴스·공시는 원문을 직접 보시도록 링크로 엽니다 ──
        # (뉴스 내용을 점수로 바꾸지 않습니다. 근거가 약하고 오판을 부르기 때문입니다)
        name_q = quote_plus(str(row["종목명"]))
        links = [
            (f"https://finance.naver.com/item/main.naver?code={row['종목코드']}",
             "📊 네이버 금융 (사업내용·시세)"),
            (f"https://search.naver.com/search.naver?where=news&query={name_q}",
             "📰 뉴스 검색"),
            (f"https://dart.fss.or.kr/dsab007/main.do?textCrpNm={name_q}",
             "📑 DART 공시·사업보고서"),
        ]
        if row.get("홈페이지"):
            links.append((str(row["홈페이지"]), "🌐 회사 홈페이지"))

        st.markdown(
            "<div class='link-row'>"
            + "".join(
                f"<a href='{url}' target='_blank' rel='noopener'>{text}</a>"
                for url, text in links
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "사업 내용·경영진 이력·최근 뉴스는 위 링크에서 직접 확인하세요. "
            "이 점수는 숫자만 보고 매긴 것이라 그런 내용은 반영되어 있지 않습니다."
        )

        st.markdown("**📐 지표별 근거**")
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
        "- **사업 내용과 경영진의 능력은 점수에 없습니다.** 대표이사 이름과 업력은 "
        "보여주지만, 사람의 경영 능력을 숫자로 매기는 것은 불가능합니다. 대신 "
        "'여러 분기 꾸준히 흑자였는가, 매출이 늘었는가'라는 **결과**로만 대신 봤습니다. "
        "사업 내용은 위의 네이버 금융·DART 링크에서 직접 확인하셔야 합니다.\n"
        "- **뉴스는 점수에 반영하지 않습니다.** 뉴스의 좋고 나쁨을 기계가 판정하면 "
        "오판이 잦아, 링크로만 연결했습니다. 큰 악재는 숫자에 나타나기 전에 "
        "뉴스에 먼저 나오므로 반드시 직접 확인하세요.\n"
        "- **업종 분류의 한계.** 표준산업분류를 기준으로 '반도체 / 전지(배터리) / "
        "게임 소프트웨어'처럼 잘게 나눠 비교하지만, 자세한 업종에 회사가 "
        f"{MIN_PEERS}곳 미만이면 큰 묶음(예: 전자·통신장비)으로 비교하고, "
        "그마저도 부족하면 공통 기준을 씁니다. 카드에 어떤 묶음으로 비교했는지 "
        "표시되니 확인하세요. 또 한 회사가 여러 사업을 해도 대표 업종 하나로만 "
        "분류됩니다.\n"
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
