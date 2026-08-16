# -*- coding: utf-8 -*-
"""
'조심해야 할 종목'을 가려내는 기준을 모아둔 파일.

왜 필요한가요?
  점수가 높은 회사를 찾는 것만큼 중요한 것이 '크게 다칠 회사를 피하는 것'입니다.
  초보자가 돈을 크게 잃는 경우는 대체로 좋은 회사를 못 골라서가 아니라,
  위험한 회사인 줄 모르고 샀기 때문입니다.

주의
  이 신호는 '위험하니 절대 사지 말라'는 뜻이 아니고,
  '사기 전에 왜 이런지 꼭 확인하라'는 표시입니다.
  반대로 신호가 하나도 없다고 안전한 회사라는 뜻도 아닙니다.

기준을 바꾸려면
  아래 RULES 의 숫자만 고치면 화면이 자동으로 따라 바뀝니다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 기준 숫자 (여기만 고치면 됩니다)
CAPITAL_ERODED = 0            # 자본총계가 이 값 이하이면 자본잠식
PROFIT_RATE_BAD = 50.0        # 최근 보고서 중 흑자 비율이 이 % 미만이면 적자 잦음
DEBT_DANGER = 400.0           # 부채비율이 이 % 이상이면 위험
VOLUME_LOW = 10_000           # 하루 거래량이 이 주수 미만이면 거래 부족
CAP_SMALL = 500               # 시가총액이 이 억원 미만이면 초소형
PENNY_PRICE = 1_000           # 주가가 이 원 미만이면 동전주


@dataclass(frozen=True)
class Flag:
    key: str        # 내부 이름
    label: str      # 화면에 보일 짧은 말
    level: str      # "위험" 또는 "주의"
    why: str        # 왜 문제인지 쉬운 설명


FLAGS: dict[str, Flag] = {
    "자본잠식": Flag(
        "자본잠식", "자본잠식", "위험",
        "빚이 회사 재산을 다 갉아먹어 자기 돈이 마이너스인 상태입니다. "
        "상장폐지로 이어지는 대표적인 경로라 초보자는 피하는 것이 좋습니다.",
    ),
    "최근적자": Flag(
        "최근적자", "최근 적자", "주의",
        "가장 최근 보고서에서 손해를 봤습니다. 한 번은 그럴 수 있지만, "
        "왜 적자인지(일시적인지 계속될 일인지) 확인이 필요합니다.",
    ),
    "적자잦음": Flag(
        "적자잦음", "적자 잦음", "위험",
        f"최근 보고서 중 흑자 비율이 {PROFIT_RATE_BAD:.0f}% 미만입니다. "
        "돈을 꾸준히 벌지 못하는 회사는 버티는 힘이 약합니다.",
    ),
    "빚과다": Flag(
        "빚과다", "빚 많음", "위험",
        f"부채비율이 {DEBT_DANGER:.0f}% 이상입니다. 금리가 오르거나 실적이 나빠지면 "
        "이자 부담으로 회사가 크게 흔들릴 수 있습니다. "
        "다만 은행·증권·건설은 원래 높으니 업종을 함께 보세요.",
    ),
    "거래부족": Flag(
        "거래부족", "거래 부족", "주의",
        f"하루 거래량이 {VOLUME_LOW:,}주 미만입니다. 사는 것보다 파는 게 문제입니다. "
        "팔고 싶을 때 사줄 사람이 없어 제값을 못 받을 수 있습니다.",
    ),
    "초소형": Flag(
        "초소형", "초소형 종목", "주의",
        f"시가총액이 {CAP_SMALL:,}억원 미만입니다. 작은 회사는 몇몇 사람의 매매로도 "
        "가격이 크게 출렁이고, 정보도 적어 초보자에게 불리합니다.",
    ),
    "동전주": Flag(
        "동전주", "동전주", "주의",
        f"주가가 {PENNY_PRICE:,}원 미만입니다. 값이 싸 보여 많이 사기 쉽지만, "
        "그만큼 실적이 나빠 주가가 내려온 경우가 많습니다.",
    ),
    "적자로제외": Flag(
        "적자로제외", "이익 없음(PER 없음)", "주의",
        "이익을 내지 못해 PER 을 계산할 수 없습니다. 점수 순위에서는 빠집니다. "
        "성장 초기 회사일 수도 있지만, 그만큼 불확실합니다.",
    ),
}


def detect(row: pd.Series) -> list[Flag]:
    """한 종목의 위험 신호를 찾아 목록으로 돌려줍니다."""
    found: list[Flag] = []

    equity = row.get("최근자본")
    if pd.notna(equity) and float(equity) <= CAPITAL_ERODED:
        found.append(FLAGS["자본잠식"])

    net = row.get("최근순이익")
    if pd.notna(net) and float(net) < 0:
        found.append(FLAGS["최근적자"])

    rate = row.get("흑자비율(%)")
    if pd.notna(rate) and float(rate) < PROFIT_RATE_BAD:
        found.append(FLAGS["적자잦음"])

    debt = row.get("부채비율(%)")
    if pd.notna(debt) and float(debt) >= DEBT_DANGER:
        found.append(FLAGS["빚과다"])

    vol = row.get("거래량")
    if pd.notna(vol) and float(vol) < VOLUME_LOW:
        found.append(FLAGS["거래부족"])

    cap = row.get("시가총액(억)")
    if pd.notna(cap) and float(cap) < CAP_SMALL:
        found.append(FLAGS["초소형"])

    price = row.get("종가")
    if pd.notna(price) and float(price) < PENNY_PRICE:
        found.append(FLAGS["동전주"])

    # 주식인데 PER 이 없다는 것은 이익을 못 냈다는 뜻입니다. (ETF 는 해당 없음)
    if row.get("종류") == "주식" and pd.isna(row.get("PER")):
        found.append(FLAGS["적자로제외"])

    return found


def add_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    표 전체에 위험 신호를 붙입니다.

    붙는 칸
      위험신호   : 신호 이름 목록 (예: ['자본잠식', '빚 많음'])
      위험개수   : 신호 개수
      위험수준   : '위험' 이 하나라도 있으면 '위험', 아니면 '주의' 또는 '' (없음)
    """
    if df.empty:
        return df.assign(위험신호=None, 위험개수=0, 위험수준="")

    found = [detect(row) for _, row in df.iterrows()]
    out = df.copy()
    out["위험신호"] = [[f.label for f in fs] for fs in found]
    out["위험개수"] = [len(fs) for fs in found]
    out["위험수준"] = [
        "위험" if any(f.level == "위험" for f in fs)
        else ("주의" if fs else "")
        for fs in found
    ]
    return out


def badges_html(labels) -> str:
    """위험 신호를 화면에 붙일 작은 딱지(HTML)로 만듭니다."""
    if not isinstance(labels, (list, tuple)) or not labels:
        return ""
    parts = []
    for label in labels:
        flag = next((f for f in FLAGS.values() if f.label == label), None)
        cls = "risk-badge danger" if (flag and flag.level == "위험") else "risk-badge warn"
        parts.append(f"<span class='{cls}'>⚠ {label}</span>")
    return "".join(parts)
