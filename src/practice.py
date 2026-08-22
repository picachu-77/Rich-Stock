# -*- coding: utf-8 -*-
"""
모의투자를 '연습' 으로 만들어주는 파일.

왜 이 파일이 따로 있나요?
  사고판 기록을 적기만 하면 그것은 **가계부**입니다. 연습이 되려면
  세 가지가 더 있어야 합니다.

    1) 할 일이 순서대로 주어질 것      → missions()   무엇부터 해볼지
    2) 끝난 뒤 되돌아볼 것             → reviews()    계획대로 했는가
    3) 반복되는 버릇이 보일 것         → habits()     내가 늘 하는 실수

  운동으로 치면 매매 기록은 '오늘 몇 kg 들었다' 이고, 이 파일은
  '자세가 맞았는가' 를 봅니다. 주식에서 자세에 해당하는 것이
  **살 이유를 정하고, 팔 기준을 미리 정하고, 그 기준을 지키는 것** 입니다.

★ 가장 중요한 생각 ★
  연습의 성적표는 **수익률이 아닙니다.**
  운이 좋아 번 돈은 다음에도 벌 수 있다는 뜻이 아니고, 운이 나빠 잃은 돈은
  판단이 틀렸다는 뜻이 아닙니다. 몇 번 안 되는 매매에서 수익률은 거의
  운입니다. 그래서 여기서는 **판단하는 습관**을 점수로 봅니다.
"""

from __future__ import annotations

import re

import pandas as pd

# ══════════════════════════════════════════════════════════════
#  왜 샀는지 / 왜 파는지 — 종류를 골라두면 나중에 성적을 낼 수 있습니다
# ══════════════════════════════════════════════════════════════
#
# 왜 '종류' 를 고르게 하나요?
#   글로만 적어두면 나중에 모아서 볼 수가 없습니다. 종류를 함께 정해두면
#   "나는 '남들이 사길래' 산 것만 늘 잃는구나" 처럼 **내 버릇**이 숫자로
#   드러납니다. 그것이 연습에서 가장 크게 남는 것입니다.
#
# 마지막 항목이 솔직한 답인 이유
#   실제로 초보자의 매매 상당수는 근거 없이 이뤄집니다. 그 선택지를 아예
#   없애면 다들 그럴듯한 이유를 고르게 되고, 기록이 거짓이 됩니다.

BUY_REASONS: list[tuple[str, str]] = [
    ("실적이 좋아서",   "매출·이익이 늘고 있거나 재무가 튼튼해서"),
    ("값이 싸 보여서",  "PER·PBR 이 예전보다, 또는 같은 업종보다 낮아서"),
    ("방향이 좋아서",   "공시·신사업 등 회사가 가는 길이 마음에 들어서"),
    ("배당을 보고",     "꾸준히 배당을 주는 점이 마음에 들어서"),
    ("뉴스·테마를 보고", "요즘 뜨는 이야기라서"),
    ("차트를 보고",     "가격 흐름·이동평균선 등 그림을 보고"),
    ("그냥 느낌으로",   "남들이 사길래 / 딱히 이유는 없이"),
]

SELL_REASONS: list[tuple[str, str]] = [
    ("목표가에 닿아서",   "살 때 정한 목표 가격까지 올라서"),
    ("손절가에 닿아서",   "살 때 정한 손절 가격까지 내려서"),
    ("산 이유가 사라져서", "실적이 꺾이는 등 처음 산 근거가 없어져서"),
    ("더 좋은 곳에 쓰려고", "다른 종목이 더 나아 보여서"),
    ("불안해서",         "많이 내려서 / 참기 힘들어서"),
    ("돈이 필요해서",     "투자와 상관없는 이유로"),
]

# 좋은 판단으로 보는 매도 이유 (계획이 있었던 것)
_PLANNED_SELL = {"목표가에 닿아서", "손절가에 닿아서", "산 이유가 사라져서"}

_TAG = re.compile(r"^\[(?P<kind>[^\]]{1,30})\]\s*(?P<note>.*)$", re.S)


def tag(kind: str | None, note: str | None) -> str | None:
    """
    고른 종류와 직접 쓴 메모를 한 칸에 합쳐 저장합니다.

        tag("실적이 좋아서", "3년째 매출 증가")  →  "[실적이 좋아서] 3년째 매출 증가"

    왜 이렇게 하나요?
      표에 칸을 새로 만들면 이미 쓰던 분들이 표를 다시 만들어야 합니다.
      대괄호로 앞에 붙여두면 표를 바꾸지 않고도 종류를 남길 수 있고,
      사람이 읽어도 그대로 읽힙니다.
    """
    kind = (kind or "").strip()
    note = (note or "").strip()
    if kind and note:
        return f"[{kind}] {note}"
    if kind:
        return f"[{kind}]"
    return note or None


def untag(text) -> tuple[str | None, str]:
    """합쳐둔 글에서 '종류' 와 '메모' 를 다시 떼어냅니다."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None, ""
    m = _TAG.match(str(text).strip())
    if not m:
        return None, str(text).strip()
    return m.group("kind").strip(), m.group("note").strip()


def kind_of(text) -> str:
    """종류만 뽑습니다. 없으면 '안 적음'."""
    k, _ = untag(text)
    return k or "안 적음"


# ══════════════════════════════════════════════════════════════
#  1) 연습 단계 — 무엇부터 해볼지
# ══════════════════════════════════════════════════════════════
def missions(trades: pd.DataFrame, cash: pd.DataFrame,
             pos: pd.DataFrame, closed: list[dict]) -> list[dict]:
    """
    연습을 순서대로 안내합니다.

    왜 필요한가요?
      "연습해 보세요" 라고만 하면 대부분 한 종목 사보고 끝냅니다.
      실제 투자에서 필요한 동작은 사는 것 말고도 여럿입니다. 기준을 정하고,
      나눠 담고, 팔아보고, 오래 들고 있어 보는 것까지 해봐야 연습이 됩니다.

    돌려주는 값: [{제목, 설명, 끝남, 지금값}]
    """
    buys = trades[trades["side"] == "BUY"] if not trades.empty else trades
    sells = trades[trades["side"] == "SELL"] if not trades.empty else trades

    has_plan = 0
    has_reason = 0
    if not buys.empty:
        has_plan = int((buys["target_price"].notna() & buys["stop_price"].notna()).sum())
        has_reason = int(buys["reason"].fillna("").astype(str).str.strip().ne("").sum())

    종목수 = int(pos["종목코드"].nunique()) if not pos.empty else 0
    최장보유 = int(pos["보유일"].max()) if (not pos.empty and pos["보유일"].notna().any()) else 0
    if closed:
        최장보유 = max(최장보유, max(int(c.get("보유일") or 0) for c in closed))

    지킨횟수 = sum(1 for r in _judge_all(closed) if r["잘함"])

    items = [
        ("연습 자금 넣기", "💵 예수금 탭에서, 실제로 투자할 만한 금액을 넣어보세요.",
         (not cash.empty), None),
        ("종목 하나 사보기", "🛒 사고팔기에서 마음에 드는 회사를 한 주라도 사보세요.",
         (not buys.empty), None),
        ("살 이유를 적고 사보기", "왜 사는지 한 줄이라도 적어두면 팔 때 기준이 생깁니다.",
         has_reason >= 1, f"{has_reason:,}번"),
        ("목표가·손절가를 정하고 사보기",
         "'얼마가 되면 판다'를 미리 정해두는 것이 실전에서 가장 큰 차이를 만듭니다.",
         has_plan >= 1, f"{has_plan:,}번"),
        ("팔아보기", "사는 것보다 파는 것이 훨씬 어렵습니다. 한 번 팔아보세요.",
         (not sells.empty), None),
        ("3종목 이상으로 나눠 담기",
         "한 곳에 몰아넣으면 그 회사가 잘못됐을 때 방법이 없습니다.",
         종목수 >= 3, f"{종목수:,}종목"),
        ("30일 이상 들고 있어보기",
         "며칠 만에 사고파는 것은 투자가 아니라 도박에 가깝습니다.",
         최장보유 >= 30, f"{최장보유:,}일"),
        ("정한 기준대로 팔아보기 (3번)",
         "정하는 것보다 지키는 것이 어렵습니다. 여기까지 오면 연습이 된 것입니다.",
         지킨횟수 >= 3, f"{지킨횟수:,}번"),
    ]
    return [{"제목": t, "설명": d, "끝남": bool(done), "지금값": now}
            for t, d, done, now in items]


# ══════════════════════════════════════════════════════════════
#  2) 복기 — 계획대로 했는가
# ══════════════════════════════════════════════════════════════
def _judge(c: dict) -> dict:
    """
    판 거래 하나를 놓고 '계획대로 했는지' 를 따집니다.

    ★ 번 돈으로 판단하지 않습니다 ★
      계획대로 손절했는데 그 뒤에 올랐을 수도 있고, 아무 생각 없이 샀는데
      운 좋게 오를 수도 있습니다. 결과는 운이 섞이지만 **과정은 내 것**이라
      다음에도 똑같이 반복됩니다. 그래서 과정만 봅니다.
    """
    판가 = float(c.get("판가격") or 0)
    목표 = c.get("목표가")
    손절 = c.get("손절가")
    이유종류, _ = untag(c.get("이유"))
    목표 = float(목표) if pd.notna(목표) else None
    손절 = float(손절) if pd.notna(손절) else None

    if 목표 is None and 손절 is None:
        return {"판정": "기준 없이 팔았습니다", "잘함": False,
                "말": ("살 때 목표가·손절가를 정하지 않아, 판 시점이 옳았는지 "
                       "따져볼 방법이 없습니다. 다음에는 두 숫자를 먼저 정해보세요.")}

    if 목표 is not None and 판가 >= 목표:
        return {"판정": "목표를 지켰습니다", "잘함": True,
                "말": ("정한 목표가에 닿아 팔았습니다. '조금만 더' 를 참은 것이라 "
                       "가장 어려운 일 중 하나입니다.")}

    if 손절 is not None and 판가 <= 손절:
        늦음 = 판가 <= 손절 * 0.95
        if 늦음:
            return {"판정": "손절이 늦었습니다", "잘함": False,
                    "말": (f"정한 손절가({손절:,.0f}원)보다 한참 내려간 뒤에 팔았습니다. "
                           "손절가를 정해두고 지나치는 것이 손실이 커지는 가장 흔한 "
                           "이유입니다.")}
        return {"판정": "손절을 지켰습니다", "잘함": True,
                "말": ("손해를 보면서 파는 것은 정말 어렵습니다. 정한 대로 지켰다면 "
                       "그것만으로 잘한 매매입니다. 결과가 아니라 지킨 것이 중요합니다.")}

    # 목표와 손절 사이에서 팔았습니다 — 계획에 없던 매도입니다.
    이익 = float(c.get("실현손익") or 0) > 0
    if 이유종류 == "산 이유가 사라져서":
        return {"판정": "이유가 사라져 팔았습니다", "잘함": True,
                "말": ("가격이 아니라 회사를 보고 판 것입니다. 처음 산 근거가 "
                       "없어졌다면 목표가 전이라도 파는 것이 맞습니다.")}
    if 이익:
        return {"판정": "목표 전에 팔았습니다", "잘함": False,
                "말": ("이익이 났을 때 서둘러 파는 것은 흔한 버릇입니다. 조금씩 여러 번 "
                       "이기고 한 번 크게 지면 결국 손해가 됩니다.")}
    return {"판정": "손절 전에 팔았습니다", "잘함": False,
            "말": ("정한 손절가에 닿기도 전에 팔았습니다. 불안해서 판 것이라면, "
                   "손절가를 처음부터 견딜 수 있는 자리에 두는 편이 낫습니다.")}


def _judge_all(closed: list[dict]) -> list[dict]:
    return [_judge(c) for c in (closed or [])]


def reviews(closed: list[dict], name_of: dict[str, str] | None = None) -> pd.DataFrame:
    """판 거래를 '계획 vs 실제' 로 나란히 놓은 표를 만듭니다. (최근 것부터)"""
    cols = ["판날", "종목명", "종목코드", "산이유종류", "판이유종류",
            "평균단가", "목표가", "손절가", "판가격",
            "실현손익", "실현수익률(%)", "보유일", "판정", "잘함", "말"]
    if not closed:
        return pd.DataFrame(columns=cols)

    name_of = name_of or {}
    rows = []
    for c in closed:
        j = _judge(c)
        rows.append({
            "판날": c.get("판날"),
            "종목명": name_of.get(str(c["종목코드"]), str(c["종목코드"])),
            "종목코드": str(c["종목코드"]),
            "산이유종류": kind_of(c.get("산이유")),
            "판이유종류": kind_of(c.get("이유")),
            "평균단가": c.get("평균단가"),
            "목표가": c.get("목표가"),
            "손절가": c.get("손절가"),
            "판가격": c.get("판가격"),
            "실현손익": c.get("실현손익"),
            "실현수익률(%)": c.get("실현수익률(%)"),
            "보유일": c.get("보유일"),
            "판정": j["판정"],
            "잘함": j["잘함"],
            "말": j["말"],
        })
    df = pd.DataFrame(rows, columns=cols)
    return df.iloc[::-1].reset_index(drop=True)


def by_reason(rev: pd.DataFrame, column: str = "산이유종류") -> pd.DataFrame:
    """
    '어떤 이유로 샀을 때 잘 됐는지' 를 모아 봅니다.

    이게 왜 연습에서 가장 값진가요?
      대부분의 사람은 자기가 무엇 때문에 잃는지 모릅니다. 종류별로 모아보면
      "뉴스 보고 산 것은 늘 잃는다" 같은 사실이 숫자로 보입니다. 그것 하나만
      고쳐도 성적이 달라집니다.

    ※ 3번 미만은 운일 가능성이 커서 화면에서 흐리게 다룹니다.
    """
    if rev.empty:
        return pd.DataFrame(columns=[column, "횟수", "이긴횟수", "승률(%)",
                                     "손익합계", "평균수익률(%)"])

    g = rev.groupby(column, dropna=False)
    out = pd.DataFrame({
        "횟수": g.size(),
        "이긴횟수": g["실현손익"].apply(lambda s: int((s > 0).sum())),
        "손익합계": g["실현손익"].sum(),
        "평균수익률(%)": g["실현수익률(%)"].mean(),
    }).reset_index()
    out["승률(%)"] = out["이긴횟수"] / out["횟수"] * 100
    out = out[[column, "횟수", "이긴횟수", "승률(%)", "손익합계", "평균수익률(%)"]]
    return out.sort_values("손익합계", ascending=False, na_position="last")


# ══════════════════════════════════════════════════════════════
#  3) 습관 점수 — 내가 늘 하는 실수
# ══════════════════════════════════════════════════════════════
def habits(trades: pd.DataFrame, closed: list[dict], pos: pd.DataFrame,
           원금: float = 0.0) -> list[dict]:
    """
    '판단하는 습관' 을 항목별로 점수 냅니다. (0~100점, 수익률이 아닙니다)

    돌려주는 값: [{항목, 점수, 값글, 말, 잼}]
      점수가 None 이면 아직 판단할 자료가 모자란 것입니다.
    """
    buys = trades[trades["side"] == "BUY"] if not trades.empty else trades
    rev = reviews(closed)
    out: list[dict] = []

    def add(항목, 점수, 값글, 말):
        out.append({"항목": 항목, "점수": 점수, "값글": 값글, "말": 말})

    # ① 살 때 이유를 적는가
    if buys.empty:
        add("살 이유를 적는가", None, "아직 산 적이 없습니다",
            "한 종목이라도 사보면 여기에 점수가 생깁니다.")
    else:
        적음 = buys["reason"].fillna("").astype(str).str.strip().ne("")
        비율 = float(적음.mean()) * 100
        add("살 이유를 적는가", 비율, f"{int(적음.sum()):,}번 / {len(buys):,}번",
            ("이유 없이 산 종목은 팔 기준도 없습니다. 내릴 때 버틸지 팔지를 "
             "그 자리에서 정하게 되고, 그때 판단은 대개 틀립니다."))

    # ② 팔 기준을 미리 정하는가
    if buys.empty:
        add("팔 기준을 미리 정하는가", None, "아직 산 적이 없습니다",
            "목표가와 손절가를 정하고 사보세요.")
    else:
        정함 = buys["target_price"].notna() & buys["stop_price"].notna()
        비율 = float(정함.mean()) * 100
        add("팔 기준을 미리 정하는가", 비율, f"{int(정함.sum()):,}번 / {len(buys):,}번",
            ("사기 전에 정한 숫자는 냉정하지만, 사고 난 뒤에 정하는 숫자는 "
             "이미 마음이 기울어 있습니다. 그래서 순서가 중요합니다."))

    # ③ 정한 기준을 지키는가
    if rev.empty:
        add("정한 기준을 지키는가", None, "아직 판 적이 없습니다",
            "팔아봐야 지켰는지 알 수 있습니다.")
    else:
        판정있음 = rev[rev["판정"] != "기준 없이 팔았습니다"]
        if 판정있음.empty:
            add("정한 기준을 지키는가", None, "기준을 정한 매매가 없습니다",
                "목표가·손절가를 정하고 사면 여기에 점수가 생깁니다.")
        else:
            비율 = float(판정있음["잘함"].mean()) * 100
            add("정한 기준을 지키는가",
                비율, f"{int(판정있음['잘함'].sum()):,}번 / {len(판정있음):,}번",
                ("정하는 것보다 지키는 것이 훨씬 어렵습니다. 이 점수가 높으면 "
                 "실제 돈을 넣어도 크게 무너지지 않습니다."))

    # ④ 너무 자주 사고팔지 않는가 (평균 보유일)
    보유일 = [int(c["보유일"]) for c in (closed or []) if c.get("보유일") is not None]
    if not pos.empty and pos["보유일"].notna().any():
        보유일 += [int(v) for v in pos["보유일"].dropna().tolist()]
    if not 보유일:
        add("오래 들고 있는가", None, "아직 셀 수 없습니다",
            "산 뒤 며칠이 지나야 알 수 있습니다.")
    else:
        평균 = sum(보유일) / len(보유일)
        # 30일이면 100점, 그보다 짧으면 비례해서 깎습니다.
        add("오래 들고 있는가", min(100.0, 평균 / 30 * 100), f"평균 {평균:,.0f}일",
            ("며칠 만에 사고팔면 회사가 잘하는지 확인할 시간 자체가 없습니다. "
             "그건 회사를 산 것이 아니라 가격을 맞히는 내기입니다. "
             "수수료도 사고팔 때마다 나갑니다."))

    # ⑤ 한 곳에 몰지 않는가
    if pos.empty or pos["평가금액"].isna().all():
        add("나눠 담는가", None, "들고 있는 종목이 없습니다",
            "3종목 이상으로 나눠 담아보세요.")
    else:
        최대비중 = float(pd.to_numeric(pos["비중(%)"], errors="coerce").max())
        # 한 종목이 40% 를 넘어가면 0점에 가깝게, 20% 이하면 100점.
        점수 = max(0.0, min(100.0, (40 - 최대비중) / 20 * 100))
        add("나눠 담는가", 점수,
            f"가장 큰 한 종목이 {최대비중:,.0f}%",
            ("분산은 돈을 더 버는 방법이 아니라 **크게 망하지 않는 방법**입니다. "
             "한 종목이 반을 넘으면 그 회사 하나에 내 돈 전부를 건 것과 같습니다."))

    # ⑥ 비용이 수익을 갉아먹지 않는가
    #
    # ★ 왜 '원금 대비' 로 재나요? ★
    #   사고판 금액 대비로 재면 한 번을 사고팔든 백 번을 사고팔든 비율이
    #   똑같이 나옵니다(한 번 오갈 때마다 같은 요율이 붙기 때문입니다).
    #   그러면 '자주 사고파는 버릇' 이 전혀 드러나지 않습니다.
    #   내가 넣은 돈 대비로 재야, 매매를 반복할수록 숫자가 커집니다.
    비용 = (float(trades["fee"].sum()) + float(trades["tax"].sum())) \
        if not trades.empty else 0.0
    if trades.empty or not 원금:
        add("비용을 아끼는가", None,
            "아직 매매가 없습니다" if trades.empty else "넣은 돈이 없습니다", "")
    else:
        비율 = 비용 / 원금 * 100
        # 넣은 돈의 3% 가 비용으로 나갔다면 지나치게 자주 사고판 것입니다.
        # (한 번 사고파는 데 드는 비용은 0.2% 남짓입니다)
        add("비용을 아끼는가", max(0.0, min(100.0, (3.0 - 비율) / 3.0 * 100)),
            f"{비용:,.0f}원 (넣은 돈의 {비율:,.2f}%)",
            ("수수료와 세금은 벌든 잃든 나갑니다. 한 번 사고파는 데 넣은 돈의 "
             "0.2% 남짓이 사라지므로, 열 번이면 2% 입니다. 매매를 줄이는 것은 "
             "**확실하게 돈이 늘어나는 유일한 방법**입니다."))

    return out


def overall(hs: list[dict]) -> float | None:
    """습관 점수를 하나로 합칩니다. (아직 잴 수 없는 항목은 빼고 평균)"""
    vals = [h["점수"] for h in hs if h["점수"] is not None]
    return (sum(vals) / len(vals)) if vals else None


def grade(score: float | None) -> tuple[str, str]:
    """점수를 사람이 읽는 말로. (등급, 한 줄 설명)"""
    if score is None:
        return "아직", "몇 번 사고팔아 보면 습관이 보이기 시작합니다."
    if score >= 80:
        return "좋음", "지금 습관이라면 실제 돈을 넣어도 크게 무너지지 않습니다."
    if score >= 60:
        return "보통", "기본은 잡혔습니다. 아래에서 점수가 낮은 항목 하나만 고쳐보세요."
    if score >= 40:
        return "연습 필요", "기준을 정하고 지키는 연습이 더 필요합니다. 아직 실제 돈은 이릅니다."
    return "많이 필요", "지금은 판단이 아니라 기분으로 사고팔고 있을 가능성이 큽니다."


def coach(hs: list[dict], rev: pd.DataFrame) -> list[str]:
    """
    지금 가장 먼저 고치면 좋을 것 한두 가지를 골라줍니다.

    왜 하나둘만 주나요?
      고칠 것을 다섯 개 주면 아무것도 안 고칩니다. 가장 낮은 항목부터
      하나씩 올리는 편이 실제로 바뀝니다.
    """
    tips: list[str] = []
    잴수있음 = [h for h in hs if h["점수"] is not None]
    for h in sorted(잴수있음, key=lambda x: x["점수"])[:2]:
        if h["점수"] >= 80:
            continue
        tips.append(f"**{h['항목']}** — 지금 {h['점수']:,.0f}점 ({h['값글']}). {h['말']}")

    # 반복되는 실수 하나를 덧붙입니다.
    if not rev.empty:
        흔한 = rev[~rev["잘함"]]["판정"].value_counts()
        if not 흔한.empty and int(흔한.iloc[0]) >= 2:
            tips.append(
                f"판 {len(rev):,}번 중 **{흔한.index[0]}** 가 {int(흔한.iloc[0]):,}번으로 "
                "가장 잦습니다. 같은 실수를 반복하고 있다는 뜻입니다."
            )
    return tips
