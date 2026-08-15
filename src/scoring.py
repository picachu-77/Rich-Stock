# -*- coding: utf-8 -*-
"""
'투자하기 좋은 회사' 점수를 매기는 기준을 모아둔 파일.

⚠️ 먼저 알아두실 점
  이 점수는 투자 추천이 아닙니다. 공개된 재무 숫자를 정해진 계산식에 넣어
  기계적으로 매긴 값일 뿐이며, 점수가 높다고 주가가 오른다는 뜻이 절대 아닙니다.
  기준(아래 숫자)은 널리 쓰이는 일반적인 눈금일 뿐 정답이 아닙니다.

기준을 바꾸고 싶으면
  아래 METRICS 의 points 숫자만 고치면 화면이 자동으로 따라 바뀝니다.
  points 는 [(지표값, 점수), ...] 형태이며, 그 사이 값은 자동으로 비례 계산됩니다.
  higher_is_better=False 인 지표(부채비율·PER·PBR)는 값이 작을수록 점수가 높습니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True)
class Metric:
    key: str            # 데이터 표의 열 이름
    label: str          # 화면에 보여줄 이름
    unit: str           # 단위
    group: str          # 묶음 (수익성 / 안정성 / 가치 / 배당)
    higher_is_better: bool
    points: list[tuple[float, float]]   # [(지표값, 점수 0~100), ...] 낮은 값부터
    why: str            # 이 지표를 왜 보는지 (한 줄)
    good: str           # 점수가 높을 때의 뜻
    bad: str            # 점수가 낮을 때의 뜻
    required: bool = True   # 값이 없으면 순위에서 빼는 핵심 지표인지
    digits: int = 2
    # 값이 마이너스일 때 따로 알려줄 말 (없으면 bad 를 씁니다)
    # 예) 이익률이 마이너스면 '손해', 매출성장이 마이너스면 '매출 감소' 로 뜻이 다릅니다.
    negative: str | None = None


METRICS: list[Metric] = [
    Metric(
        key="ROE(%)", label="ROE", unit="%", group="수익성", higher_is_better=True,
        points=[(0, 0), (5, 30), (10, 60), (15, 85), (20, 100)],
        why="회사가 자기 돈을 굴려 1년에 몇 % 벌었는지 봅니다.",
        good="자기 돈을 효율적으로 굴려 이익을 잘 냅니다.",
        bad="자기 돈에 비해 버는 돈이 적습니다.",
        negative="마이너스입니다. 이 기간에 순손실(적자)을 냈다는 뜻입니다.",
    ),
    Metric(
        key="영업이익률(%)", label="영업이익률", unit="%", group="수익성", higher_is_better=True,
        points=[(0, 0), (5, 35), (10, 60), (20, 90), (30, 100)],
        why="물건을 팔아 남기는 비율로 '본업 실력'을 봅니다.",
        good="팔면 많이 남는 장사를 하고 있습니다.",
        bad="팔아도 남는 것이 적습니다. 경쟁이 치열할 수 있습니다.",
        negative="마이너스입니다. 본업에서 손해를 보고 있다는 뜻입니다(영업적자).",
        required=False,
    ),
    Metric(
        key="부채비율(%)", label="부채비율", unit="%", group="안정성", higher_is_better=False,
        points=[(50, 100), (100, 80), (200, 45), (300, 20), (400, 0)],
        why="자기 돈에 비해 빚이 얼마나 많은지 봅니다.",
        good="빚이 적어 불황이 와도 버틸 힘이 있습니다.",
        bad="빚이 많아 금리가 오르거나 실적이 나빠지면 위험할 수 있습니다.",
        digits=0,
    ),
    Metric(
        key="PER", label="PER", unit="배", group="가치", higher_is_better=False,
        points=[(4, 100), (8, 85), (12, 65), (20, 35), (35, 0)],
        why="지금 주가가 1년 이익의 몇 배인지, 즉 비싼지 싼지 봅니다.",
        good="벌어들이는 이익에 비해 주가가 싼 편입니다.",
        bad="이익에 비해 주가가 비싼 편입니다. 기대가 이미 반영됐을 수 있습니다.",
    ),
    Metric(
        key="PBR", label="PBR", unit="배", group="가치", higher_is_better=False,
        points=[(0.4, 100), (0.8, 85), (1.5, 60), (3.0, 25), (5.0, 0)],
        why="회사가 가진 재산에 비해 주가가 몇 배인지 봅니다.",
        good="가진 재산에 비해 주가가 싼 편입니다.",
        bad="재산에 비해 주가가 비쌉니다. 브랜드·기술 기대가 클 수도 있습니다.",
    ),
    Metric(
        key="배당수익률(%)", label="배당수익률", unit="%", group="배당", higher_is_better=True,
        points=[(0, 0), (1, 30), (2.5, 65), (4, 90), (6, 100)],
        why="지금 주가로 샀을 때 배당이 연 몇 %인지 봅니다.",
        good="주가가 안 올라도 현금이 꾸준히 들어오는 편입니다.",
        bad="배당이 거의 없습니다. 성장에 재투자하는 회사일 수도 있습니다.",
        required=False,
    ),
    # ── 아래 둘은 '경영을 믿을 만한가'를 지나온 실적으로 대신 봅니다 ──
    # 사람(대표이사)을 점수로 매길 수는 없지만, 여러 해의 성적표는 숫자로 남습니다.
    Metric(
        key="흑자비율(%)", label="흑자 지속", unit="%", group="꾸준함", higher_is_better=True,
        points=[(0, 0), (50, 40), (75, 70), (90, 90), (100, 100)],
        why="최근 보고서들 중 몇 %에서 이익을 냈는지 봅니다.",
        good="여러 해 꾸준히 이익을 내 온 회사입니다.",
        bad="적자를 낸 기간이 잦습니다. 실적이 들쭉날쭉합니다.",
        required=False, digits=0,
    ),
    Metric(
        key="매출성장(%)", label="매출 성장", unit="%", group="꾸준함", higher_is_better=True,
        points=[(-30, 0), (-10, 25), (0, 50), (20, 80), (50, 100)],
        why="가장 오래된 보고서 대비 매출이 얼마나 늘었는지 봅니다.",
        good="사업 규모가 커지고 있습니다.",
        bad="매출이 줄고 있습니다. 사업이 위축되는 중일 수 있습니다.",
        negative="매출이 예전보다 줄었습니다. 파는 규모 자체가 작아지고 있습니다.",
        required=False, digits=1,
    ),
]

# 묶음별 가중치 모음 (합이 100 이 되도록)
WEIGHT_PRESETS: dict[str, dict[str, int]] = {
    "균형 (기본)":       {"수익성": 25, "안정성": 15, "가치": 25, "배당": 15, "꾸준함": 20},
    "안정성 중시":       {"수익성": 20, "안정성": 30, "가치": 15, "배당": 15, "꾸준함": 20},
    "저평가(가치) 중시":  {"수익성": 20, "안정성": 10, "가치": 45, "배당": 10, "꾸준함": 15},
    "배당 중시":         {"수익성": 15, "안정성": 20, "가치": 10, "배당": 40, "꾸준함": 15},
    "돈 잘 버는 회사 중시": {"수익성": 45, "안정성": 10, "가치": 15, "배당": 5, "꾸준함": 25},
    "꾸준한 회사 중시":    {"수익성": 20, "안정성": 20, "가치": 15, "배당": 10, "꾸준함": 35},
}

GROUPS = ["수익성", "안정성", "가치", "배당", "꾸준함"]


def score_one(metric: Metric, value) -> float | None:
    """
    지표값 하나를 0~100 점으로 바꿉니다.

    points 에 적힌 눈금 사이는 직선으로 이어서 계산합니다.
    예) ROE 눈금이 (10, 60), (15, 85) 라면 ROE 12.5% 는 72.5점이 됩니다.
    """
    if value is None or pd.isna(value):
        return None
    v = float(value)
    pts = metric.points

    if v <= pts[0][0]:
        return float(pts[0][1])
    if v >= pts[-1][0]:
        return float(pts[-1][1])

    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= v <= x2:
            if x2 == x1:
                return float(y2)
            ratio = (v - x1) / (x2 - x1)
            return float(y1 + (y2 - y1) * ratio)
    return None


MIN_PEERS = 5   # 업종 안에 이만큼은 있어야 '같은 업종 비교'가 의미 있습니다


def sector_relative_scores(df: pd.DataFrame, sector_col: str = "업종") -> pd.DataFrame:
    """
    같은 업종 안에서 몇 등쯤인지를 0~100 점으로 바꿉니다.

    왜 필요한가요?
      부채비율 200%는 소프트웨어 회사에는 위험 신호지만 은행에는 평범합니다.
      절대 기준 하나로 모든 업종을 재면 은행·건설은 늘 낮은 점수를 받습니다.
      그래서 '같은 업종 사람들끼리 줄 세웠을 때 몇 등인가'로 바꿔서 봅니다.
      (백분위: 업종에서 가장 좋으면 100점, 한가운데면 50점)

    업종을 모르거나 같은 업종 종목이 너무 적으면(MIN_PEERS 미만)
    이 방식을 쓸 수 없으므로 빈칸으로 두고, 부르는 쪽에서 절대 기준을 씁니다.
    """
    out = pd.DataFrame(index=df.index)
    sectors = df[sector_col].fillna("업종 미상")
    sizes = sectors.map(sectors.value_counts())
    usable = (sectors != "업종 미상") & (sizes >= MIN_PEERS)

    for m in METRICS:
        values = pd.to_numeric(df[m.key], errors="coerce")
        # 낮을수록 좋은 지표(부채비율·PER·PBR)는 부호를 뒤집어 줄을 세웁니다.
        ranked_input = values if m.higher_is_better else -values
        pct = ranked_input.groupby(sectors).rank(pct=True) * 100
        pct = pct.where(usable)
        out[f"점수_{m.label}"] = pct.round(1)

    out["업종비교가능"] = usable
    out["업종내종목수"] = sizes
    return out


def score_table(
    df: pd.DataFrame,
    weights: dict[str, int],
    mode: str = "절대 기준",
) -> pd.DataFrame:
    """
    전 종목 표에 지표별 점수와 총점을 붙여 돌려줍니다.

    mode
      "절대 기준"    : 업종과 상관없이 정해진 눈금으로 점수를 매깁니다.
      "같은 업종 비교" : 같은 업종 안에서 몇 등인지로 점수를 매깁니다.
                        업종을 모르거나 같은 업종이 5곳 미만이면 절대 기준을 씁니다.

    - 핵심 지표(required=True)가 하나라도 없으면 '자료 부족'으로 표시해 순위에서 뺍니다.
      (ETF 는 재무제표가 없어 대부분 여기에 해당합니다)
    - 묶음 점수 = 그 묶음에 속한 지표 점수의 평균
    - 총점 = 묶음 점수 × 가중치의 합 ÷ 100
    """
    out = df.copy()

    for m in METRICS:
        out[f"점수_{m.label}"] = out[m.key].map(lambda v, mm=m: score_one(mm, v))

    out["업종비교적용"] = False
    if mode == "같은 업종 비교" and "업종" in out.columns:
        rel = sector_relative_scores(out)
        for m in METRICS:
            col = f"점수_{m.label}"
            # 업종 비교가 가능한 종목만 상대 점수로 갈아끼웁니다.
            out[col] = rel[col].where(rel["업종비교가능"], out[col])
        out["업종비교적용"] = rel["업종비교가능"]
        out["업종내종목수"] = rel["업종내종목수"]

    required = [f"점수_{m.label}" for m in METRICS if m.required]
    out["자료충분"] = out[required].notna().all(axis=1)

    for g in GROUPS:
        cols = [f"점수_{m.label}" for m in METRICS if m.group == g]
        out[f"묶음_{g}"] = out[cols].mean(axis=1, skipna=True)

    total_weight = sum(weights.get(g, 0) for g in GROUPS)
    if total_weight <= 0:
        total_weight = 1

    total = 0
    for g in GROUPS:
        w = weights.get(g, 0)
        # 그 묶음 점수가 없으면(예: 배당 정보 없음) 0 점으로 봅니다.
        total = total + out[f"묶음_{g}"].fillna(0) * w
    out["총점"] = (total / total_weight).round(1)

    return out


def comment_for(metric: Metric, value, score) -> str:
    """지표 하나에 대한 한 줄 해석을 만듭니다."""
    if score is None or pd.isna(score):
        return "자료가 없어 점수를 매기지 못했습니다."
    # 마이너스 값은 뜻이 달라서(이익률은 '적자', 매출성장은 '매출 감소') 따로 알려줍니다.
    if metric.higher_is_better and pd.notna(value) and float(value) < 0 and metric.negative:
        return metric.negative
    if score >= 70:
        return metric.good
    if score >= 40:
        return "보통 수준입니다. " + (metric.good if score >= 55 else metric.bad)
    return metric.bad


def explain(row: pd.Series) -> list[dict]:
    """한 종목이 왜 그 점수인지, 지표별 근거를 만들어 돌려줍니다."""
    rows = []
    for m in METRICS:
        value = row.get(m.key)
        score = row.get(f"점수_{m.label}")
        rows.append({
            "묶음": m.group,
            "지표": m.label,
            "값": "—" if pd.isna(value) else f"{float(value):,.{m.digits}f}{m.unit}",
            # 점수 칸은 막대그래프로 그려지므로 반드시 숫자(또는 빈값)여야 합니다.
            "점수": None if (score is None or pd.isna(score)) else round(float(score)),
            "이 지표를 보는 이유": m.why,
            "해석": comment_for(m, value, score),
        })
    return rows


def summary_sentence(row: pd.Series) -> str:
    """근거를 한 문단으로 요약합니다 (가장 높은 점수 2개, 가장 낮은 점수 1개)."""
    scored = [
        (m, row.get(f"점수_{m.label}"), row.get(m.key))
        for m in METRICS
        if pd.notna(row.get(f"점수_{m.label}"))
    ]
    if not scored:
        return "점수를 매길 자료가 없습니다."

    scored.sort(key=lambda t: t[1], reverse=True)
    best = scored[:2]
    worst = scored[-1]

    parts = [
        f"**{m.label} {float(v):,.{m.digits}f}{m.unit}** ({round(s)}점) — {comment_for(m, v, s)}"
        for m, s, v in best
    ]
    text = " / ".join(parts)

    if worst[1] < 55 and worst[0].label not in [m.label for m, _, _ in best]:
        m, s, v = worst
        text += (
            f"<br>다만 **{m.label} {float(v):,.{m.digits}f}{m.unit}** "
            f"({round(s)}점) — {comment_for(m, v, s)}"
        )
    return text
