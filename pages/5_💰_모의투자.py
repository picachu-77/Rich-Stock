# -*- coding: utf-8 -*-
"""
모의투자 화면 — 진짜 돈을 쓰기 전에 **투자를 연습하는 곳**.

이 화면의 목적은 '얼마 벌었나' 가 아닙니다
  가짜 돈으로 번 수익률은 아무 의미가 없습니다. 몇 번 안 되는 매매에서
  결과는 거의 운입니다. 그래서 여기서는 **판단하는 습관**을 봅니다.

    · 살 이유를 정하고 사는가
    · 팔 기준(목표가·손절가)을 **사기 전에** 정하는가
    · 정해둔 기준을 실제로 지키는가
    · 한 곳에 몰지 않고, 너무 자주 사고팔지 않는가

  이 네 가지는 실제 돈을 넣었을 때 그대로 따라옵니다. 연습으로 고칠 수
  있는 것도 이 네 가지뿐입니다. 그래서 이것만 점수로 봅니다.

화면 구성
  🎓 연습     — 무엇부터 해볼지, 내 습관은 몇 점인지
  💼 내 계좌  — 지금 들고 있는 것
  🛒 사고팔기 — 사고파는 곳 (살 때 이유의 '종류' 를 함께 고릅니다)
  🔍 복기     — 판 뒤에 '계획대로 했는지' 되돌아보는 곳
  💵 예수금   — 연습에 쓸 돈

  실제로 매수를 막는 것은 '현금 부족' 하나뿐입니다. 나머지는 알려주기만
  하고 막지 않습니다. 막아버리면 연습이 아니라 시험이 됩니다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.db import get_conn
from src.market_data import load_overview
from src.risk import add_flags, badges_html
from src.ui_table import as_text, text_columns
from src.paper import (
    DEFAULT_FEE_RATE,
    alerts,
    DEFAULT_TAX_RATE,
    add_cash,
    add_trade,
    cash_balance,
    concentration_warnings,
    costs,
    delete_cash,
    delete_trade,
    held_qty,
    load_cash,
    load_trades,
    positions,
    summary,
    walk,
)
from src.practice import (
    BUY_REASONS,
    SELL_REASONS,
    by_reason,
    coach,
    grade,
    habits,
    missions,
    overall,
    reviews,
    tag,
    untag,
)
from src.search import search
from src.ui_korean import apply_korean_ui, josa
from src.ui_style import apply_style

st.set_page_config(
    page_title="모의투자",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={},
)

apply_style()
apply_korean_ui()


def money(v, digits: int = 0) -> str:
    """돈을 보기 좋게. 값이 없으면 '—'."""
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):,.{digits}f}원"


def _in_words(amount: float) -> str:
    """
    큰 금액을 '억/만' 단위로 덧붙여 읽어줍니다.

    1000000 처럼 0 이 많은 숫자는 자릿수를 세어야 얼마인지 알 수 있습니다.
    '100만원' 이라고 함께 적어주면 한눈에 들어옵니다.
    """
    n = int(amount or 0)
    if n < 10_000:
        return ""
    억, 나머지 = divmod(n, 100_000_000)
    만 = 나머지 // 10_000
    parts = []
    if 억:
        parts.append(f"{억:,}억")
    if 만:
        parts.append(f"{만:,}만")
    return f"  ({''.join(parts)}원)" if parts else ""


def signed(v, digits: int = 0) -> str:
    """손익처럼 부호가 중요한 값."""
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):+,.{digits}f}원"


def flash(msg: str, kind: str = "success") -> None:
    """
    다음 화면에 뜰 안내문을 적어둡니다.

    왜 필요한가요?
      st.success() 로 안내를 띄운 직후 st.rerun() 을 하면 화면이 새로 그려지면서
      그 안내가 사라집니다. 그러면 사고팔기 버튼을 눌러도 아무 반응이 없는 것처럼
      보입니다. 그래서 안내문을 잠깐 적어뒀다가 새로 그린 화면에서 보여줍니다.
    """
    st.session_state["_알림"] = (kind, msg)


def show_flash() -> None:
    """적어둔 안내문이 있으면 한 번 보여주고 지웁니다."""
    got = st.session_state.pop("_알림", None)
    if not got:
        return
    kind, msg = got
    (st.success if kind == "success" else st.info)(msg)


st.title("💰 모의투자 — 연습장")
st.caption(
    "**진짜 돈은 한 푼도 쓰지 않습니다.** 여기서 보는 것은 '얼마 벌었나' 가 아니라 "
    "**어떻게 판단하는가** 입니다. 가짜 돈으로 낸 수익률은 거의 운이지만, "
    "기준을 정하고 지키는 습관은 실제 돈을 넣어도 그대로 따라옵니다."
)

# ── 데이터 읽기 ───────────────────────────────────────────────
try:
    market = load_overview()
except Exception as exc:  # noqa: BLE001
    st.error("데이터베이스에 접속하지 못했습니다.")
    st.code(str(exc))
    st.stop()

if market.empty:
    st.warning("아직 시세 데이터가 없습니다. 수집기를 먼저 실행해 주세요.")
    st.stop()

# 보유 종목에 위험 신호(자본잠식·적자 잦음 등)를 함께 보여주기 위해 붙입니다.
market = add_flags(market)

price_of = {
    r["종목코드"]: (float(r["종가"]) if pd.notna(r["종가"]) else None)
    for _, r in market.iterrows()
}
price_of = {k: v for k, v in price_of.items() if v is not None}
name_of = dict(zip(market["종목코드"], market["종목명"]))
sector_of = dict(zip(market["종목코드"], market.get("업종", pd.Series(dtype=str))))
flags_of = dict(zip(market["종목코드"], market.get("위험신호", pd.Series(dtype=object))))

trades = load_trades()
cash = load_cash()

# 표가 아직 없을 수도 있습니다 (create_tables 를 다시 돌려야 하는 경우)
try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.paper_trade');")
            table_ready = cur.fetchone()[0] is not None
except Exception:  # noqa: BLE001
    table_ready = False

if not table_ready:
    st.error(
        "모의투자용 표가 아직 없습니다.\n\n"
        "명령창에서 아래를 한 번 실행해 주세요. "
        "(기존 데이터는 그대로 두고 새 표만 추가합니다)\n\n"
        "`python -m src.create_tables`"
    )
    st.stop()

pos = positions(trades, price_of, name_of, sector_of)
acct = summary(trades, cash, price_of)
현금 = acct["현금"]

# ── 연습 성적 계산 ───────────────────────────────────────────
# 수익률과 따로 계산합니다. 여기서 중요한 것은 번 돈이 아니라
# '어떻게 판단했는가' 이기 때문입니다. → src/practice.py
_, closed = walk(trades)
rev = reviews(closed, name_of)
습관 = habits(trades, closed, pos, acct["투자원금"])
연습점수 = overall(습관)
등급, 등급말 = grade(연습점수)

# ── 처음 오신 분 안내 ─────────────────────────────────────────
if cash.empty and trades.empty:
    st.info(
        "### 처음이시군요\n\n"
        "이곳은 **투자를 연습하는 곳**입니다. 돈을 벌어보는 곳이 아닙니다.\n\n"
        "**🎓 연습** 탭에 무엇부터 해볼지 순서대로 적어두었습니다. "
        "그대로 따라 해보시면 됩니다. 첫 번째 할 일은 **💵 예수금** 탭에서 "
        "연습에 쓸 돈을 넣는 것입니다."
    )

# 방금 사고팔거나 돈을 넣은 결과를 알려줍니다. (화면을 새로 그려도 남습니다)
show_flash()

# ── 계좌 현황 ─────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("총자산", money(acct["총자산"]),
          help="현금 + 지금 들고 있는 종목의 평가금액")
c2.metric("현금", money(현금), help="아직 안 쓴 돈")

손익 = acct["총손익"]
수익률 = acct["총수익률(%)"]
# 수익률이 아주 작으면 '-0.00%' 처럼 찍혀 오류로 보입니다. 그럴 땐 아예 감춥니다.
delta_txt = (None if 수익률 is None or abs(수익률) < 0.01
             else f"{수익률:+,.2f}%")
c3.metric("총손익", signed(손익), delta=delta_txt,
          help="총자산 − 내가 넣은 돈. **연습에서는 이 숫자가 가장 덜 중요합니다.**")

# ★ 네 번째 자리에 '투자원금' 대신 습관 점수를 둡니다 ★
#   어느 탭에 있든 '여기서 봐야 할 것은 수익률이 아니다' 가 보이도록.
# delta 로 등급을 넣으면 Streamlit 이 화살표(↑)를 함께 그립니다.
# '보통' 옆에 오르는 화살표가 붙으면 '점수가 올랐다'로 잘못 읽히므로
# 값 안에 등급을 같이 적습니다.
c4.metric(
    "판단 습관",
    "—" if 연습점수 is None else f"{연습점수:,.0f}점 · {등급}",
    help="기준을 정하고 지키는 습관을 0~100점으로 본 것입니다. "
         "**수익률과는 상관없습니다.** 자세한 내용은 🎓 연습 탭에 있습니다.",
)

st.divider()

# key 를 주면 고른 탭이 기억됩니다.
#   이게 없으면 사거나 팔 때마다 화면이 새로 그려지면서 첫 탭(🎓 연습)으로
#   튕겨 나갑니다. 연달아 두 종목을 사려면 매번 탭을 다시 눌러야 해서
#   연습이 끊깁니다.
tab_learn, tab_acct, tab_trade, tab_log, tab_cash = st.tabs(
    ["🎓 연습", "💼 내 계좌", "🛒 사고팔기", "🔍 복기", "💵 예수금"],
    key="paper_tabs",
)

# ══════════════════════════════════════════════════════════════
#  🎓 연습 — 무엇부터 해볼지 · 내 습관은 몇 점인지
# ══════════════════════════════════════════════════════════════
with tab_learn:
    st.markdown(
        "> **여기서 잘한다는 것은 돈을 많이 벌었다는 뜻이 아닙니다.**\n"
        "> 가짜 돈으로 낸 수익률은 대부분 운입니다. 운은 다음에 또 오지 않지만, "
        "습관은 실제 돈을 넣어도 똑같이 따라옵니다. 그래서 습관만 봅니다."
    )

    # ── ① 연습 단계 ──
    st.subheader("① 이 순서로 해보세요")
    todo = missions(trades, cash, pos, closed)
    끝난수 = sum(1 for m in todo if m["끝남"])
    st.progress(끝난수 / len(todo),
                text=f"{끝난수:,}단계 / {len(todo):,}단계 끝냈습니다")

    for m in todo:
        값 = f"  ·  지금 {m['지금값']}" if m["지금값"] else ""
        if m["끝남"]:
            st.markdown(
                f"<div class='mission done'>✅ <b>{m['제목']}</b>{값}</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='mission'>⬜ <b>{m['제목']}</b>{값}"
                f"<br><span class='mission-desc'>{m['설명']}</span></div>",
                unsafe_allow_html=True)

    st.caption(
        "순서대로 하지 않아도 됩니다. 다만 **팔 기준을 정하고 사보기** 와 "
        "**정한 기준대로 팔아보기** 는 꼭 해보세요. 실제 투자에서 초보자와 "
        "그렇지 않은 사람을 가르는 것이 거의 이 두 가지입니다."
    )

    # ── ② 습관 점수 ──
    st.divider()
    st.subheader("② 내 판단 습관")

    if 연습점수 is None:
        st.info(
            "아직 점수를 낼 자료가 없습니다. 한 종목이라도 사고팔아 보시면 "
            "여기에 습관이 나타납니다."
        )
    else:
        st.markdown(
            f"<div class='score-box'><span class='score-num'>{연습점수:,.0f}</span>"
            f"<span class='score-max'>/ 100점</span>"
            f"<span class='score-grade'>{등급}</span>"
            f"<div class='score-say'>{등급말}</div></div>",
            unsafe_allow_html=True,
        )

    for h in 습관:
        점 = h["점수"]
        if 점 is None:
            st.markdown(
                f"<div class='habit'><b>{h['항목']}</b>"
                f"<span class='habit-val'>{h['값글']}</span></div>",
                unsafe_allow_html=True)
            continue
        색 = "good" if 점 >= 80 else ("mid" if 점 >= 50 else "bad")
        st.markdown(
            f"<div class='habit'><b>{h['항목']}</b>"
            f"<span class='habit-score {색}'>{점:,.0f}점</span>"
            f"<span class='habit-val'>{h['값글']}</span>"
            f"<div class='habit-bar'><i class='{색}' style='width:{max(2, min(100, 점)):,.0f}%'></i></div>"
            f"</div>",
            unsafe_allow_html=True)
        # 잘하고 있는 항목까지 설명을 달면 화면이 길어지기만 합니다.
        # 고쳐야 할 것(80점 미만)에만 '왜 중요한지' 를 붙입니다.
        if 점 < 80:
            with st.expander(f"'{h['항목']}' 가 왜 중요한가요?"):
                st.markdown(h["말"])

    # ── ③ 지금 고칠 것 ──
    tips = coach(습관, rev)
    if tips:
        st.divider()
        st.subheader("③ 지금 하나만 고친다면")
        st.caption("고칠 것을 여러 개 주면 아무것도 안 고쳐집니다. 하나씩 올려보세요.")
        for t in tips:
            st.warning(t)

    st.divider()
    st.caption(
        "⚠️ 여기서 점수가 높다고 실제로도 잘된다는 뜻은 아닙니다. 진짜 돈이 걸리면 "
        "손이 떨리고, 원하는 가격에 사고팔지 못하는 일도 많습니다. "
        "다만 **여기서도 못 지키는 기준은 실제 돈으로는 절대 못 지킵니다.**"
    )

# ══════════════════════════════════════════════════════════════
#  💼 내 계좌
# ══════════════════════════════════════════════════════════════
with tab_acct:
    if pos.empty:
        st.info("아직 들고 있는 종목이 없습니다. **🛒 사고팔기** 탭에서 사보세요.")
    else:
        # ══ 살 때 정한 약속에 닿았는지 — 가장 먼저 보여줍니다 ══
        # 목표가·손절가를 적어두게 해놓고 아무도 안 보면 적는 의미가 없습니다.
        for a in alerts(pos):
            현재 = money(a["현재가"])
            기준 = money(a["기준가"])
            # 종목명 끝 글자에 맞춰 조사를 고릅니다 (가나반도체가 / 가나전자가)
            이름 = josa(str(a["종목명"]), "이/가")
            if a["종류"] == "손절":
                st.error(
                    f"🔻 **{이름}** 손절가 아래로 내려왔습니다 "
                    f"(지금 {현재} · 정해둔 손절가 {기준})\n\n{a['말']}"
                )
            else:
                st.success(
                    f"🎯 **{이름}** 목표가에 닿았습니다 "
                    f"(지금 {현재} · 정해둔 목표가 {기준})\n\n{a['말']}"
                )

        st.subheader("들고 있는 종목")

        # 쏠림 경고 (숫자보다 위험이 먼저입니다)
        for w in concentration_warnings(pos):
            st.warning(
                f"⚠️ {w}\n\n"
                "한 곳에 몰아넣으면 그 회사가 잘못됐을 때 회복할 방법이 없습니다. "
                "분산은 돈을 더 버는 방법이 아니라 **크게 망하지 않는 방법**입니다."
            )

        # 보유 종목에 붙은 위험 신호 (대시보드와 같은 기준 → src/risk.py)
        risk_lines = []
        for _, r in pos.iterrows():
            fl = flags_of.get(r["종목코드"])
            if isinstance(fl, (list, tuple)) and fl:
                # 이 줄은 HTML 로 그리므로 마크다운 ** 대신 <b> 를 씁니다.
                # (** 를 쓰면 별표가 화면에 그대로 보입니다)
                risk_lines.append(
                    f"<b>{r['종목명']}</b> {badges_html(fl)}"
                )
        if risk_lines:
            st.markdown(
                "<div class='risk-box'>⚠️ 들고 있는 종목에 붙은 신호<br>"
                + "<br>".join(risk_lines) + "</div>",
                unsafe_allow_html=True,
            )
            st.caption(
                "이 신호는 '팔라'는 뜻이 아니라 '왜 들고 있는지 다시 확인하라'는 "
                "표시입니다. 자세한 뜻은 대시보드 📊 차트 탭에서 볼 수 있습니다."
            )

        # ── 표 ──
        # 값이 없는 칸에 'None' 이 찍히지 않도록 미리 글자로 바꿉니다. → src/ui_table.py
        SHOW = ["종목명", "종목코드", "수량", "평균단가", "현재가",
                "평가금액", "평가손익", "수익률(%)", "비중(%)",
                "목표가", "손절가", "보유일"]
        HELPS = {
            "평균단가": "산 가격의 평균입니다. 수수료까지 포함한 값이라 "
                       "'실제로 1주에 얼마 들었는지'를 뜻합니다.",
            "평가손익": "아직 팔지 않았으므로 확정된 돈이 아닙니다. "
                       "팔면 수수료와 세금이 더 빠집니다.",
            "비중(%)": "들고 있는 것 전체에서 이 종목이 차지하는 몫",
            "목표가": "살 때 '여기까지 오르면 팔겠다'고 정한 가격입니다.",
            "손절가": "살 때 '여기까지 내리면 팔겠다'고 정한 가격입니다.",
            "보유일": "처음 산 날부터 오늘까지 며칠 지났는지",
        }
        LABELS = {"수량": "수량(주)", "평균단가": "평균단가(원)", "현재가": "현재가(원)",
                  "평가금액": "평가금액(원)", "평가손익": "평가손익(원)",
                  "목표가": "목표가(원)", "손절가": "손절가(원)", "보유일": "보유(일)"}

        src = pos[SHOW]
        st.dataframe(
            as_text(src, SHOW),
            width="stretch",
            hide_index=True,
            column_config=text_columns(src, SHOW, helps=HELPS, labels=LABELS),
        )

        st.caption(
            "**평가손익은 아직 내 돈이 아닙니다.** 팔아야 확정됩니다. "
            "그리고 팔 때 수수료와 증권거래세가 빠지므로, 실제로 손에 쥐는 돈은 "
            "여기 적힌 것보다 조금 적습니다."
        )

        # 비중 원그래프
        chart = pos.dropna(subset=["평가금액"])
        if len(chart) >= 2:
            fig = go.Figure(go.Pie(
                labels=chart["종목명"], values=chart["평가금액"],
                hole=0.45, textinfo="label+percent",
                hovertemplate="%{label}<br>%{value:,.0f}원 (%{percent})<extra></extra>",
            ))
            fig.update_layout(
                height=320, margin=dict(l=6, r=6, t=36, b=6), showlegend=False,
                title=dict(text="무엇에 얼마나 들어가 있나", font=dict(size=13)),
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # ── 성적표 ──
    st.divider()
    st.subheader("지금까지 성적")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("실현손익", signed(acct["실현손익"]),
              help="이미 팔아서 확정된 손익입니다.")
    m2.metric("평가손익", signed(acct["평가손익"]),
              help="아직 안 판 종목의 손익입니다. 확정된 것이 아닙니다.")
    지킨 = int(rev["잘함"].sum()) if not rev.empty else 0
    m3.metric("계획대로 판 횟수",
              "—" if rev.empty else f"{지킨:,} / {len(rev):,}번",
              help="살 때 정한 목표가·손절가대로 팔았는지. "
                   "**연습에서는 승률보다 이 숫자가 중요합니다.**")
    m4.metric("낸 비용", money(acct["비용합계"]),
              help="수수료와 증권거래세를 모두 더한 금액입니다. "
                   "사고팔 때마다 벌든 잃든 나갑니다.")

    if acct["매도횟수"] >= 3:
        승률 = acct["승률(%)"]
        승률글 = "—" if 승률 is None else f"{승률:,.0f}%"
        st.caption(
            f"참고 — 판 횟수 {acct['매도횟수']:,}번 · 이긴 {acct['이긴횟수']:,}번 / "
            f"진 {acct['진횟수']:,}번 (승률 {승률글})\n\n"
            "**승률이 높다고 잘하는 것은 아닙니다.** 조금씩 여러 번 이기고 "
            "한 번 크게 지면 결국 손해입니다. 그리고 몇 번 안 되는 매매에서 "
            "승률은 대부분 운입니다. 🎓 연습 탭의 **판단 습관** 을 보세요."
        )

# ══════════════════════════════════════════════════════════════
#  🛒 사고팔기
# ══════════════════════════════════════════════════════════════
with tab_trade:
    buy_tab, sell_tab = st.tabs(["🔴 사기", "🔵 팔기"], key="paper_side")

    # ── 사기 ──
    with buy_tab:
        st.caption(f"쓸 수 있는 현금: **{money(현금)}**")

        q = st.text_input(
            "살 종목 찾기",
            key="buy_q",
            placeholder="이름 · 종목코드 · 초성   (예: 삼성전자, 005930, ㅅㅅㅈㅈ)",
        )

        hits = search(market, q, limit=8) if q.strip() else market.head(0)

        if q.strip() and hits.empty:
            st.info(f"'{q}' 로 찾은 종목이 없습니다.")
        elif not hits.empty:
            label_of = {
                f"{r['종목명']} ({r['종목코드']})": r["종목코드"]
                for _, r in hits.iterrows()
            }
            picked_label = st.radio(
                "종목 고르기", list(label_of.keys()), horizontal=True, key="buy_pick"
            )
            code = label_of[picked_label]
            now = price_of.get(code)

            if now is None:
                st.warning("이 종목은 최신 시세가 없어 살 수 없습니다.")
            else:
                st.markdown(f"#### {name_of.get(code, code)}  `{code}`")
                st.caption(f"현재가 **{money(now)}**")

                b1, b2 = st.columns(2)
                buy_price = b1.number_input(
                    "살 가격 (1주, 원)", min_value=1, value=int(now), step=10,
                    key="buy_price",
                    help="지금 시세로 사는 것이 기본입니다. 바꿔서 연습해 볼 수도 있습니다.",
                )
                b1.caption(f"**{money(buy_price)}**{_in_words(buy_price)}")

                qty = b2.number_input("수량 (주)", min_value=1, value=1, step=1, key="buy_qty")
                b2.caption(f"**{qty:,}주**")

                amount = buy_price * qty
                fee, _ = costs(amount, "BUY")
                need = amount + fee

                st.markdown(
                    f"주문금액 **{money(amount)}** + 수수료 **{money(fee, 0)}** "
                    f"= 필요한 돈 **{money(need)}**"
                )

                st.markdown("##### 왜 사시나요?")
                st.caption(
                    "가장 가까운 것을 하나 고르세요. 나중에 **어떤 이유로 샀을 때 "
                    "잘 됐는지**를 종류별로 모아서 보여드립니다. 자기가 무엇 때문에 "
                    "잃는지 아는 것이 연습에서 가장 크게 남습니다."
                )
                buy_kind = st.radio(
                    "사는 이유 종류",
                    [k for k, _ in BUY_REASONS] + ["고르지 않음"],
                    horizontal=True, key="buy_kind",
                )
                설명 = dict(BUY_REASONS).get(buy_kind)
                if 설명:
                    st.caption(f"↳ {설명}")
                if buy_kind == "그냥 느낌으로":
                    # 솔직하게 고른 것을 나무라지 않습니다. 다만 이 종류가 나중에
                    # 어떤 성적을 내는지 직접 보게 되는 편이 훨씬 오래 남습니다.
                    st.info(
                        "솔직하게 고르셨습니다. 그대로 사셔도 됩니다. "
                        "이 종류로 산 것들이 나중에 어떤 성적을 냈는지 "
                        "🔍 복기 탭에서 직접 확인해 보세요."
                    )

                reason = st.text_area(
                    "덧붙일 말 (선택)",
                    key="buy_reason",
                    placeholder="예: 3년 PER 하위 10% 구간이고 매출이 3년째 늘고 있음. "
                                "반도체 업황 회복 기대.",
                    help="비워두셔도 됩니다. 적어두면 팔 때 다시 보여드립니다.",
                )
                if not reason.strip():
                    st.caption(
                        "비워두셔도 살 수 있습니다. 다만 한 줄이라도 적어두면 팔지 말지 "
                        "고민될 때 **'그때 왜 샀더라'** 를 다시 읽어볼 수 있습니다."
                    )

                t1, t2 = st.columns(2)
                target = t1.number_input(
                    "목표가 (원)", min_value=0, value=int(buy_price * 1.2), step=10,
                    key="buy_target",
                    help="여기까지 오르면 팔겠다는 가격입니다. 미리 정해두지 않으면 "
                         "오를 때 '더 오를까' 하다가 놓칩니다.",
                )
                stop = t2.number_input(
                    "손절가 (원)", min_value=0, value=int(buy_price * 0.9), step=10,
                    key="buy_stop",
                    help="여기까지 내리면 팔겠다는 가격입니다. 미리 정해두지 않으면 "
                         "내릴 때 '곧 오르겠지' 하다가 크게 잃습니다.",
                )

                # ── 살 수 있는지 확인 ──
                # 매수를 실제로 막는 것은 '현금 부족' 하나뿐입니다.
                # 없는 돈으로는 살 수 없기 때문입니다.
                # 나머지(이유·목표가·손절가)는 알려주기만 하고 막지 않습니다.
                problems = []
                if need > 현금:
                    problems.append(
                        f"현금이 부족합니다. 필요한 돈 {money(need)} > 현금 {money(현금)}"
                    )
                for p in problems:
                    st.error(p)

                # 숫자가 앞뒤가 안 맞으면 알려만 줍니다 (사는 것은 그대로 됩니다)
                if stop and stop >= buy_price:
                    st.warning(
                        "손절가가 사는 가격보다 높거나 같습니다. "
                        "손절가는 '여기까지 내리면 팔겠다'는 가격이라 보통 더 낮습니다."
                    )
                if target and target <= buy_price:
                    st.warning(
                        "목표가가 사는 가격보다 낮거나 같습니다. "
                        "목표가는 '여기까지 오르면 팔겠다'는 가격이라 보통 더 높습니다."
                    )

                if st.button("🔴 사기", type="primary", width="stretch",
                             disabled=bool(problems), key="do_buy"):
                    with get_conn() as conn:
                        add_trade(
                            conn, trade_date=date.today(), code=code, side="BUY",
                            qty=int(qty), price=float(buy_price), fee=float(fee), tax=0.0,
                            reason=tag(
                                None if buy_kind == "고르지 않음" else buy_kind,
                                reason,
                            ),
                            target_price=float(target) or None,
                            stop_price=float(stop) or None,
                        )
                    # ★ 방금 스스로 한 약속을 다시 읽어줍니다 ★
                    #   사고 나면 목표가·손절가를 정했다는 사실 자체를 잊습니다.
                    #   글로 다시 보면 나중에 지킬 확률이 올라갑니다.
                    약속 = []
                    if target:
                        약속.append(f"**{money(target)}**이 되면 팔고,")
                    if stop:
                        약속.append(f"**{money(stop)}**까지 내리면 손절하기로")
                    맺음 = (" ".join(약속) + " 정했습니다.") if 약속 else \
                        "팔 기준은 정하지 않았습니다. 다음에는 정해보세요."
                    flash(
                        f"{name_of.get(code, code)} {int(qty):,}주를 "
                        f"{money(buy_price)}에 샀다고 기록했습니다.\n\n"
                        f"약속 — {맺음}"
                    )
                    st.rerun()

    # ── 팔기 ──
    with sell_tab:
        if pos.empty:
            st.info("들고 있는 종목이 없습니다.")
        else:
            label_of = {
                f"{r['종목명']} ({r['종목코드']}) — {int(r['수량']):,}주": r["종목코드"]
                for _, r in pos.iterrows()
            }
            picked_label = st.selectbox("팔 종목", list(label_of.keys()), key="sell_pick")
            code = label_of[picked_label]

            row = pos[pos["종목코드"] == code].iloc[0]
            have = int(row["수량"])
            avg = float(row["평균단가"])
            now = price_of.get(code, avg)

            s1, s2, s3 = st.columns(3)
            s1.metric("보유 수량", f"{have:,}주")
            s2.metric("평균단가", money(avg))
            s3.metric("현재가", money(now))

            # 목표가·손절가를 알려줍니다 (살 때 정한 약속을 상기시킵니다)
            mine = trades[(trades["code"] == code) & (trades["side"] == "BUY")]
            if not mine.empty:
                last_buy = mine.iloc[-1]
                tgt, stp = last_buy.get("target_price"), last_buy.get("stop_price")
                bits = []
                if pd.notna(tgt):
                    bits.append(f"목표가 **{money(tgt)}**")
                if pd.notna(stp):
                    bits.append(f"손절가 **{money(stp)}**")
                if bits:
                    st.info("살 때 정한 기준 — " + " · ".join(bits))
                산종류, 산메모 = untag(last_buy.get("reason"))
                if 산종류 or 산메모:
                    # ★ 팔기 직전에 '그때 왜 샀는지' 를 다시 보여줍니다 ★
                    #   파는 순간은 감정이 가장 앞서는 때입니다. 그때 처음의
                    #   생각을 눈으로 다시 읽는 것만으로 판단이 달라집니다.
                    with st.expander("💭 살 때 무슨 생각이었나요? (팔기 전에 한 번 보세요)",
                                     expanded=True):
                        if 산종류:
                            st.markdown(f"**{산종류}** 라서 샀습니다.")
                        if 산메모:
                            st.write(산메모)
                        st.caption(
                            "그때 생각한 이유가 **아직 그대로인가요?** "
                            "이유가 사라졌다면 파는 것이 맞습니다. "
                            "이유는 그대로인데 가격만 내렸다면, 파는 것이 아니라 "
                            "오히려 더 살 자리일 수도 있습니다. "
                            "가격이 아니라 이유를 보고 정하세요."
                        )

            v1, v2 = st.columns(2)
            sell_price = v1.number_input(
                "팔 가격 (1주, 원)", min_value=1, value=int(now), step=10, key="sell_price"
            )
            v1.caption(f"**{money(sell_price)}**{_in_words(sell_price)}")

            sell_qty = v2.number_input(
                "수량 (주)", min_value=1, max_value=have, value=have, step=1, key="sell_qty"
            )
            v2.caption(f"**{sell_qty:,}주** (가진 {have:,}주 중)")

            amount = sell_price * sell_qty
            fee, tax = costs(amount, "SELL")
            받는돈 = amount - fee - tax
            들인돈 = avg * sell_qty
            손익 = 받는돈 - 들인돈

            st.markdown(
                f"판 금액 **{money(amount)}** − 수수료 **{money(fee, 0)}** "
                f"− 거래세 **{money(tax, 0)}** = 손에 쥐는 돈 **{money(받는돈)}**"
            )
            st.markdown(
                f"산 값 **{money(들인돈)}** 대비 → 실현손익 **{signed(손익)}** "
                f"({(손익 / 들인돈 * 100) if 들인돈 else 0:+,.2f}%)"
            )

            st.markdown("##### 왜 파시나요?")
            st.caption(
                "이 답으로 **정한 기준대로 팔았는지**를 따집니다. "
                "'불안해서' 를 고르는 것이 부끄러운 일이 아닙니다. "
                "그렇게 적어둬야 내가 어디서 흔들리는지 보입니다."
            )
            sell_kind = st.radio(
                "파는 이유 종류",
                [k for k, _ in SELL_REASONS] + ["고르지 않음"],
                horizontal=True, key="sell_kind",
            )
            설명 = dict(SELL_REASONS).get(sell_kind)
            if 설명:
                st.caption(f"↳ {설명}")

            sell_reason = st.text_area(
                "덧붙일 말 (선택)", key="sell_reason",
                placeholder="예: 실적이 꺾여 처음 산 이유가 사라짐",
            )

            if st.button("🔵 팔기", type="primary", width="stretch", key="do_sell"):
                with get_conn() as conn:
                    add_trade(
                        conn, trade_date=date.today(), code=code, side="SELL",
                        qty=int(sell_qty), price=float(sell_price),
                        fee=float(fee), tax=float(tax),
                        reason=tag(
                            None if sell_kind == "고르지 않음" else sell_kind,
                            sell_reason,
                        ),
                    )
                flash(
                    f"{name_of.get(code, code)} {int(sell_qty):,}주를 "
                    f"{money(sell_price)}에 팔았다고 기록했습니다. "
                    f"실현손익 {signed(손익)}\n\n"
                    "**🔍 복기** 탭에서 이 매매가 계획대로였는지 바로 볼 수 있습니다."
                )
                st.rerun()

# ══════════════════════════════════════════════════════════════
#  🔍 복기 — 판 뒤에 '계획대로 했는지' 되돌아보는 곳
# ══════════════════════════════════════════════════════════════
with tab_log:
    if trades.empty:
        st.info("아직 매매 기록이 없습니다. 사고팔아 보면 여기서 되돌아볼 수 있습니다.")
    else:
        st.markdown(
            "> **복기가 연습의 절반입니다.**\n"
            "> 사고파는 것은 누구나 합니다. 끝난 뒤에 '내가 정한 대로 했는가' 를 "
            "따져보는 사람만 다음번에 달라집니다."
        )

        # ── ① 한 건씩 되짚기 ──
        st.subheader("① 판 거래 하나씩 되짚기")
        if rev.empty:
            st.caption(
                "아직 판 종목이 없습니다. 파는 순간이 사는 순간보다 훨씬 어렵고, "
                "연습이 가장 많이 되는 곳입니다."
            )
        else:
            잘한수 = int(rev["잘함"].sum())
            st.caption(
                f"판 {len(rev):,}번 중 **계획대로 한 것이 {잘한수:,}번** 입니다. "
                "돈을 벌었는지가 아니라, 살 때 정한 기준대로 했는지로 봅니다."
            )
            for _, r in rev.iterrows():
                날 = pd.Timestamp(r["판날"]).strftime("%Y-%m-%d") if pd.notna(r["판날"]) else ""
                계획 = []
                if pd.notna(r["목표가"]):
                    계획.append(f"목표 {float(r['목표가']):,.0f}원")
                if pd.notna(r["손절가"]):
                    계획.append(f"손절 {float(r['손절가']):,.0f}원")
                계획글 = " · ".join(계획) if 계획 else "정해둔 기준 없음"
                수익 = r["실현수익률(%)"]
                수익글 = f"{float(수익):+,.2f}%" if pd.notna(수익) else "—"
                보유 = f" · {int(r['보유일']):,}일 들고 있었습니다" \
                    if pd.notna(r["보유일"]) else ""
                st.markdown(
                    f"<div class='rv {'ok' if r['잘함'] else 'no'}'>"
                    f"<span class='rv-head'>{'✅' if r['잘함'] else '⚠️'} "
                    f"{r['종목명']} — {r['판정']}</span>"
                    f"<div class='rv-sub'>{날} · 계획 {계획글} → "
                    f"실제 {float(r['판가격']):,.0f}원에 팔았습니다 "
                    f"({signed(r['실현손익'])}, {수익글}){보유}<br>"
                    f"산 이유 <b>{r['산이유종류']}</b> → 판 이유 <b>{r['판이유종류']}</b>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
                st.caption(r["말"])

        # ── ② 이유 종류별 성적 ──
        st.divider()
        st.subheader("② 어떤 이유로 샀을 때 잘 됐나")
        if rev.empty:
            st.caption("판 거래가 쌓이면 여기에 나타납니다.")
        else:
            st.caption(
                "**여기가 이 화면에서 가장 값진 부분입니다.** 대부분의 사람은 자기가 "
                "무엇 때문에 잃는지 모릅니다. 종류별로 모아보면 보입니다. "
                "다만 **3번 미만은 운일 가능성이 크니** 참고만 하세요."
            )
            for col, 제목 in [("산이유종류", "살 때 이유별"), ("판이유종류", "팔 때 이유별")]:
                g = by_reason(rev, col)
                if g.empty:
                    continue
                st.markdown(f"**{제목}**")
                COLS = [col, "횟수", "이긴횟수", "승률(%)", "손익합계", "평균수익률(%)"]
                st.dataframe(
                    as_text(g, COLS), width="stretch", hide_index=True,
                    column_config=text_columns(
                        g, COLS,
                        labels={col: 제목.replace("별", ""), "횟수": "판 횟수",
                                "손익합계": "손익합계(원)"},
                        helps={"승률(%)": "이 종류로 산 것 중 이익을 본 비율",
                               "손익합계": "이 종류로 사고팔아 남은 돈의 합계"},
                    ),
                )

            # 가장 성적이 나쁜 이유 하나를 짚어줍니다.
            g = by_reason(rev, "산이유종류")
            충분 = g[g["횟수"] >= 3]
            if not 충분.empty:
                worst = 충분.iloc[-1]
                if float(worst["손익합계"]) < 0:
                    st.warning(
                        f"**'{worst['산이유종류']}'** 로 산 {int(worst['횟수']):,}번은 "
                        f"합쳐서 {signed(worst['손익합계'])} 입니다. "
                        "이 이유로 사는 것을 한동안 멈춰보는 것만으로 성적이 달라질 수 "
                        "있습니다."
                    )
                best = 충분.iloc[0]
                if float(best["손익합계"]) > 0 and best["산이유종류"] != worst["산이유종류"]:
                    st.success(
                        f"반대로 **'{best['산이유종류']}'** 로 산 "
                        f"{int(best['횟수']):,}번은 합쳐서 "
                        f"{signed(best['손익합계'])} 입니다. 나에게 맞는 방식일 수 "
                        "있으니, 다음에도 이 기준으로 찾아보세요."
                    )

        # ── ③ 모든 기록 ──
        st.divider()
        st.subheader("③ 모든 매매 기록")
        st.caption("적어둔 것을 그대로 보여줍니다. 잘못 적은 것은 아래에서 지울 수 있습니다.")

        log = trades.copy()
        log["종목명"] = log["code"].map(name_of).fillna(log["code"])
        log["날짜"] = log["trade_date"].dt.strftime("%Y-%m-%d")
        log["구분"] = log["side"].map({"BUY": "🔴 매수", "SELL": "🔵 매도"})
        log["금액"] = log["qty"] * log["price"]

        # 이유는 '[종류] 메모' 로 한 칸에 저장돼 있습니다. 읽기 좋게 나눕니다.
        log["이유종류"] = log["reason"].map(lambda t: untag(t)[0] or "")
        log["메모"] = log["reason"].map(lambda t: untag(t)[1])

        st.dataframe(
            log[["날짜", "구분", "종목명", "qty", "price", "금액",
                 "fee", "tax", "이유종류", "메모",
                 "target_price", "stop_price"]].iloc[::-1],
            width="stretch", hide_index=True,
            column_config={
                "qty": st.column_config.NumberColumn("수량", format="localized"),
                "price": st.column_config.NumberColumn("가격(원)", format="localized"),
                "금액": st.column_config.NumberColumn("금액(원)", format="localized"),
                "fee": st.column_config.NumberColumn("수수료", format="localized"),
                "tax": st.column_config.NumberColumn("거래세", format="localized"),
                "이유종류": st.column_config.TextColumn("이유 종류", width="medium"),
                "메모": st.column_config.TextColumn("덧붙인 말", width="large"),
                "target_price": st.column_config.NumberColumn("목표가", format="localized"),
                "stop_price": st.column_config.NumberColumn("손절가", format="localized"),
            },
        )

        with st.expander("잘못 적은 기록 지우기"):
            st.caption(
                "지우면 되돌릴 수 없습니다. 보유 수량과 현금은 남은 기록으로 "
                "다시 계산됩니다."
            )
            opts = {
                f"[{r['날짜']}] {r['구분']} {r['종목명']} "
                f"{int(r['qty']):,}주 @ {float(r['price']):,.0f}원  (#{int(r['id'])})":
                int(r["id"])
                for _, r in log.iloc[::-1].iterrows()
            }
            target_label = st.selectbox("지울 기록", list(opts.keys()), key="del_trade")
            if st.button("이 기록 지우기", key="do_del_trade"):
                with get_conn() as conn:
                    delete_trade(conn, opts[target_label])
                flash("지웠습니다.")
                st.rerun()

# ══════════════════════════════════════════════════════════════
#  💵 예수금
# ══════════════════════════════════════════════════════════════
with tab_cash:
    st.subheader("연습에 쓸 돈 넣기 / 빼기")
    st.caption(
        "실제로 투자할 만한 금액으로 하시는 편이 연습이 됩니다. "
        "1억으로 연습하면 실제 감각과 달라집니다."
    )

    d1, d2 = st.columns(2)
    amount = d1.number_input(
        "금액 (원)", min_value=0, value=1_000_000, step=100_000, key="cash_amt"
    )
    # 입력칸 자체에는 자릿수 구분기호를 넣을 수 없습니다(Streamlit 제한).
    # 그래서 입력한 금액을 바로 아래에 읽기 쉬운 형태로 다시 적어줍니다.
    #   1000000 → "1,000,000원 (백만원)"
    d1.caption(f"**{money(amount)}**{_in_words(amount)}")

    direction = d2.radio("구분", ["넣기 (입금)", "빼기 (출금)"],
                         horizontal=True, key="cash_dir")
    memo = st.text_input("메모 (선택)", key="cash_memo", placeholder="예: 연습 시작 자금")

    out = direction.startswith("빼기")
    if out and amount > 현금:
        st.error(f"현금이 부족합니다. 지금 현금은 {money(현금)} 입니다.")
    elif st.button("기록하기", type="primary", key="do_cash"):
        with get_conn() as conn:
            add_cash(conn, cash_date=date.today(),
                     amount=(-amount if out else amount),
                     memo=(memo.strip() or None))
        flash(f"{money(amount)} {'출금' if out else '입금'}으로 기록했습니다.")
        st.rerun()

    if not cash.empty:
        st.divider()
        st.subheader("입출금 기록")
        cs = cash.copy()
        cs["날짜"] = cs["cash_date"].dt.strftime("%Y-%m-%d")
        cs["구분"] = cs["amount"].map(lambda a: "입금" if a >= 0 else "출금")
        cs["금액(원)"] = cs["amount"].abs()
        st.dataframe(
            cs[["날짜", "구분", "금액(원)", "memo"]].iloc[::-1],
            width="stretch", hide_index=True,
            column_config={
                "금액(원)": st.column_config.NumberColumn(format="localized"),
                "memo": st.column_config.TextColumn("메모", width="medium"),
            },
        )

        with st.expander("잘못 적은 입출금 지우기"):
            opts = {
                f"[{r['날짜']}] {r['구분']} {float(r['금액(원)']):,.0f}원  (#{int(r['id'])})":
                int(r["id"])
                for _, r in cs.iloc[::-1].iterrows()
            }
            pick = st.selectbox("지울 기록", list(opts.keys()), key="del_cash")
            if st.button("이 기록 지우기", key="do_del_cash"):
                with get_conn() as conn:
                    delete_cash(conn, opts[pick])
                flash("지웠습니다.")
                st.rerun()

st.divider()
st.caption(
    f"수수료 {DEFAULT_FEE_RATE}% (살 때·팔 때) · 증권거래세 {DEFAULT_TAX_RATE}% (팔 때만) 기준으로 "
    "계산합니다. 실제 증권사 요율과 세율은 다를 수 있고 해마다 바뀝니다.\n\n"
    "⚠️ 여기서 잘된다고 실제로도 잘된다는 뜻은 아닙니다. 진짜 돈이 걸리면 "
    "판단이 달라지고, 원하는 가격에 사고팔지 못하는 경우도 많습니다. "
    "**연습의 목적은 돈을 버는 것이 아니라, 실제 돈을 넣기 전에 내 버릇을 "
    "미리 알아두는 것입니다.**"
)
