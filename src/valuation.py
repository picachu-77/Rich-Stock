# -*- coding: utf-8 -*-
"""
'지금 이 주식이 싼가, 비싼가' 를 그 종목 자신의 과거와 비교하는 파일.

왜 필요한가요?
  화면에 "PER 12배" 라고만 나오면 초보자는 판단할 수 없습니다.
  12배가 싼 건지 비싼 건지는 종목마다 완전히 다르기 때문입니다.
  (은행은 5배도 보통이고, 성장하는 회사는 40배도 흔합니다)

  그래서 다른 회사와 비교하는 대신, **그 회사가 지난 3년 동안 받아온
  자기 PER** 과 비교합니다. "이 회사는 보통 15배쯤에 거래됐는데 지금은
  10배다" 라는 식으로 보면 초보자도 판단할 수 있습니다.

꼭 알아둘 한계 (화면에도 그대로 표시합니다)
  1) PER 이 낮다고 무조건 싼 게 아닙니다. 앞으로 이익이 줄어들 것 같으면
     시장이 미리 주가를 낮춰서 PER 이 낮아 보이는 것뿐일 수 있습니다.
  2) 회사가 하는 사업이 3년 사이에 크게 바뀌었다면 과거와 비교하는 것
     자체가 의미 없습니다.
  3) 적자가 난 기간은 PER 을 계산할 수 없어 비교에서 빠집니다.
"""

from __future__ import annotations

import warnings

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.db import get_conn

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)


# ── 비교할 지표 정의 ──────────────────────────────────────────
# lower_is_cheap : 값이 낮을수록 '싸다'는 뜻이면 True
#                  (배당수익률은 반대로 높을수록 투자자에게 유리합니다)
BAND_METRICS = {
    "PER": {
        "col": "per",
        "unit": "배",
        "digits": 2,
        "lower_is_cheap": True,
        "low_word": "싼 편",
        "high_word": "비싼 편",
        "what": "주가 ÷ 주당순이익. 지금 주가가 회사 이익의 몇 배인지",
    },
    "PBR": {
        "col": "pbr",
        "unit": "배",
        "digits": 2,
        "lower_is_cheap": True,
        "low_word": "싼 편",
        "high_word": "비싼 편",
        "what": "주가 ÷ 주당순자산. 회사가 가진 재산 대비 주가가 몇 배인지",
    },
    "배당수익률": {
        "col": "div_yield",
        "unit": "%",
        "digits": 2,
        "lower_is_cheap": False,
        "low_word": "적은 편",
        "high_word": "많은 편",
        "what": "1년 배당금 ÷ 주가 × 100. 주가가 내리면 이 값은 올라갑니다",
    },
}


# ── 데이터 읽기 ───────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_band_history(code: str, years: int = 3) -> pd.DataFrame:
    """
    한 종목의 최근 N년치 PER·PBR·배당수익률·종가를 날짜순으로 가져옵니다.

    기간의 끝은 '이 종목의 마지막 거래일' 이 아니라 '창고 전체의 마지막
    거래일' 을 기준으로 잡습니다. 거래가 끊긴 종목이 마치 최신인 것처럼
    보이는 것을 막기 위해서입니다.
    """
    sql = f"""
        WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price)
        SELECT p.trade_date, p.close, p.per, p.pbr, p.div_yield
          FROM daily_price p, bound b
         WHERE p.code = %(code)s
           AND p.trade_date >= b.last_d - INTERVAL '{int(years)} years'
         ORDER BY p.trade_date;
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn, params={"code": code})
    except Exception:  # noqa: BLE001
        # 밸류에이션 화면이 실패해도 나머지 화면은 계속 동작해야 합니다.
        return pd.DataFrame(columns=["trade_date", "close", "per", "pbr", "div_yield"])

    if df.empty:
        return df

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    for c in ["close", "per", "pbr", "div_yield"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _clean(series: pd.Series) -> pd.Series:
    """
    비교에 쓸 수 없는 값을 걸러냅니다.

    거래소는 적자인 회사의 PER 을 '0' 으로 내려보냅니다. 0 을 그대로 두면
    '역대급 저평가' 처럼 보이는 엉뚱한 결과가 나오므로 빼야 합니다.
    배당을 안 준 날의 배당수익률 0 도 같은 이유로 뺍니다.
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    return s[s > 0]


def band_stats(df: pd.DataFrame, metric: str) -> dict | None:
    """
    한 지표의 '3년 분포' 를 요약합니다.

    돌려주는 값
      현재      : 가장 최근 값
      최저/최고 : 3년 중 가장 낮았던 값 / 높았던 값
      25%/중앙/75% : 낮은 쪽부터 줄 세웠을 때 각 위치의 값
      백분위    : 지금 값이 과거 대비 몇 % 지점인지 (0 = 3년 최저, 100 = 3년 최고)
      일수      : 비교에 쓴 거래일 수
    """
    spec = BAND_METRICS.get(metric)
    if spec is None or df.empty or spec["col"] not in df:
        return None

    s = _clean(df[spec["col"]])
    # 최소 60거래일(약 3개월)은 있어야 '보통 수준' 을 말할 수 있습니다.
    if len(s) < 60:
        return None

    current = float(s.iloc[-1])
    pct = float((s <= current).mean() * 100)

    lo, hi, mid = float(s.min()), float(s.max()), float(s.median())

    # ★ 3년 내내 값이 거의 안 변한 종목 처리 ★
    #   값이 계속 12.0 이었다면 '지금 값보다 작거나 같은 날' 이 100% 가 되어
    #   '3년 중 가장 비싼 축' 이라는 엉뚱한 결론이 나옵니다. 실제로는
    #   비싸지도 싸지도 않은 것이므로, 폭이 거의 없으면 따로 표시합니다.
    spread = (hi - lo) / abs(mid) if mid else 0.0
    flat = spread < 0.02          # 3년 최고·최저 차이가 2% 미만

    return {
        "지표": metric,
        "현재": current,
        "최저": lo,
        "25%": float(s.quantile(0.25)),
        "중앙": mid,
        "75%": float(s.quantile(0.75)),
        "최고": hi,
        "백분위": pct,
        "변동없음": flat,
        "일수": int(len(s)),
        "단위": spec["unit"],
        "자릿수": spec["digits"],
        "싼쪽이낮음": spec["lower_is_cheap"],
    }


# ── 화면에 그리기 ─────────────────────────────────────────────
def _fmt(value: float, stats: dict) -> str:
    return f"{value:,.{stats['자릿수']}f}{stats['단위']}"


def cheapness_label(stats: dict) -> tuple[str, str]:
    """
    백분위를 '사람이 읽는 말' 로 바꿉니다.
    돌려주는 값: (짧은 표현, 색깔용 등급)
    """
    # 3년 내내 값이 안 변했다면 싸다·비싸다를 말할 수 없습니다.
    if stats.get("변동없음"):
        return "3년 내내 비슷한 값", "mid"

    pct = stats["백분위"]
    # 값이 낮을수록 싼 지표(PER·PBR)는 백분위가 낮을수록 싸다는 뜻입니다.
    # 배당수익률은 반대이므로 뒤집어서 '유리한 정도' 로 통일합니다.
    good = pct if not stats["싼쪽이낮음"] else 100 - pct

    if good >= 80:
        return "3년 중 가장 싼 축", "cheap"
    if good >= 60:
        return "3년 평균보다 싼 편", "cheapish"
    if good >= 40:
        return "3년 평균과 비슷", "mid"
    if good >= 20:
        return "3년 평균보다 비싼 편", "richish"
    return "3년 중 가장 비싼 축", "rich"


def band_html(stats: dict) -> str:
    """분포 막대 하나를 HTML 로 만듭니다. (모양은 src/ui_style.py 에 있습니다)"""
    metric = stats["지표"]
    spec = BAND_METRICS[metric]
    label, grade = cheapness_label(stats)

    # 점의 위치는 '백분위' 를 그대로 씁니다.
    # 값의 크기로 위치를 잡으면, 한 번 튄 값 때문에 나머지가 한쪽에 뭉쳐 보입니다.
    # 다만 3년 내내 값이 안 변한 종목은 위치가 뜻이 없으므로 가운데에 둡니다.
    pos = 50.0 if stats.get("변동없음") else max(0.0, min(100.0, stats["백분위"]))

    # 배당수익률은 오른쪽(높은 쪽)이 유리하므로 색 방향을 뒤집습니다.
    flip = "" if spec["lower_is_cheap"] else " flip"

    return (
        f"<div class='vb'>"
        f"  <div class='vb-head'>"
        f"    <span class='vb-title'>{metric} <b>{_fmt(stats['현재'], stats)}</b></span>"
        f"    <span class='vb-tag {grade}'>{label}</span>"
        f"  </div>"
        f"  <div class='vb-bar{flip}'>"
        f"    <div class='vb-dot' style='left:{pos:.0f}%'></div>"
        f"  </div>"
        f"  <div class='vb-ticks'>"
        f"    <span>{_fmt(stats['최저'], stats)}</span>"
        f"    <span class='vb-q'>{_fmt(stats['25%'], stats)}</span>"
        f"    <span>중앙 {_fmt(stats['중앙'], stats)}</span>"
        f"    <span class='vb-q'>{_fmt(stats['75%'], stats)}</span>"
        f"    <span>{_fmt(stats['최고'], stats)}</span>"
        f"  </div>"
        f"  <div class='vb-ends'><span>← {spec['low_word']}</span>"
        f"<span>{spec['high_word']} →</span></div>"
        f"</div>"
    )


def read_sentence(stats: dict) -> str:
    """막대 아래에 붙일 해석 문장. '주의할 점' 을 반드시 함께 적습니다."""
    metric = stats["지표"]
    pct = stats["백분위"]
    _, grade = cheapness_label(stats)
    now = _fmt(stats["현재"], stats)
    mid = _fmt(stats["중앙"], stats)

    if stats.get("변동없음"):
        return (
            f"지금 {metric} 은 **{now}** 입니다. 그런데 이 값이 3년 내내 거의 "
            "그대로였습니다.\n\n"
            "변동이 없으면 지금이 싼지 비싼지 **과거와 비교해서는 알 수 없습니다.** "
            "지표가 오래 갱신되지 않았을 수도 있으니, 🏦 재무 탭에서 실적을 "
            "직접 확인하시는 편이 낫습니다."
        )

    if metric == "배당수익률":
        base = (
            f"지금 배당수익률 **{now}** 은 최근 3년 중 **{pct:,.0f}% 지점**입니다. "
            f"(3년 보통 수준은 {mid})"
        )
        if grade in ("cheap", "cheapish"):
            caution = (
                "배당수익률이 높아진 이유가 **배당을 늘려서인지, 주가가 떨어져서인지** "
                "꼭 확인하세요. 주가가 떨어져서 높아진 것이라면 좋은 신호가 아닙니다."
            )
        else:
            caution = (
                "배당수익률은 주가가 오르면 자동으로 낮아집니다. "
                "회사가 배당을 줄인 것과는 다른 이야기입니다."
            )
        return f"{base}\n\n{caution}"

    base = (
        f"지금 {metric} **{now}** 은 최근 3년 중 **{pct:,.0f}% 지점**입니다. "
        f"(3년 보통 수준은 {mid})"
    )

    if grade == "cheap":
        caution = (
            f"3년 중 가장 싼 축입니다. 다만 **{metric}이 낮은 것이 항상 좋은 신호는 "
            "아닙니다.** 앞으로 이익이 줄어들 것 같으면 시장이 미리 주가를 낮춥니다. "
            "왜 싸졌는지(실적 악화인지, 시장 전체가 내린 것인지)를 뉴스와 재무 탭에서 "
            "먼저 확인하세요."
        )
    elif grade == "cheapish":
        caution = (
            "평소보다 싼 구간입니다. 회사 실적이 그대로인데 주가만 내린 것이라면 "
            "기회일 수 있고, 실적이 같이 나빠지는 중이라면 아닙니다. **재무 탭의 "
            "매출·영업이익 추세를 함께 보세요.**"
        )
    elif grade == "mid":
        caution = (
            "평소와 비슷한 값이라, 이 지표만으로는 싸다·비싸다를 말하기 어렵습니다. "
            "실적이 좋아지는 중인지를 보고 판단하는 편이 낫습니다."
        )
    elif grade == "richish":
        caution = (
            "평소보다 비싼 구간입니다. 이미 좋은 기대가 주가에 반영돼 있다는 뜻이라, "
            "기대만큼 실적이 나와도 주가가 크게 오르지 않을 수 있습니다."
        )
    else:
        caution = (
            "3년 중 가장 비싼 축입니다. 지금 사면 **회사가 잘해도 손해가 날 수 있는** "
            "구간입니다. 기대가 조금만 어긋나도 주가가 크게 내리기 쉽습니다."
        )

    return f"{base}\n\n{caution}"


def band_figure(df: pd.DataFrame, metric: str, stats: dict) -> go.Figure | None:
    """
    3년 동안 이 지표가 어떻게 움직였는지 선그래프로 그립니다.
    가운데 점선이 '3년 보통 수준(중앙값)' 입니다.
    """
    spec = BAND_METRICS.get(metric)
    if spec is None or df.empty:
        return None

    plot = df[["trade_date", spec["col"]]].copy()
    plot[spec["col"]] = pd.to_numeric(plot[spec["col"]], errors="coerce")
    plot = plot[plot[spec["col"]] > 0].dropna()
    if plot.empty:
        return None

    fig = go.Figure()

    # 25%~75% 구간(= 3년 중 절반의 시간을 보낸 구간)을 옅게 칠합니다.
    fig.add_hrect(
        y0=stats["25%"], y1=stats["75%"],
        fillcolor="rgba(37,99,235,.07)", line_width=0, layer="below",
    )
    fig.add_hline(
        y=stats["중앙"], line=dict(color="#94a3b8", width=1, dash="dash"),
        annotation_text=f"3년 보통 {_fmt(stats['중앙'], stats)}",
        annotation_position="top left",
        annotation_font=dict(size=11, color="#64748b"),
    )
    fig.add_trace(
        go.Scatter(
            x=plot["trade_date"], y=plot[spec["col"]],
            mode="lines", line=dict(width=2, color="#2563eb"),
            hovertemplate="%{x|%Y-%m-%d}<br>" + metric
                          + " %{y:,." + str(spec["digits"]) + "f}<extra></extra>",
        )
    )
    # 지금 위치를 점으로 찍어 눈에 띄게 합니다.
    fig.add_trace(
        go.Scatter(
            x=[plot["trade_date"].iloc[-1]], y=[plot[spec["col"]].iloc[-1]],
            mode="markers", marker=dict(size=11, color="#0f172a",
                                        line=dict(width=2, color="#fff")),
            hovertemplate="지금 %{y:,." + str(spec["digits"]) + "f}<extra></extra>",
        )
    )

    fig.update_yaxes(title_text=None, gridcolor="#eef2f7",
                     tickformat=",.{}f".format(spec["digits"]))
    fig.update_xaxes(title_text=None, tickformat="%y.%m",
                     hoverformat="%Y-%m-%d", gridcolor="#f5f7fa")
    fig.update_layout(
        height=260,
        margin=dict(l=6, r=6, t=34, b=6),
        showlegend=False,
        plot_bgcolor="white",
        hovermode="x unified",
        title=dict(text=f"{metric} 3년 흐름  (옅은 띠 = 흔했던 구간)",
                   font=dict(size=13)),
    )
    return fig
