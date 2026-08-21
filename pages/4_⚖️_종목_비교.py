# -*- coding: utf-8 -*-
"""
종목 2~4개를 나란히 놓고 비교하는 화면.

왜 필요한가요?
  종목을 하나씩 따로 보면 "괜찮네" 라는 느낌만 남습니다. 하지만 실제
  투자는 "이 셋 중에 뭘 살까" 를 고르는 일입니다. 나란히 놓고 봐야
  비로소 차이가 보입니다.

  이 화면은 어느 것을 사라고 말하지 않습니다. 같은 자리에 숫자를 놓아
  **직접 비교하고 직접 고르시라고** 만든 화면입니다.
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
)
from src.market_data import load_52w, load_overview, load_track_record
from src.risk import add_flags, badges_html
from src.ui_korean import apply_korean_ui, josa
from src.ui_style import apply_style
from src.valuation import BAND_METRICS, band_html, band_stats, load_band_history

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)

st.set_page_config(
    page_title="종목 비교",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={},
)

apply_style()
apply_korean_ui()

MAX_PICK = 4

# 비교표에 넣을 항목
#   방향  "high" = 높을수록 유리 / "low" = 낮을수록 유리 / None = 좋고 나쁨이 없음
#   자릿수, 단위
COMPARE_ROWS = [
    ("종가",           None,   0, "원",  "지금 1주 가격"),
    ("시가총액(억)",    None,   0, "억",  "회사 전체의 몸값. 클수록 대체로 안정적"),
    ("PER",           "low",  2, "배",  "이익 대비 주가. 낮을수록 싸다는 뜻"),
    ("PBR",           "low",  2, "배",  "재산 대비 주가. 낮을수록 싸다는 뜻"),
    ("배당수익률(%)",   "high", 2, "%",  "주가 대비 1년 배당금"),
    ("ROE(%)",        "high", 2, "%",  "자기 돈으로 얼마나 벌었나. 높을수록 좋음"),
    ("영업이익률(%)",   "high", 2, "%",  "매출 100원당 남는 영업이익"),
    ("부채비율(%)",     "low",  0, "%",  "자기 돈 대비 빚. 낮을수록 안전"),
    ("매출성장(%)",     "high", 1, "%",  "최근 보고서들 사이의 매출 증가율"),
    ("흑자비율(%)",     "high", 0, "%",  "최근 보고서 중 흑자였던 비율"),
    ("수익률 1년(%)",   "high", 1, "%",  "지난 1년 주가 변동. 과거일 뿐 앞날이 아님"),
    ("52주위치(%)",     None,   0, "%",  "1년 범위에서 지금 위치 (0=최저, 100=최고)"),
    ("고점대비(%)",     None,   1, "%",  "1년 최고가에서 얼마나 내려왔는지"),
    ("업력(년)",        None,   0, "년",  "회사가 세워진 뒤 지난 햇수"),
]


@st.cache_data(ttl=600, show_spinner=False)
def load_multi_history(codes: tuple[str, ...], years: int = 3) -> pd.DataFrame:
    """고른 종목들의 최근 N년 종가를 한 번에 가져옵니다."""
    if not codes:
        return pd.DataFrame(columns=["code", "trade_date", "close"])

    sql = f"""
        WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price)
        SELECT p.code, p.trade_date, p.close
          FROM daily_price p, bound b
         WHERE p.code IN %(codes)s
           AND p.trade_date >= b.last_d - INTERVAL '{int(years)} years'
           AND p.close IS NOT NULL
         ORDER BY p.code, p.trade_date;
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn, params={"codes": tuple(codes)})
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["code", "trade_date", "close"])

    if df.empty:
        return df
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df


def _fmt(value, digits: int, unit: str) -> str:
    """숫자를 화면용 글자로. 값이 없으면 '—'."""
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):,.{digits}f}{unit}"


def compare_table_html(picked: pd.DataFrame) -> str:
    """
    비교표를 만듭니다. (항목이 세로, 종목이 가로)

    ★ 표시는 '그 줄에서 가장 유리한 숫자' 라는 뜻일 뿐입니다.
    좋은 회사라는 뜻이 아닙니다 — 그 판단은 사람이 해야 합니다.
    """
    names = list(picked["종목명"])

    head = "".join(f"<th>{n}</th>" for n in names)
    body = []

    for col, direction, digits, unit, _tip in COMPARE_ROWS:
        if col not in picked.columns:
            continue
        values = pd.to_numeric(picked[col], errors="coerce")
        if values.dropna().empty:
            continue

        best_idx = set()
        # 비교 대상이 2개 이상 있을 때만 ★ 를 붙입니다.
        if direction and values.notna().sum() >= 2:
            target = values.max() if direction == "high" else values.min()
            best_idx = set(values[values == target].index)

        cells = []
        for idx, v in values.items():
            cls = " class='best'" if idx in best_idx else ""
            cells.append(f"<td{cls}>{_fmt(v, digits, unit)}</td>")
        body.append(f"<tr><td class='metric'>{col}</td>{''.join(cells)}</tr>")

    return (
        "<div class='cmp-wrap'><table class='cmp'>"
        f"<thead><tr><th class='metric'>항목</th>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></div>"
    )


def relative_figure(hist: pd.DataFrame, name_of: dict[str, str],
                    months: int | None) -> go.Figure | None:
    """
    여러 종목의 주가를 '시작을 100' 으로 맞춰 한 그림에 그립니다.

    왜 100 으로 맞추나요?
      5만원짜리와 50만원짜리를 그냥 겹쳐 그리면 비싼 쪽 선만 보입니다.
      시작점을 똑같이 100 으로 두면 '누가 더 올랐는지' 만 남습니다.
    """
    if hist.empty:
        return None

    plot = hist
    if months:
        cutoff = hist["trade_date"].max() - pd.DateOffset(months=months)
        plot = hist[hist["trade_date"] >= cutoff]
    if plot.empty:
        return None

    # 종목마다 데이터 시작일이 다르면 비교가 어긋납니다.
    # 모두가 데이터를 가진 가장 늦은 시작일로 기준을 맞춥니다.
    starts = plot.groupby("code")["trade_date"].min()
    base_date = starts.max()
    plot = plot[plot["trade_date"] >= base_date]
    if plot.empty:
        return None

    palette = ["#2563eb", "#d92d20", "#0e9384", "#7839ee"]
    fig = go.Figure()

    for i, (code, grp) in enumerate(plot.groupby("code")):
        grp = grp.sort_values("trade_date")
        base = float(grp["close"].iloc[0])
        if not base:
            continue
        rel = grp["close"] / base * 100
        label = name_of.get(code, code)
        fig.add_trace(
            go.Scatter(
                x=grp["trade_date"], y=rel, mode="lines", name=label,
                line=dict(width=2.4, color=palette[i % len(palette)]),
                hovertemplate="%{x|%Y-%m-%d}<br>" + label
                              + " %{y:,.1f}<extra></extra>",
            )
        )

    # 100 = 시작점. 이 선 위면 올랐고 아래면 내린 것입니다.
    fig.add_hline(y=100, line=dict(color="#94a3b8", width=1, dash="dash"))

    fig.update_yaxes(title_text=None, tickformat=",.0f", gridcolor="#eef2f7")
    fig.update_xaxes(title_text=None, tickformat="%y.%m",
                     hoverformat="%Y-%m-%d", gridcolor="#f5f7fa")
    fig.update_layout(
        height=360,
        margin=dict(l=6, r=6, t=44, b=6),
        plot_bgcolor="white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
        title=dict(
            text=f"시작을 100 으로 맞춘 주가 흐름  "
                 f"(기준일 {base_date:%Y-%m-%d})",
            font=dict(size=13),
        ),
    )
    return fig


# ══════════════════════════════════════════════════════════════
#  본문
# ══════════════════════════════════════════════════════════════
st.title("⚖️ 종목 비교")
st.caption(
    "종목 2~4개를 나란히 놓고 비교합니다. "
    "**어느 것을 사라고 말하지 않습니다.** 같은 자리에 숫자를 놓아 드릴 뿐이고, "
    "고르는 것은 직접 하셔야 합니다."
)

try:
    df = load_overview()
except Exception as exc:  # noqa: BLE001
    st.error("데이터베이스에 접속하지 못했습니다.")
    st.code(str(exc))
    st.stop()

if df.empty:
    st.warning("아직 시세 데이터가 없습니다. 수집기를 먼저 실행해 주세요.")
    st.stop()

# 실적 이력·52주 최고최저를 붙여 비교 항목을 늘립니다.
track = load_track_record()
if not track.empty:
    df = df.merge(track, on="종목코드", how="left")
for col in ["흑자비율(%)", "매출성장(%)"]:
    if col not in df:
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
df["고점대비(%)"] = ((close / high - 1) * 100).round(1).astype("Float64")
span = high - low
df["52주위치(%)"] = (
    ((close - low) / span.where(span > 0) * 100).round(0).astype("Float64")
)

df = add_flags(df)

# ── 종목 고르기 ───────────────────────────────────────────────
# 화면에 보일 이름표: "삼성전자 (005930)"  → 같은 이름의 종목도 구분됩니다.
df["표시이름"] = df["종목명"] + " (" + df["종목코드"] + ")"
label_to_code = dict(zip(df["표시이름"], df["종목코드"]))
code_to_name = dict(zip(df["종목코드"], df["종목명"]))

st.subheader("1. 비교할 종목 고르기")

picked_labels = st.multiselect(
    f"종목 이름이나 코드를 입력해 고르세요 (최대 {MAX_PICK}개)",
    options=sorted(label_to_code.keys()),
    max_selections=MAX_PICK,
    key="cmp_pick",
    placeholder="예: 삼성전자",
)

if not picked_labels:
    st.info(
        "위 칸에 종목을 **2개 이상** 골라 주세요.\n\n"
        "비슷한 회사끼리 비교해야 의미가 있습니다. "
        "예를 들어 은행끼리, 자동차 회사끼리 비교하는 식입니다. "
        "업종이 다른 회사를 비교하면 PER·부채비율 같은 숫자를 "
        "그대로 견주기 어렵습니다."
    )
    st.stop()

picked_codes = [label_to_code[l] for l in picked_labels]
picked = df[df["종목코드"].isin(picked_codes)].copy()
# 고른 순서대로 줄을 세웁니다 (사용자가 고른 순서가 곧 관심 순서입니다).
picked["_order"] = picked["종목코드"].map({c: i for i, c in enumerate(picked_codes)})
picked = picked.sort_values("_order").reset_index(drop=True)

# ── 같은 업종 경쟁사 추천 ─────────────────────────────────────
first_sector = picked.iloc[0].get("업종")
if first_sector and first_sector != "업종 미상" and len(picked_codes) < MAX_PICK:
    peers = df[
        (df["업종"] == first_sector)
        & (~df["종목코드"].isin(picked_codes))
        & (df["종류"] == "주식")
    ].sort_values("시가총액(억)", ascending=False).head(6)

    if not peers.empty:
        # 종목명 끝 글자에 따라 '과/와' 를 골라 붙입니다 (예: 삼성전자와 / 한국전력과)
        first_name = josa(str(picked.iloc[0]["종목명"]), "과/와")
        st.caption(
            f"**{first_name}** 같은 업종(**{first_sector}**)에서 "
            "시가총액이 큰 회사들입니다. 눌러서 비교에 추가할 수 있습니다."
        )

        def _add_peer(label: str) -> None:
            """버튼을 누르면 고른 목록에 더합니다."""
            current = st.session_state.get("cmp_pick", [])
            if label not in current and len(current) < MAX_PICK:
                st.session_state["cmp_pick"] = current + [label]

        cols = st.columns(min(len(peers), 3))
        for i, (_, prow) in enumerate(peers.iterrows()):
            cols[i % len(cols)].button(
                f"➕ {prow['종목명']}",
                key=f"peer_{prow['종목코드']}",
                on_click=_add_peer,
                args=(prow["표시이름"],),
                width="stretch",
            )

if len(picked) < 2:
    st.warning("비교하려면 종목이 **2개 이상** 있어야 합니다. 하나 더 골라 주세요.")
    st.stop()

# 업종이 서로 다르면 알려줍니다 (숫자를 그대로 견주면 안 되는 경우)
sectors = [s for s in picked["업종"].dropna().unique() if s != "업종 미상"]
if len(sectors) > 1:
    st.warning(
        f"고른 종목의 업종이 서로 다릅니다 (**{' / '.join(sectors)}**).\n\n"
        "업종이 다르면 PER·부채비율의 '보통 수준' 자체가 다릅니다. "
        "예를 들어 은행은 부채비율이 원래 매우 높고, 소프트웨어 회사는 원래 낮습니다. "
        "숫자를 그대로 견주지 마시고 참고만 하세요."
    )

st.divider()

tab_now, tab_val, tab_fin = st.tabs(
    ["📊 한눈에 비교", "📉 싼가 비싼가", "🏦 실적 추세"]
)

# ── 탭 1: 한눈에 비교 ─────────────────────────────────────────
with tab_now:
    st.subheader("2. 숫자를 나란히 놓고 보기")

    st.markdown(compare_table_html(picked), unsafe_allow_html=True)
    st.caption(
        "★ 는 **그 줄에서만** 가장 유리한 숫자라는 표시입니다. "
        "★ 가 많다고 좋은 회사라는 뜻이 결코 아닙니다. "
        "예를 들어 PER 이 가장 낮은 회사는 시장이 그 회사의 앞날을 "
        "가장 나쁘게 보고 있다는 뜻일 수도 있습니다."
    )

    # 위험 신호를 종목별로
    st.markdown("#### ⚠️ 위험 신호")
    any_flag = False
    for _, r in picked.iterrows():
        flags = r.get("위험신호")
        if isinstance(flags, (list, tuple)) and flags:
            any_flag = True
            st.markdown(
                f"**{r['종목명']}** {badges_html(flags)}", unsafe_allow_html=True
            )
        else:
            st.markdown(f"**{r['종목명']}** — 표시된 신호 없음")
    if not any_flag:
        st.caption(
            "신호가 없다고 안전하다는 뜻은 아닙니다. "
            "이 화면이 확인하는 몇 가지 항목에 걸리지 않았다는 뜻일 뿐입니다."
        )

    st.divider()

    # 주가 흐름 겹쳐 보기
    st.markdown("#### 📈 주가 흐름 나란히 보기")
    range_label = st.radio(
        "기간",
        ["3개월", "6개월", "1년", "3년"],
        index=2,
        horizontal=True,
        key="cmp_range",
    )
    months_map = {"3개월": 3, "6개월": 6, "1년": 12, "3년": 36}

    hist = load_multi_history(tuple(picked_codes))
    fig_rel = relative_figure(hist, code_to_name, months_map[range_label])

    if fig_rel is None:
        st.info("이 기간에 겹치는 시세 자료가 부족해 그래프를 그릴 수 없습니다.")
    else:
        st.plotly_chart(fig_rel, width="stretch", config={"displayModeBar": False})
        st.caption(
            "모두 **100 에서 시작**하도록 맞췄습니다. 100 보다 위면 그 기간에 오른 것, "
            "아래면 내린 것입니다. 실제 주가가 아니라 **변동폭만** 비교하는 그래프입니다. "
            "지난 성적이 앞으로를 알려주지는 않습니다."
        )

# ── 탭 2: 싼가 비싼가 ─────────────────────────────────────────
with tab_val:
    st.subheader("3. 각자 자기 과거와 비교하면 지금 싼가?")
    st.caption(
        "종목끼리 PER 을 직접 견주지 않습니다. **각 회사가 지난 3년 동안 받아온 "
        "자기 PER** 과 비교합니다. 그래야 업종이 다른 회사도 같은 기준으로 볼 수 있습니다."
    )

    cols = st.columns(len(picked))
    for col, (_, r) in zip(cols, picked.iterrows()):
        with col:
            st.markdown(f"##### {r['종목명']}")
            hist_b = load_band_history(r["종목코드"])
            drawn = 0
            for metric in BAND_METRICS:
                stats = band_stats(hist_b, metric)
                if stats is None:
                    continue
                drawn += 1
                st.markdown(band_html(stats), unsafe_allow_html=True)
            if drawn == 0:
                st.info("과거 지표가 부족해 비교할 수 없습니다.")

    st.caption(
        "막대의 점이 **왼쪽에 있을수록 그 회사 기준으로 싼 구간**입니다 "
        "(배당수익률은 반대로 오른쪽이 유리합니다). "
        "다만 싸다고 사도 된다는 뜻은 아닙니다 — 시장이 그 회사의 앞날을 나쁘게 봐서 "
        "싼 경우가 훨씬 많습니다."
    )

# ── 탭 3: 실적 추세 ───────────────────────────────────────────
with tab_fin:
    st.subheader("4. 실적이 좋아지는 중인가?")
    st.caption(
        "지금 숫자보다 **방향**이 중요합니다. 매출이 3년째 줄고 있는 회사와 "
        "3년째 늘고 있는 회사는 같은 ROE 라도 완전히 다른 회사입니다."
    )

    for _, r in picked.iterrows():
        code = r["종목코드"]
        st.markdown(f"#### {r['종목명']} ({code})")

        fin = load_financials(code)
        if fin.empty:
            st.info("이 종목은 재무 자료가 없습니다. (ETF·리츠 등은 원래 없습니다)")
            st.divider()
            continue

        kinds = available_kinds(fin)
        if not kinds:
            st.info(
                "같은 종류의 보고서가 2개 이상 있어야 방향을 볼 수 있습니다. "
                "아직 하나뿐입니다."
            )
            st.divider()
            continue

        kind = kinds[0]  # 연간이 있으면 연간을 씁니다 (가장 믿을 만한 비교)
        same = same_kind(fin, kind)

        st.caption(
            f"**{QUARTER_NAME.get(kind, '')}** 보고서끼리 비교 "
            f"({QUARTER_SPAN.get(kind, '')}) · 출처: DART 전자공시"
        )
        for line in summary_lines(same, kind):
            st.markdown(f"- {line}")

        fig_rev = revenue_figure(same, kind)
        if fig_rev is not None:
            st.plotly_chart(
                fig_rev, width="stretch", config={"displayModeBar": False},
                key=f"rev_{code}",
            )

        with st.expander(f"{r['종목명']} 영업이익·순이익 막대 보기"):
            fig_p = profit_figure(same, kind)
            if fig_p is None:
                st.info("그릴 자료가 부족합니다.")
            else:
                st.plotly_chart(
                    fig_p, width="stretch", config={"displayModeBar": False},
                    key=f"prof_{code}",
                )
        st.divider()

    st.info(
        "**비교할 때 조심할 점**\n\n"
        "회사마다 보고서에 담긴 기간이 다를 수 있습니다. 위 그래프는 각 회사의 "
        "같은 종류 보고서끼리만 비교하지만, 회사 A 는 연간·회사 B 는 3분기 기준일 수 "
        "있습니다. 각 그래프 위의 '기준' 설명을 확인하세요."
    )
