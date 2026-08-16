# -*- coding: utf-8 -*-
"""
회사의 재무 '추세' 를 보여주는 파일. (숫자 하나가 아니라 방향을 봅니다)

왜 필요한가요?
  "ROE 12%" 라는 숫자 하나만 보면 이 회사가 좋아지는 중인지 나빠지는
  중인지 알 수 없습니다. 투자 판단에서는 지금 값보다 **방향**이 더
  중요할 때가 많습니다. 매출이 3년째 줄고 있는 회사와 3년째 늘고 있는
  회사는 같은 ROE 라도 완전히 다른 회사입니다.

★ 가장 중요한 주의점 — 보고서마다 담는 기간이 다릅니다 ★
  수집기(src/financial_collect.py)는 DART 의 '당기금액(thstrm_amount)' 을
  가져옵니다. 이 값이 담는 기간은 보고서 종류마다 다릅니다.

      1분기·반기·3분기 보고서 → 대체로 3개월치
      사업보고서(연간)        → 1년치

  그래서 분기 막대와 연간 막대를 나란히 그리면, 회사가 아무것도 달라진 게
  없어도 연간 막대만 네 배쯤 커 보입니다. 이건 성장이 아니라 착시입니다.

  이 파일은 그 함정을 막기 위해 **같은 종류의 보고서끼리만**
  (연간 vs 연간, 3분기 vs 3분기) 비교해서 그립니다.

  참고: 회사에 따라 누적 금액으로 적어 내는 곳도 있습니다. 값이 이상하게
  보이면 화면 아래 '재무제표 원본 금액 보기' 로 직접 확인하세요.
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

# 보고서 종류 이름 (DART 의 fiscal_quarter 값)
QUARTER_NAME = {1: "1분기", 2: "반기", 3: "3분기", 4: "연간"}

# 각 보고서가 대략 몇 개월치인지 (화면에 설명으로 띄웁니다)
QUARTER_SPAN = {1: "3개월치", 2: "3개월치", 3: "3개월치", 4: "1년치"}

# 금액 항목: (데이터베이스 칸 이름, 화면 이름, 색)
AMOUNT_COLS = {
    "revenue": ("매출액", "#2563eb"),
    "operating_profit": ("영업이익", "#0e9384"),
    "net_income": ("당기순이익", "#7839ee"),
}


@st.cache_data(ttl=600, show_spinner=False)
def load_financials(code: str) -> pd.DataFrame:
    """
    한 종목의 분기별 재무지표를 오래된 것부터 가져옵니다.

    재무 데이터가 없거나 표가 아직 없어도 화면이 멈추지 않도록,
    문제가 생기면 빈 표를 돌려줍니다.
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
    except Exception:  # noqa: BLE001
        return pd.DataFrame()

    if df.empty:
        return df

    df["기간"] = [
        f"{int(y)} {QUARTER_NAME.get(int(q), q)}"
        for y, q in zip(df["fiscal_year"], df["fiscal_quarter"])
    ]
    for c in ["roe", "debt_ratio", "op_margin", "payout_ratio"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 금액은 '원' 단위라 자릿수가 너무 깁니다. 억원으로 바꿔 둡니다.
    for c in ["revenue", "operating_profit", "net_income",
              "total_equity", "total_liabilities", "total_assets"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
        df[f"{c}_억"] = (df[c] / 100_000_000).round(0)
    return df


def available_kinds(fin: pd.DataFrame) -> list[int]:
    """
    비교에 쓸 수 있는 보고서 종류를 돌려줍니다.
    (같은 종류가 2개 이상 있어야 '추세' 를 말할 수 있으므로 그것만 고릅니다)
    """
    if fin.empty or "fiscal_quarter" not in fin:
        return []
    counts = fin["fiscal_quarter"].value_counts()
    kinds = [int(q) for q, n in counts.items() if n >= 2]
    # 연간(4) → 3분기 → 반기 → 1분기 순으로 보여줍니다. 연간이 가장 믿을 만합니다.
    return sorted(kinds, reverse=True)


def same_kind(fin: pd.DataFrame, quarter: int) -> pd.DataFrame:
    """같은 종류의 보고서만 뽑아 연도순으로 정렬합니다. (사과는 사과끼리 비교)"""
    if fin.empty:
        return fin
    out = fin[fin["fiscal_quarter"] == int(quarter)].copy()
    return out.sort_values("fiscal_year")


def add_yoy(same: pd.DataFrame) -> pd.DataFrame:
    """
    전년 같은 기간 대비 증감률(%)과 '흑자/적자 전환' 여부를 붙입니다.

    이미 '같은 종류의 보고서' 만 모아둔 표이므로, 바로 앞줄이 작년 같은 기간입니다.
    단, 중간에 빠진 연도가 있으면 계산하지 않습니다(엉뚱한 비교를 막기 위해).

    ★ 왜 적자일 때는 % 를 안 쓰나요? ★
      영업이익이 150억 → -50억 이 되면 계산상 '-133%' 가 나옵니다. 하지만
      이 숫자는 아무 뜻도 없습니다. 이익이 133% 줄어든다는 말 자체가
      성립하지 않기 때문입니다. 초보자가 가장 오해하기 쉬운 지점이라,
      이런 경우에는 % 대신 **'적자 전환'** 이라고 말로 적습니다.
    """
    out = same.copy()

    # 빈 표라도 뒤에서 쓰는 칸은 만들어 둡니다 (없는 칸을 찾다 멈추는 것을 막습니다).
    if out.empty:
        for col in AMOUNT_COLS:
            out[f"{col}_증감"] = pd.Series(dtype="float64")
            out[f"{col}_전환"] = pd.Series(dtype="object")
        return out

    years = pd.to_numeric(out["fiscal_year"], errors="coerce")
    is_prev_year = years.diff() == 1

    for col in AMOUNT_COLS:
        cur = pd.to_numeric(out[col], errors="coerce")
        prev = cur.shift(1)

        # 증감률은 '작년도 흑자, 올해도 흑자' 일 때만 뜻이 있습니다.
        both_positive = (prev > 0) & (cur > 0)
        growth = (cur / prev - 1) * 100
        out[f"{col}_증감"] = growth.where(both_positive & is_prev_year).round(1)

        # % 로 못 적는 경우는 말로 남깁니다.
        state = pd.Series(pd.NA, index=out.index, dtype="object")
        state[is_prev_year & (prev > 0) & (cur <= 0)] = "적자 전환"
        state[is_prev_year & (prev <= 0) & (cur > 0)] = "흑자 전환"
        state[is_prev_year & (prev <= 0) & (cur <= 0)] = "적자 지속"
        out[f"{col}_전환"] = state

    return out


def trend_arrow(values: pd.Series) -> str:
    """
    최근 3개 값의 방향을 화살표 한 글자로 요약합니다.
    (초보자가 표를 안 읽어도 방향은 알 수 있게)
    """
    s = pd.to_numeric(values, errors="coerce").dropna()
    if len(s) < 2:
        return ""
    recent = s.tail(3)
    if len(recent) >= 3 and recent.iloc[0] < recent.iloc[1] < recent.iloc[2]:
        return "📈 계속 늘어남"
    if len(recent) >= 3 and recent.iloc[0] > recent.iloc[1] > recent.iloc[2]:
        return "📉 계속 줄어듦"
    return "📈 늘어남" if s.iloc[-1] > s.iloc[-2] else "📉 줄어듦"


# ── 그래프 ────────────────────────────────────────────────────
def revenue_figure(same: pd.DataFrame, kind: int) -> go.Figure | None:
    """
    매출액(막대) + 영업이익률(선) 을 한 그림에 그립니다.

    이 둘을 같이 보는 이유
      매출만 늘고 이익률이 떨어지는 회사는 '싸게 팔아 덩치만 키우는' 중일 수
      있습니다. 반대로 매출이 그대로여도 이익률이 오르면 좋아지는 중입니다.
    """
    if same.empty:
        return None

    plot = same.dropna(subset=["revenue_억"])
    if plot.empty:
        return None

    x = [str(int(y)) for y in plot["fiscal_year"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x, y=plot["revenue_억"], name="매출액(억원)",
            marker=dict(color="#93c5fd"),
            hovertemplate="%{x}년<br>매출액 %{y:,.0f}억원<extra></extra>",
        )
    )

    margin = plot.dropna(subset=["op_margin"])
    if not margin.empty:
        fig.add_trace(
            go.Scatter(
                x=[str(int(y)) for y in margin["fiscal_year"]],
                y=margin["op_margin"],
                name="영업이익률(%)", yaxis="y2", mode="lines+markers",
                line=dict(width=3, color="#0e9384"), marker=dict(size=8),
                hovertemplate="%{x}년<br>영업이익률 %{y:,.2f}%<extra></extra>",
            )
        )

    fig.update_layout(
        height=320,
        margin=dict(l=6, r=6, t=44, b=6),
        plot_bgcolor="white",
        barmode="group",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
        yaxis=dict(title=None, tickformat=",.0f", gridcolor="#eef2f7"),
        yaxis2=dict(title=None, overlaying="y", side="right",
                    tickformat=",.1f", showgrid=False, ticksuffix="%"),
        xaxis=dict(title=None, type="category"),
        title=dict(
            text=f"연도별 매출액과 영업이익률  ({QUARTER_NAME.get(kind, '')} 기준)",
            font=dict(size=13),
        ),
    )
    return fig


def profit_figure(same: pd.DataFrame, kind: int) -> go.Figure | None:
    """
    영업이익·당기순이익을 묶음 막대로 그립니다.
    적자(0보다 작은 값)는 파란색으로 칠해 한눈에 보이게 합니다.
    """
    if same.empty:
        return None

    plot = same.dropna(subset=["operating_profit_억", "net_income_억"], how="all")
    if plot.empty:
        return None

    x = [str(int(y)) for y in plot["fiscal_year"]]
    fig = go.Figure()

    for col, (label, color) in [
        ("operating_profit", AMOUNT_COLS["operating_profit"]),
        ("net_income", AMOUNT_COLS["net_income"]),
    ]:
        vals = plot[f"{col}_억"]
        # 적자는 국내 증시 관행대로 파란색으로 표시합니다.
        colors = [color if pd.notna(v) and v >= 0 else "#1570ef" for v in vals]
        fig.add_trace(
            go.Bar(
                x=x, y=vals, name=f"{label}(억원)",
                marker=dict(color=colors),
                hovertemplate="%{x}년<br>" + label + " %{y:,.0f}억원<extra></extra>",
            )
        )

    # 0 선을 진하게 그려 흑자·적자 경계를 분명히 합니다.
    fig.add_hline(y=0, line=dict(color="#0f172a", width=1))
    fig.update_layout(
        height=300,
        margin=dict(l=6, r=6, t=44, b=6),
        plot_bgcolor="white",
        barmode="group",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
        yaxis=dict(title=None, tickformat=",.0f", gridcolor="#eef2f7"),
        xaxis=dict(title=None, type="category"),
        title=dict(
            text=f"연도별 영업이익·당기순이익  ({QUARTER_NAME.get(kind, '')} 기준, "
                 "파란 막대는 적자)",
            font=dict(size=13),
        ),
    )
    return fig


def yoy_figure(same: pd.DataFrame, kind: int) -> go.Figure | None:
    """
    전년 같은 기간 대비 증감률(%)을 막대로 그립니다.

    흑자↔적자가 뒤바뀐 해는 % 로 표현할 수 없어 막대가 비어 있습니다.
    (그 내용은 그래프 위 요약 문장에 말로 적힙니다)
    """
    if same.empty:
        return None

    plot = add_yoy(same)
    cols = [f"{c}_증감" for c in AMOUNT_COLS if f"{c}_증감" in plot.columns]
    if not cols:
        return None
    plot = plot.dropna(subset=cols, how="all")
    if plot.empty:
        return None

    x = [str(int(y)) for y in plot["fiscal_year"]]
    fig = go.Figure()
    for col, (label, color) in AMOUNT_COLS.items():
        vals = plot[f"{col}_증감"]
        if vals.dropna().empty:
            continue
        colors = [color if pd.notna(v) and v >= 0 else "#1570ef" for v in vals]
        fig.add_trace(
            go.Bar(
                x=x, y=vals, name=label, marker=dict(color=colors),
                hovertemplate="%{x}년<br>" + label + " %{y:+,.1f}%<extra></extra>",
            )
        )

    fig.add_hline(y=0, line=dict(color="#0f172a", width=1))
    fig.update_layout(
        height=280,
        margin=dict(l=6, r=6, t=44, b=6),
        plot_bgcolor="white",
        barmode="group",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=11)),
        yaxis=dict(title=None, tickformat=",.0f", ticksuffix="%", gridcolor="#eef2f7"),
        xaxis=dict(title=None, type="category"),
        title=dict(
            text=f"작년 같은 기간과 비교한 증감률  ({QUARTER_NAME.get(kind, '')} 기준)",
            font=dict(size=13),
        ),
    )
    return fig


def summary_lines(same: pd.DataFrame, kind: int) -> list[str]:
    """
    그래프를 못 읽는 사람도 알 수 있게, 추세를 문장으로 정리합니다.
    """
    if same.empty:
        return []

    y = add_yoy(same)
    last = y.iloc[-1]
    label_kind = QUARTER_NAME.get(int(kind), "")
    year = int(last["fiscal_year"])
    lines = []

    for col, (label, _) in AMOUNT_COLS.items():
        amount = last.get(f"{col}_억")
        growth = last.get(f"{col}_증감")
        state = last.get(f"{col}_전환")
        arrow = trend_arrow(same[col])

        if pd.isna(amount):
            continue

        text = f"**{label}** {year}년 {label_kind} 기준 **{float(amount):,.0f}억원**"

        if pd.notna(growth):
            word = "늘었습니다" if float(growth) >= 0 else "줄었습니다"
            text += f" — 작년 같은 기간보다 **{float(growth):+,.1f}%** {word}"
        elif pd.notna(state):
            # 흑자↔적자가 뒤바뀌면 % 가 뜻을 잃으므로 말로 적습니다.
            note = {
                "적자 전환": "작년 같은 기간에는 흑자였는데 **적자로 돌아섰습니다** ⚠️",
                "흑자 전환": "작년 같은 기간에는 적자였는데 **흑자로 돌아섰습니다**",
                "적자 지속": "작년 같은 기간에 이어 **적자가 이어지고 있습니다** ⚠️",
            }.get(str(state))
            if note:
                text += f" — {note}"

        if arrow:
            text += f"　({arrow})"
        lines.append(text)

    return lines
