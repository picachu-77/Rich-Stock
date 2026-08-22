# -*- coding: utf-8 -*-
"""
모의투자(가상 매매) 계산을 담당하는 파일.

이게 뭔가요?
  진짜 돈은 한 푼도 쓰지 않고, '샀다 치고' 기록만 남기는 기능입니다.
  실제로 사기 전에 내 판단이 맞는지 확인해 보는 연습장입니다.

왜 필요한가요?
  머릿속으로 "그때 샀으면 벌었을 텐데" 라고 생각하는 것은 거의 항상
  실제보다 후하게 기억됩니다. 적어두지 않으면 내 판단이 좋았는지
  나빴는지 영원히 알 수 없습니다.

  그래서 이 기능은 살 때 **왜 사는지·목표가·손절가**를 함께 적을 수 있게
  해두었습니다. 적지 않아도 살 수 있지만, 적어두면 나중에 그 기록을 다시 볼 때
  내가 어떤 실수를 반복하는지 보입니다.

★ 보유 수량과 현금을 따로 저장하지 않습니다 ★
  매매 기록에서 매번 다시 계산합니다. 잔고를 따로 저장해두면 기록과
  어긋나는 순간 어느 쪽이 맞는지 알 수 없게 되기 때문입니다.
"""

from __future__ import annotations

import warnings
from datetime import date

import pandas as pd
import streamlit as st

from src.db import get_conn

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)

# 기본 수수료·세금 (🧮 계산기 화면과 같은 값입니다)
DEFAULT_FEE_RATE = 0.015   # 증권사 수수료 (%) — 살 때·팔 때 각각
DEFAULT_TAX_RATE = 0.18    # 증권거래세 (%) — 팔 때만, 손해를 봐도 냅니다


# ── 읽기 ──────────────────────────────────────────────────────
def load_trades(conn=None) -> pd.DataFrame:
    """매매 기록을 오래된 것부터 가져옵니다. (계산 순서가 중요합니다)"""
    sql = """
        SELECT id, trade_date, code, side, qty, price, fee, tax,
               reason, target_price, stop_price
          FROM paper_trade
         ORDER BY trade_date, id;
    """
    cols = ["id", "trade_date", "code", "side", "qty", "price", "fee", "tax",
            "reason", "target_price", "stop_price"]
    try:
        if conn is not None:
            df = pd.read_sql(sql, conn)
        else:
            with get_conn() as c:
                df = pd.read_sql(sql, c)
    except Exception:  # noqa: BLE001
        # 표가 아직 없어도 화면이 멈추지 않게 합니다.
        return pd.DataFrame(columns=cols)

    if df.empty:
        return pd.DataFrame(columns=cols)

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    for c in ["qty"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    for c in ["price", "fee", "tax", "target_price", "stop_price"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[["fee", "tax"]] = df[["fee", "tax"]].fillna(0.0)
    return df


def load_cash(conn=None) -> pd.DataFrame:
    """예수금 입출금 기록을 가져옵니다."""
    sql = "SELECT id, cash_date, amount, memo FROM paper_cash ORDER BY cash_date, id;"
    try:
        if conn is not None:
            df = pd.read_sql(sql, conn)
        else:
            with get_conn() as c:
                df = pd.read_sql(sql, c)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["id", "cash_date", "amount", "memo"])

    if df.empty:
        return pd.DataFrame(columns=["id", "cash_date", "amount", "memo"])
    df["cash_date"] = pd.to_datetime(df["cash_date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df


# ── 쓰기 ──────────────────────────────────────────────────────
def costs(amount: float, side: str,
          fee_rate: float = DEFAULT_FEE_RATE,
          tax_rate: float = DEFAULT_TAX_RATE) -> tuple[float, float]:
    """
    거래 금액에 붙는 수수료와 세금을 계산합니다.

    수수료는 살 때·팔 때 모두 붙고, 증권거래세는 **팔 때만** 붙습니다.
    (그리고 손해를 봐도 냅니다 — 판 금액 기준으로 떼어가기 때문입니다)
    """
    fee = round(amount * fee_rate / 100, 2)
    tax = round(amount * tax_rate / 100, 2) if side == "SELL" else 0.0
    return fee, tax


def add_trade(conn, *, trade_date: date, code: str, side: str, qty: int,
              price: float, fee: float, tax: float,
              reason: str | None = None,
              target_price: float | None = None,
              stop_price: float | None = None) -> None:
    """매매 한 건을 기록합니다."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO paper_trade
                (trade_date, code, side, qty, price, fee, tax,
                 reason, target_price, stop_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (trade_date, code, side, int(qty), float(price), float(fee), float(tax),
             reason, target_price, stop_price),
        )


def add_cash(conn, *, cash_date: date, amount: float, memo: str | None = None) -> None:
    """예수금을 넣거나 뺍니다. (amount 가 음수면 출금)"""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO paper_cash (cash_date, amount, memo) VALUES (%s, %s, %s);",
            (cash_date, float(amount), memo),
        )


def delete_trade(conn, trade_id: int) -> None:
    """잘못 적은 매매 기록을 지웁니다."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM paper_trade WHERE id = %s;", (int(trade_id),))


def delete_cash(conn, cash_id: int) -> None:
    """잘못 적은 입출금 기록을 지웁니다."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM paper_cash WHERE id = %s;", (int(cash_id),))


# ── 계산 ──────────────────────────────────────────────────────
def walk(trades: pd.DataFrame) -> tuple[dict[str, dict], list[dict]]:
    """
    매매 기록을 처음부터 훑으면서 보유 상태와 실현손익을 계산합니다.

    평균단가는 **이동평균법**으로 계산합니다.
      살 때마다 '들어간 돈 전부 ÷ 가진 수량' 으로 평균을 다시 냅니다.
      팔 때는 평균단가를 그대로 두고 수량만 줄입니다.

      예) 1만원에 10주 산 뒤 2만원에 10주 더 사면
          평균단가 = (10만 + 20만) ÷ 20주 = 1만 5천원

    수수료는 평균단가에 포함시킵니다. 실제로 나간 돈이기 때문입니다.

    돌려주는 값
      held    : {종목코드: {수량, 취득원가, 평균단가}}
      closed  : 팔아서 확정된 손익 목록
    """
    held: dict[str, dict] = {}
    closed: list[dict] = []

    if trades.empty:
        return held, closed

    for _, t in trades.iterrows():
        code = str(t["code"])
        qty = int(t["qty"])
        price = float(t["price"])
        fee = float(t["fee"] or 0)
        tax = float(t["tax"] or 0)

        pos = held.setdefault(
            code,
            {"수량": 0, "취득원가": 0.0, "평균단가": 0.0,
             "보유시작": None, "목표가": None, "손절가": None, "산이유": None},
        )

        if t["side"] == "BUY":
            # 다 팔았다가 다시 사면 '보유 기간' 은 그때부터 새로 셉니다.
            if pos["수량"] == 0:
                pos["보유시작"] = t["trade_date"]
            pos["수량"] += qty
            pos["취득원가"] += qty * price + fee
            pos["평균단가"] = pos["취득원가"] / pos["수량"] if pos["수량"] else 0.0
            # 살 때 정한 목표가·손절가는 가장 최근 것을 기준으로 둡니다.
            if pd.notna(t.get("target_price")):
                pos["목표가"] = float(t["target_price"])
            if pd.notna(t.get("stop_price")):
                pos["손절가"] = float(t["stop_price"])
            # 살 때 적은 이유도 들고 있습니다. 팔 때 '그때 왜 샀는지' 를
            # 나란히 보여주어야 복기가 됩니다.
            if pd.notna(t.get("reason")) and str(t.get("reason")).strip():
                pos["산이유"] = str(t["reason"]).strip()
            continue

        # ── 팔 때 ──
        # 가진 것보다 많이 팔 수는 없습니다. (화면에서 막지만 계산에서도 지킵니다)
        sell_qty = min(qty, pos["수량"])
        if sell_qty <= 0:
            continue

        avg = pos["평균단가"]
        받은돈 = sell_qty * price - fee - tax     # 실제로 손에 들어온 돈
        들인돈 = avg * sell_qty                    # 그 수량을 사는 데 들었던 돈
        closed.append({
            "판날": t["trade_date"],
            "종목코드": code,
            "수량": sell_qty,
            "판가격": price,
            "평균단가": avg,
            "실현손익": 받은돈 - 들인돈,
            "실현수익률(%)": ((받은돈 / 들인돈 - 1) * 100) if 들인돈 else None,
            "이유": t.get("reason"),
            # ── 아래는 '복기' 화면에서 쓰는 값입니다 ──
            #   살 때 세운 계획을 함께 남겨두어야, 나중에 '계획대로 했는지'
            #   를 따져볼 수 있습니다. 팔고 나면 계획은 지워지기 때문에
            #   여기서 같이 적어둡니다.
            "목표가": pos.get("목표가"),
            "손절가": pos.get("손절가"),
            "산이유": pos.get("산이유"),
            "산날": pos.get("보유시작"),
            "보유일": ((t["trade_date"] - pos["보유시작"]).days
                       if pos.get("보유시작") is not None else None),
        })

        pos["수량"] -= sell_qty
        pos["취득원가"] = avg * pos["수량"]
        if pos["수량"] == 0:
            pos["평균단가"] = 0.0
            pos["보유시작"] = None
            pos["목표가"] = None
            pos["손절가"] = None
            pos["산이유"] = None

    return held, closed


def cash_balance(trades: pd.DataFrame, cash: pd.DataFrame) -> float:
    """
    지금 남은 현금(예수금)을 계산합니다.

        넣은 돈 − 산 금액(수수료 포함) + 판 금액(수수료·세금 뺀 것)
    """
    total = float(cash["amount"].sum()) if not cash.empty else 0.0

    if trades.empty:
        return total

    for _, t in trades.iterrows():
        amount = int(t["qty"]) * float(t["price"])
        fee = float(t["fee"] or 0)
        tax = float(t["tax"] or 0)
        if t["side"] == "BUY":
            total -= amount + fee
        else:
            total += amount - fee - tax
    return total


def positions(trades: pd.DataFrame, price_of: dict[str, float],
              name_of: dict[str, str] | None = None,
              sector_of: dict[str, str] | None = None) -> pd.DataFrame:
    """
    지금 들고 있는 종목을 표로 만듭니다.

    price_of : {종목코드: 현재가} — 대시보드가 쓰는 최신 종가를 넘겨주세요.
    """
    held, _ = walk(trades)
    name_of = name_of or {}
    sector_of = sector_of or {}

    rows = []
    for code, pos in held.items():
        if pos["수량"] <= 0:
            continue
        now = price_of.get(code)
        평가금액 = (now * pos["수량"]) if now is not None else None
        평가손익 = (평가금액 - pos["취득원가"]) if 평가금액 is not None else None
        목표가, 손절가 = pos.get("목표가"), pos.get("손절가")

        # ★ 살 때 정한 약속에 닿았는지 ★
        #   적어두기만 하고 아무도 안 보면 적는 의미가 없습니다.
        신호 = None
        if now is not None:
            if 목표가 and now >= 목표가:
                신호 = "목표가 도달"
            elif 손절가 and now <= 손절가:
                신호 = "손절가 도달"

        시작 = pos.get("보유시작")
        보유일 = (pd.Timestamp.today().normalize() - pd.Timestamp(시작)).days \
            if 시작 is not None else None

        rows.append({
            "종목코드": code,
            "종목명": name_of.get(code, code),
            "업종": sector_of.get(code, "업종 미상"),
            "수량": pos["수량"],
            "평균단가": pos["평균단가"],
            "현재가": now,
            "취득원가": pos["취득원가"],
            "평가금액": 평가금액,
            "평가손익": 평가손익,
            "수익률(%)": ((평가금액 / pos["취득원가"] - 1) * 100)
                         if (평가금액 is not None and pos["취득원가"]) else None,
            "목표가": 목표가,
            "손절가": 손절가,
            "신호": 신호,
            "보유일": 보유일,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "종목코드", "종목명", "업종", "수량", "평균단가", "현재가",
            "취득원가", "평가금액", "평가손익", "수익률(%)",
            "목표가", "손절가", "신호", "보유일", "비중(%)"])

    df = pd.DataFrame(rows)
    total = df["평가금액"].sum(skipna=True)
    df["비중(%)"] = (df["평가금액"] / total * 100).round(1) if total else None
    return df.sort_values("평가금액", ascending=False, na_position="last")


def held_qty(trades: pd.DataFrame, code: str) -> int:
    """특정 종목을 지금 몇 주 들고 있는지. (팔 때 수량을 막는 데 씁니다)"""
    held, _ = walk(trades)
    return int(held.get(str(code), {}).get("수량", 0))


def summary(trades: pd.DataFrame, cash: pd.DataFrame,
            price_of: dict[str, float]) -> dict:
    """
    계좌 전체를 한 줄로 요약합니다.

      총자산   = 현금 + 지금 들고 있는 것의 평가금액
      투자원금 = 내가 넣은 돈 (입금 − 출금)
      총손익   = 총자산 − 투자원금
    """
    _, closed = walk(trades)
    pos = positions(trades, price_of)

    현금 = cash_balance(trades, cash)
    평가금액 = float(pos["평가금액"].sum(skipna=True)) if not pos.empty else 0.0
    원금 = float(cash["amount"].sum()) if not cash.empty else 0.0
    총자산 = 현금 + 평가금액

    실현 = sum(c["실현손익"] for c in closed) if closed else 0.0
    평가손익 = float(pos["평가손익"].sum(skipna=True)) if not pos.empty else 0.0

    승 = sum(1 for c in closed if c["실현손익"] > 0)
    패 = sum(1 for c in closed if c["실현손익"] <= 0)

    return {
        "현금": 현금,
        "평가금액": 평가금액,
        "총자산": 총자산,
        "투자원금": 원금,
        "총손익": 총자산 - 원금,
        "총수익률(%)": ((총자산 / 원금 - 1) * 100) if 원금 else None,
        "실현손익": 실현,
        "평가손익": 평가손익,
        "매도횟수": len(closed),
        "이긴횟수": 승,
        "진횟수": 패,
        "승률(%)": (승 / (승 + 패) * 100) if (승 + 패) else None,
        "비용합계": (float(trades["fee"].sum()) + float(trades["tax"].sum()))
                    if not trades.empty else 0.0,
    }


def alerts(pos: pd.DataFrame) -> list[dict]:
    """
    살 때 정한 약속에 닿은 종목을 모읍니다.

    왜 필요한가요?
      목표가·손절가를 적어두게 해놓고 아무도 안 보면 적는 의미가 없습니다.
      대부분의 손실은 '손절가를 정해뒀지만 그냥 지나친' 데서 생깁니다.
      그래서 계좌를 열면 가장 먼저 보이게 합니다.

    돌려주는 값: [{종류, 종목명, 현재가, 기준가, 말}]
    """
    if pos.empty or "신호" not in pos.columns:
        return []

    out = []
    for _, r in pos.iterrows():
        sig = r.get("신호")
        # ※ 빈 값이 NaN 으로 들어오는데, 파이썬에서 NaN 은 '참' 으로 취급됩니다.
        #   그래서 `if not sig` 만 쓰면 신호가 없는 종목까지 알림에 끼어듭니다.
        if sig is None or pd.isna(sig) or not str(sig).strip():
            continue
        if sig == "목표가 도달":
            out.append({
                "종류": "목표",
                "종목명": r["종목명"],
                "현재가": r.get("현재가"),
                "기준가": r.get("목표가"),
                "말": ("살 때 정한 목표가에 닿았습니다. 팔지, 더 들고 갈지 "
                       "지금 정하세요. '조금만 더' 하다 놓치는 일이 가장 흔합니다."),
            })
        else:
            out.append({
                "종류": "손절",
                "종목명": r["종목명"],
                "현재가": r.get("현재가"),
                "기준가": r.get("손절가"),
                "말": ("살 때 정한 손절가 아래로 내려왔습니다. **처음 산 이유가 "
                       "아직 유효한지** 확인하세요. 이유가 사라졌다면 파는 것이 맞습니다. "
                       "'곧 오르겠지' 는 손실을 키우는 가장 흔한 생각입니다."),
            })
    # 손절을 먼저 보여줍니다. 더 급한 쪽이라서입니다.
    return sorted(out, key=lambda a: 0 if a["종류"] == "손절" else 1)


def concentration_warnings(pos: pd.DataFrame, limit: float = 40.0) -> list[str]:
    """
    한 종목·한 업종에 너무 몰려 있으면 알려줍니다.

    왜 필요한가요?
      한 곳에 몰아넣으면 그 회사가 잘못됐을 때 회복할 방법이 없습니다.
      분산은 수익을 늘리는 방법이 아니라 **크게 망하지 않는 방법**입니다.
    """
    if pos.empty or pos["평가금액"].isna().all():
        return []

    out = []
    for _, r in pos.iterrows():
        w = r.get("비중(%)")
        if pd.notna(w) and float(w) >= limit:
            out.append(f"**{r['종목명']}** 한 종목이 {float(w):,.0f}% 를 차지합니다")

    by_sector = pos.groupby("업종")["평가금액"].sum()
    total = by_sector.sum()
    if total:
        for sector, amount in by_sector.items():
            share = amount / total * 100
            if sector != "업종 미상" and share >= 60:
                out.append(f"**{sector}** 업종에 {share:,.0f}% 가 몰려 있습니다")
    return out
