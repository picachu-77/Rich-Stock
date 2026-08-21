# -*- coding: utf-8 -*-
"""
모의투자(가상 매매) 화면 — 진짜 돈을 쓰기 전에 연습하는 곳.

여기서 하는 일
  실제로 사지 않고 '샀다 치고' 기록만 남깁니다. 그리고 지금 시세로
  얼마가 됐을지 계산해서 보여줍니다.

왜 필요한가요?
  머릿속으로 "그때 샀으면 벌었을 텐데" 하는 기억은 거의 항상 실제보다
  후합니다. 잘된 것만 기억하고 틀린 것은 잊기 때문입니다.
  적어두어야만 내 판단이 실제로 어땠는지 알 수 있습니다.

살 때 이유를 적어두길 권합니다
  이유 없이 산 종목은 팔 때도 기준이 없습니다. 다만 매번 적기 번거로우므로
  적지 않아도 살 수 있게 두었습니다. 적어두면 팔 때 다시 보여드립니다.

  실제로 매수를 막는 것은 '현금 부족' 하나뿐입니다.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.db import get_conn
from src.market_data import load_overview
from src.paper import (
    DEFAULT_FEE_RATE,
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
from src.search import search
from src.ui_korean import apply_korean_ui
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


def signed(v, digits: int = 0) -> str:
    """손익처럼 부호가 중요한 값."""
    if v is None or pd.isna(v):
        return "—"
    return f"{float(v):+,.{digits}f}원"


st.title("💰 모의투자")
st.caption(
    "**진짜 돈은 한 푼도 쓰지 않습니다.** 사고팔았다고 적어두면, 지금 시세로 "
    "얼마가 됐을지 계산해서 보여줍니다. 실제로 사기 전에 내 판단을 시험해 보는 곳입니다."
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

price_of = {
    r["종목코드"]: (float(r["종가"]) if pd.notna(r["종가"]) else None)
    for _, r in market.iterrows()
}
price_of = {k: v for k, v in price_of.items() if v is not None}
name_of = dict(zip(market["종목코드"], market["종목명"]))
sector_of = dict(zip(market["종목코드"], market.get("업종", pd.Series(dtype=str))))

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

# ── 처음 오신 분 안내 ─────────────────────────────────────────
if cash.empty and trades.empty:
    st.info(
        "### 시작해 볼까요?\n\n"
        "먼저 **💵 예수금** 탭에서 연습에 쓸 돈을 넣어주세요. "
        "실제 투자할 만한 금액으로 하시는 편이 연습이 됩니다. "
        "(너무 큰 돈으로 하면 실제 감각과 달라집니다)\n\n"
        "그다음 **🛒 사고팔기** 탭에서 종목을 골라 사시면 됩니다."
    )

# ── 계좌 현황 ─────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("총자산", money(acct["총자산"]),
          help="현금 + 지금 들고 있는 종목의 평가금액")
c2.metric("현금", money(현금), help="아직 안 쓴 돈")

손익 = acct["총손익"]
수익률 = acct["총수익률(%)"]
# 수익률이 아주 작으면 '-0.00%' 처럼 찍혀 오류로 보입니다. 그럴 땐 아예 감춥니다.
delta_txt = (None if 수익률 is None or abs(수익률) < 0.01
             else f"{수익률:+.2f}%")
c3.metric("총손익", signed(손익), delta=delta_txt,
          help="총자산 − 내가 넣은 돈")
c4.metric("투자원금", money(acct["투자원금"]), help="예수금으로 넣은 돈의 합계")

st.divider()

tab_acct, tab_trade, tab_log, tab_cash = st.tabs(
    ["💼 내 계좌", "🛒 사고팔기", "📔 거래 내역", "💵 예수금"]
)

# ══════════════════════════════════════════════════════════════
#  💼 내 계좌
# ══════════════════════════════════════════════════════════════
with tab_acct:
    if pos.empty:
        st.info("아직 들고 있는 종목이 없습니다. **🛒 사고팔기** 탭에서 사보세요.")
    else:
        st.subheader("들고 있는 종목")

        # 쏠림 경고를 표보다 먼저 보여줍니다 (숫자보다 위험이 먼저입니다)
        for w in concentration_warnings(pos):
            st.warning(
                f"⚠️ {w}\n\n"
                "한 곳에 몰아넣으면 그 회사가 잘못됐을 때 회복할 방법이 없습니다. "
                "분산은 돈을 더 버는 방법이 아니라 **크게 망하지 않는 방법**입니다."
            )

        show = pos.copy()
        st.dataframe(
            show[["종목명", "종목코드", "수량", "평균단가", "현재가",
                  "평가금액", "평가손익", "수익률(%)", "비중(%)"]],
            width="stretch",
            hide_index=True,
            column_config={
                "수량": st.column_config.NumberColumn("수량(주)", format="localized"),
                "평균단가": st.column_config.NumberColumn(
                    "평균단가(원)", format="localized",
                    help="산 가격의 평균입니다. 수수료까지 포함한 값이라 "
                         "'실제로 1주에 얼마 들었는지'를 뜻합니다."),
                "현재가": st.column_config.NumberColumn("현재가(원)", format="localized"),
                "평가금액": st.column_config.NumberColumn("평가금액(원)", format="localized"),
                "평가손익": st.column_config.NumberColumn(
                    "평가손익(원)", format="localized",
                    help="아직 팔지 않았으므로 확정된 돈이 아닙니다. "
                         "팔면 수수료와 세금이 더 빠집니다."),
                "수익률(%)": st.column_config.NumberColumn("수익률(%)", format="localized"),
                "비중(%)": st.column_config.NumberColumn(
                    "비중(%)", format="localized",
                    help="들고 있는 것 전체에서 이 종목이 차지하는 몫"),
            },
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
    승률 = acct["승률(%)"]
    m3.metric("승률", "—" if 승률 is None else f"{승률:.0f}%",
              help=f"판 {acct['매도횟수']}번 중 이익을 본 횟수의 비율")
    m4.metric("낸 비용", money(acct["비용합계"]),
              help="수수료와 증권거래세를 모두 더한 금액입니다.")

    if acct["매도횟수"] >= 3:
        st.caption(
            f"판 횟수 {acct['매도횟수']}번 · 이긴 {acct['이긴횟수']}번 / "
            f"진 {acct['진횟수']}번\n\n"
            "**승률이 높다고 잘하는 것은 아닙니다.** 조금씩 여러 번 이기고 "
            "한 번 크게 지면 결국 손해입니다. 승률보다 **실현손익 합계**를 보세요."
        )

# ══════════════════════════════════════════════════════════════
#  🛒 사고팔기
# ══════════════════════════════════════════════════════════════
with tab_trade:
    buy_tab, sell_tab = st.tabs(["🔴 사기", "🔵 팔기"])

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
                qty = b2.number_input("수량 (주)", min_value=1, value=1, step=1, key="buy_qty")

                amount = buy_price * qty
                fee, _ = costs(amount, "BUY")
                need = amount + fee

                st.markdown(
                    f"주문금액 **{money(amount)}** + 수수료 **{money(fee, 0)}** "
                    f"= 필요한 돈 **{money(need)}**"
                )

                st.markdown("##### 왜 사시나요? (선택)")
                reason = st.text_area(
                    "사는 이유",
                    key="buy_reason",
                    placeholder="예: 3년 PER 하위 10% 구간이고 매출이 3년째 늘고 있음. "
                                "반도체 업황 회복 기대.",
                    help="적어두면 나중에 📔 거래 내역에서 다시 읽어볼 수 있습니다. "
                         "비워두고 사셔도 됩니다.",
                )
                if not reason.strip():
                    st.caption(
                        "비워두셔도 살 수 있습니다. 다만 한 줄이라도 적어두면 나중에 "
                        "**'그때 왜 샀더라'** 를 알 수 있어서, 같은 실수를 반복하는지 "
                        "확인할 수 있습니다."
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
                            reason=reason.strip(),
                            target_price=float(target) or None,
                            stop_price=float(stop) or None,
                        )
                    st.success(
                        f"{name_of.get(code, code)} {int(qty):,}주를 "
                        f"{money(buy_price)}에 샀다고 기록했습니다."
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
                if pd.notna(last_buy.get("reason")):
                    with st.expander("살 때 적은 이유 다시 보기"):
                        st.write(last_buy["reason"])
                        st.caption(
                            "그때 생각한 이유가 아직 유효한가요? "
                            "이유가 사라졌다면 파는 것이 맞고, 이유가 그대로인데 "
                            "주가만 내렸다면 파는 것이 성급할 수 있습니다."
                        )

            v1, v2 = st.columns(2)
            sell_price = v1.number_input(
                "팔 가격 (1주, 원)", min_value=1, value=int(now), step=10, key="sell_price"
            )
            sell_qty = v2.number_input(
                "수량 (주)", min_value=1, max_value=have, value=have, step=1, key="sell_qty"
            )

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
                f"({(손익 / 들인돈 * 100) if 들인돈 else 0:+.2f}%)"
            )

            sell_reason = st.text_area(
                "파는 이유", key="sell_reason",
                placeholder="예: 목표가에 도달함 / 실적이 나빠져 처음 산 이유가 사라짐",
            )

            if st.button("🔵 팔기", type="primary", width="stretch", key="do_sell"):
                with get_conn() as conn:
                    add_trade(
                        conn, trade_date=date.today(), code=code, side="SELL",
                        qty=int(sell_qty), price=float(sell_price),
                        fee=float(fee), tax=float(tax),
                        reason=(sell_reason.strip() or None),
                    )
                st.success(
                    f"{name_of.get(code, code)} {int(sell_qty):,}주를 "
                    f"{money(sell_price)}에 팔았다고 기록했습니다. "
                    f"실현손익 {signed(손익)}"
                )
                st.rerun()

# ══════════════════════════════════════════════════════════════
#  📔 거래 내역
# ══════════════════════════════════════════════════════════════
with tab_log:
    if trades.empty:
        st.info("아직 매매 기록이 없습니다.")
    else:
        _, closed = walk(trades)

        st.subheader("팔아서 확정된 손익")
        if not closed:
            st.caption("아직 판 종목이 없습니다.")
        else:
            cl = pd.DataFrame(closed)
            cl["종목명"] = cl["종목코드"].map(name_of).fillna(cl["종목코드"])
            cl["판날"] = pd.to_datetime(cl["판날"]).dt.strftime("%Y-%m-%d")
            st.dataframe(
                cl[["판날", "종목명", "수량", "평균단가", "판가격",
                    "실현손익", "실현수익률(%)", "이유"]].iloc[::-1],
                width="stretch", hide_index=True,
                column_config={
                    c: st.column_config.NumberColumn(c, format="localized")
                    for c in ["수량", "평균단가", "판가격", "실현손익", "실현수익률(%)"]
                },
            )

        st.divider()
        st.subheader("모든 매매 기록")
        st.caption(
            "살 때 적은 이유를 다시 읽어보세요. **판단이 맞았는지 틀렸는지보다, "
            "어떤 이유로 살 때 잘 되었는지**를 보는 것이 훨씬 도움이 됩니다."
        )

        log = trades.copy()
        log["종목명"] = log["code"].map(name_of).fillna(log["code"])
        log["날짜"] = log["trade_date"].dt.strftime("%Y-%m-%d")
        log["구분"] = log["side"].map({"BUY": "🔴 매수", "SELL": "🔵 매도"})
        log["금액"] = log["qty"] * log["price"]

        st.dataframe(
            log[["날짜", "구분", "종목명", "qty", "price", "금액",
                 "fee", "tax", "reason", "target_price", "stop_price"]].iloc[::-1],
            width="stretch", hide_index=True,
            column_config={
                "qty": st.column_config.NumberColumn("수량", format="localized"),
                "price": st.column_config.NumberColumn("가격(원)", format="localized"),
                "금액": st.column_config.NumberColumn("금액(원)", format="localized"),
                "fee": st.column_config.NumberColumn("수수료", format="localized"),
                "tax": st.column_config.NumberColumn("거래세", format="localized"),
                "reason": st.column_config.TextColumn("이유", width="large"),
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
                st.success("지웠습니다.")
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
        st.success(f"{money(amount)} {'출금' if out else '입금'}으로 기록했습니다.")
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
                st.success("지웠습니다.")
                st.rerun()

st.divider()
st.caption(
    f"수수료 {DEFAULT_FEE_RATE}% (살 때·팔 때) · 증권거래세 {DEFAULT_TAX_RATE}% (팔 때만) 기준으로 "
    "계산합니다. 실제 증권사 요율과 세율은 다를 수 있고 해마다 바뀝니다.\n\n"
    "⚠️ 여기서 잘된다고 실제로도 잘된다는 뜻은 아닙니다. 진짜 돈이 걸리면 "
    "판단이 달라지고, 원하는 가격에 사고팔지 못하는 경우도 많습니다."
)
