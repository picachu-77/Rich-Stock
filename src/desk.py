# -*- coding: utf-8 -*-
"""
여섯 부서 — 증권사처럼 나눠서 한 종목을 봅니다.

    01 스크리닝부    살펴볼 값어치가 있는 종목을 고릅니다   ← 사람이 짠 규칙(SQL)
    02 기술적분석부  차트와 추세, 거래를 읽습니다
    03 펀더멘탈부    실적과 값이 싼지 비싼지를 봅니다
    04 마켓부        시장 국면과 그 회사에 생긴 일을 봅니다
    05 리스크관리부  위 셋에 **반대하고** 잃을 거리를 찾습니다
    06 운용부        넷을 모아 결론을 냅니다

★ 계산은 파이썬이, 해석은 AI가 ★
  이동평균·변동성·전년 대비 같은 것은 여기서 계산해서 **숫자로** 넘깁니다.
  AI 에게 종가 250개를 주고 "이동평균 내봐" 하면 틀립니다. 대신 "지금값이
  60일 평균보다 4.2% 위" 같은 사실을 주고 뜻을 해석하게 합니다.

★ 01 스크리닝부에는 AI 를 쓰지 않습니다 ★
  '시가총액 1,000억 넘고 PER 15 아래' 같은 거르기는 창고가 훨씬 빠르고
  정확합니다. 여기에 AI 를 넣으면 느려지고 비싸지고 덜 정확해집니다.

★ 자료에 없는 것은 말하지 않게 합니다 ★
  각 부서는 **자기 몫의 자료만** 받습니다. 그리고 '자료에 없으면 없다고
  하라' 를 지침에 박아둡니다. 숫자를 지어내면 이 앱이 하려던 일과
  정반대가 됩니다.

★ 05 리스크관리부는 일부러 반대편에 세웁니다 ★
  02~04 의 보고서를 그대로 읽히고, "이 판단이 틀리려면 무엇이 사실이어야
  하는가" 를 쓰게 합니다. AI 가 한쪽으로 쏠리는 것을 구조로 막습니다.
"""

from __future__ import annotations

import json
import os
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from .db import fetch_all

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# 부서마다 쓰는 모델이 다릅니다.
#   02·03·04 는 주어진 숫자를 읽고 정리하는 일이라 빠른 모델로 충분합니다.
#   05·06 은 '반대편을 찾고' '결론을 내는' 일이라 판단력이 필요합니다.
FAST = os.getenv("DESK_MODEL_FAST", "claude-haiku-4-5-20251001")
DEEP = os.getenv("DESK_MODEL_DEEP", "claude-sonnet-5")


class DeskError(RuntimeError):
    pass


# ══════════════════════════════════════════════════════════════
#  01 스크리닝부 — 사람이 짠 규칙. AI 안 씁니다.
# ══════════════════════════════════════════════════════════════
def screen(conn, limit: int = 20, min_cap_eok: int = 1000,
           min_value_eok: float = 10.0) -> list[tuple]:
    """
    살펴볼 값어치가 있는 종목을 고릅니다.

    왜 이렇게 거르나:
      · 시가총액이 너무 작으면 한두 사람이 값을 흔듭니다.
      · 그날 오간 돈이 적으면 **팔고 싶을 때 못 팝니다.** 아무리 좋아
        보여도 못 파는 종목은 후보가 아닙니다.
      · 재무가 한 줄도 없으면 03 펀더멘탈부가 할 일이 없습니다.
      · ETF 는 회사가 아니라 이 구조로 볼 것이 아닙니다.
    """
    return fetch_all(conn, """
        WITH last AS (
          SELECT DISTINCT ON (dp.code)
                 dp.code, dp.close, dp.change_pct, dp.volume, dp.market_cap
            FROM daily_price dp
           WHERE dp.trade_date >= (SELECT max(trade_date) FROM daily_price) - 7
           ORDER BY dp.code, dp.trade_date DESC
        )
        SELECT t.code, t.name, t.sector_name, l.close, l.market_cap,
               (l.volume::numeric * l.close) / 100000000 AS 거래대금억
          FROM ticker t
          JOIN last l ON l.code = t.code
         WHERE t.is_active
           AND t.kind <> 'ETF'
           AND t.currency = 'KRW'
           AND l.market_cap >= %s
           AND (l.volume::numeric * l.close) / 100000000 >= %s
           AND EXISTS (SELECT 1 FROM financial f WHERE f.code = t.code)
         ORDER BY l.market_cap DESC
         LIMIT %s
    """, (min_cap_eok, min_value_eok, limit))


# ══════════════════════════════════════════════════════════════
#  부서별 자료 — 계산은 여기서 끝냅니다
# ══════════════════════════════════════════════════════════════
def _pct(a: float, b: float) -> float | None:
    return None if not b else round((a / b - 1) * 100, 2)


def tech_facts(conn, code: str) -> dict:
    """02 기술적분석부가 볼 것. 종가에서 뽑아낸 사실들."""
    rows = fetch_all(conn, """
        SELECT trade_date, close, volume
          FROM daily_price
         WHERE code = %s AND close IS NOT NULL
         ORDER BY trade_date DESC
         LIMIT 260
    """, (code,))
    if len(rows) < 30:
        return {"자료부족": f"시세가 {len(rows)}일치뿐입니다"}

    closes = [float(r[1]) for r in rows]          # 최근이 앞
    vols = [float(r[2] or 0) for r in rows]
    now = closes[0]

    def ma(n: int) -> float | None:
        return round(sum(closes[:n]) / n, 2) if len(closes) >= n else None

    # 하루하루 오르내린 폭으로 변동성을 냅니다 (연 기준으로 바꿉니다)
    daily = [closes[i] / closes[i + 1] - 1 for i in range(min(60, len(closes) - 1))]
    vol = round(statistics.pstdev(daily) * (252 ** 0.5) * 100, 1) if len(daily) > 5 else None

    hi, lo = max(closes), min(closes)
    최근20 = sum(v * c for v, c in zip(vols[:20], closes[:20])) / 20 / 1e8
    이전20 = (sum(v * c for v, c in zip(vols[20:40], closes[20:40])) / 20 / 1e8
              if len(vols) >= 40 else None)

    facts = {
        "오늘 종가": now,
        "20일 평균": ma(20), "60일 평균": ma(60), "120일 평균": ma(120),
        "5일 수익률(%)": _pct(now, closes[5]) if len(closes) > 5 else None,
        "20일 수익률(%)": _pct(now, closes[20]) if len(closes) > 20 else None,
        "60일 수익률(%)": _pct(now, closes[60]) if len(closes) > 60 else None,
        "1년 최고": hi, "1년 최저": lo,
        "1년 최고 대비(%)": _pct(now, hi),
        "1년 최저 대비(%)": _pct(now, lo),
        "연 변동성(%)": vol,
        "최근 20일 하루 평균 거래대금(억)": round(최근20, 1),
        "그 앞 20일 하루 평균 거래대금(억)": round(이전20, 1) if 이전20 else None,
        "본 기간": f"{rows[-1][0]} ~ {rows[0][0]} ({len(rows)}거래일)",
    }
    for n in (20, 60, 120):
        m = ma(n)
        if m:
            facts[f"{n}일 평균 대비(%)"] = _pct(now, m)
    return facts


def fundamental_facts(conn, code: str) -> dict:
    """03 펀더멘탈부가 볼 것. 분기 실적과 같은 업종 견줌."""
    rows = fetch_all(conn, """
        SELECT fiscal_year, fiscal_quarter, revenue, operating_profit,
               net_income, roe, debt_ratio, op_margin
          FROM financial WHERE code = %s
         ORDER BY fiscal_year DESC, fiscal_quarter DESC LIMIT 12
    """, (code,))
    if not rows:
        return {"자료부족": "재무 자료가 없습니다"}

    억 = lambda v: None if v is None else round(float(v) / 1e8)
    분기 = [{
        "기": f"{r[0]}년 {r[1]}분기",
        "매출(억)": 억(r[2]), "영업이익(억)": 억(r[3]), "순이익(억)": 억(r[4]),
        "ROE(%)": float(r[5]) if r[5] is not None else None,
        "부채비율(%)": float(r[6]) if r[6] is not None else None,
        "영업이익률(%)": float(r[7]) if r[7] is not None else None,
    } for r in rows]

    # 작년 같은 분기와 견줍니다. 계절을 타는 회사가 많아 앞 분기와
    # 견주면 틀린 말이 됩니다.
    찾기 = {(r[0], r[1]): r for r in rows}
    yoy = []
    for r in rows[:4]:
        전 = 찾기.get((r[0] - 1, r[1]))
        if not 전:
            continue
        yoy.append({
            "기": f"{r[0]}년 {r[1]}분기",
            "매출 전년대비(%)": _pct(float(r[2]), float(전[2])) if r[2] and 전[2] else None,
            "영업이익 전년대비(%)": (_pct(float(r[3]), float(전[3]))
                                if r[3] and 전[3] and float(전[3]) > 0 else None),
            "영업이익 흑자전환": bool(r[3] and 전[3] and float(전[3]) <= 0 < float(r[3])),
        })

    피어 = fetch_all(conn, """
        SELECT count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY dp.per),
               percentile_cont(0.5) WITHIN GROUP (ORDER BY dp.pbr)
          FROM ticker t
          JOIN LATERAL (SELECT per, pbr FROM daily_price
                         WHERE code = t.code AND per > 0
                         ORDER BY trade_date DESC LIMIT 1) dp ON TRUE
         WHERE t.is_active AND t.sector_name = (
                 SELECT sector_name FROM ticker WHERE code = %s)
    """, (code,))
    나 = fetch_all(conn, """
        SELECT per, pbr, div_yield FROM daily_price
         WHERE code = %s ORDER BY trade_date DESC LIMIT 1
    """, (code,))

    out = {"분기 실적(최근이 위)": 분기, "작년 같은 분기와 견줌": yoy}
    if 나 and 나[0]:
        out["지금 PER"] = float(나[0][0]) if 나[0][0] else None
        out["지금 PBR"] = float(나[0][1]) if 나[0][1] else None
        out["배당수익률(%)"] = float(나[0][2]) if 나[0][2] else None
    if 피어 and 피어[0] and 피어[0][0]:
        out["같은 업종"] = {
            "회사 수": int(피어[0][0]),
            "PER 가운데값": round(float(피어[0][1]), 2) if 피어[0][1] else None,
            "PBR 가운데값": round(float(피어[0][2]), 2) if 피어[0][2] else None,
        }
    return out


def market_facts(conn) -> dict:
    """04 마켓부가 볼 것 — 시장 전체. 종목과 무관해서 한 번만 모읍니다."""
    idx = fetch_all(conn, """
        SELECT DISTINCT ON (symbol) symbol, close, change_pct
          FROM market_index
         WHERE trade_date >= (SELECT max(trade_date) FROM market_index) - 7
         ORDER BY symbol, trade_date DESC
    """)
    이름 = {"^KS11": "코스피", "^KQ11": "코스닥", "^IXIC": "나스닥",
            "^GSPC": "S&P500", "KRW=X": "원달러", "^TNX": "미국10년금리",
            "^VIX": "공포지수", "CL=F": "국제유가", "GC=F": "금"}
    breadth = fetch_all(conn, """
        SELECT count(*) FILTER (WHERE change_pct > 0),
               count(*) FILTER (WHERE change_pct < 0)
          FROM daily_price
         WHERE trade_date = (SELECT max(trade_date) FROM daily_price)
    """)
    return {
        "지수와 지표": {이름.get(r[0], r[0]): {"값": float(r[1]) if r[1] else None,
                                          "전일대비(%)": float(r[2]) if r[2] else None}
                    for r in idx if r[0] in 이름},
        "오늘 시장": {"오른 종목": int(breadth[0][0] or 0),
                  "내린 종목": int(breadth[0][1] or 0)} if breadth else None,
    }


def company_news(conn, code: str) -> dict:
    """04 마켓부가 볼 것 — 그 회사에 생긴 일."""
    공시 = fetch_all(conn, """
        SELECT rcept_dt, report_nm, category FROM disclosure
         WHERE code = %s ORDER BY rcept_dt DESC LIMIT 12
    """, (code,))
    리포트 = fetch_all(conn, """
        SELECT written_at, title, opinion, target_price, house FROM report
         WHERE code = %s AND written_at >= current_date - 180
         ORDER BY written_at DESC LIMIT 8
    """, (code,))
    return {
        "최근 공시": [{"날짜": str(r[0]), "제목": r[1], "갈래": r[2]} for r in 공시],
        "증권사 리포트(6개월)": [{"날짜": str(r[0]), "제목": r[1], "의견": r[2],
                            "목표주가": int(r[3]) if r[3] else None, "증권사": r[4]}
                           for r in 리포트],
    }


def risk_facts(conn, code: str) -> dict:
    """05 리스크관리부가 볼 것 — 잃을 거리."""
    위험공시 = fetch_all(conn, """
        SELECT rcept_dt, report_nm FROM disclosure
         WHERE code = %s AND category = '위험'
         ORDER BY rcept_dt DESC LIMIT 8
    """, (code,))
    조달 = fetch_all(conn, """
        SELECT rcept_dt, report_nm FROM disclosure
         WHERE code = %s AND category = '조달'
         ORDER BY rcept_dt DESC LIMIT 6
    """, (code,))
    유동성 = fetch_all(conn, """
        SELECT avg(volume::numeric * close) / 100000000
          FROM (SELECT volume, close FROM daily_price
                 WHERE code = %s AND close IS NOT NULL
                 ORDER BY trade_date DESC LIMIT 20) t
    """, (code,))
    의견 = fetch_all(conn, """
        SELECT count(*) FILTER (WHERE opinion = '매수'),
               count(*) FILTER (WHERE opinion = '중립'),
               count(*) FILTER (WHERE opinion = '매도')
          FROM report WHERE code = %s AND written_at >= current_date - 180
    """, (code,))
    return {
        "조심할 일 공시": [{"날짜": str(r[0]), "제목": r[1]} for r in 위험공시] or "없음",
        "돈 구한 공시": [{"날짜": str(r[0]), "제목": r[1]} for r in 조달] or "없음",
        "최근 20일 하루 평균 거래대금(억)": (round(float(유동성[0][0]), 1)
                                   if 유동성 and 유동성[0][0] else None),
        "증권사 의견 쏠림": {"매수": int(의견[0][0]), "중립": int(의견[0][1]),
                      "매도": int(의견[0][2])} if 의견 else None,
        "참고": ("증권사 리포트는 매도 의견이 거의 나오지 않습니다. "
               "'매수 의견이 많다' 는 것은 근거가 되지 못합니다."),
    }


# ══════════════════════════════════════════════════════════════
#  부서 지침
# ══════════════════════════════════════════════════════════════
# 모든 부서에 공통으로 붙는 규칙입니다. 이 앱이 하려던 일과
# 정반대가 되지 않게 하는 울타리입니다.
공통 = """당신은 증권사의 한 부서입니다. 한국어로, 주식을 처음 하는
사람도 읽을 수 있는 쉬운 말로 씁니다.

반드시 지킬 것
- **주어진 자료에만 근거해서** 말합니다. 자료에 없는 사실을 끌어오지
  않습니다. 회사 이름을 안다고 해서 기억에 있는 것을 쓰면 안 됩니다.
- 자료에 없으면 "자료 없음" 이라고 씁니다. 그럴듯하게 메우지 않습니다.
- 숫자를 말할 때는 자료에 있는 값을 그대로 씁니다. 반올림한 새 숫자를
  만들지 않습니다.
- 앞일을 맞히려 하지 않습니다. "오를 것" "갈 것" 같은 말을 쓰지 않습니다.
  지금 자료에서 **무엇이 보이는가**만 씁니다.
- 짧게 씁니다. 같은 말을 다시 하지 않습니다."""

부서지침: dict[str, tuple[str, str, str]] = {
    # 이름: (모델, 역할, 시킬 일)
    "기술적분석부": (FAST, "차트와 추세, 거래를 읽는 부서", """
주어진 것은 종가에서 계산해 둔 **사실**입니다. 계산은 이미 끝났으니
다시 계산하지 말고 뜻만 읽어주세요.

다음 순서로 5줄 이내:
1. 지금 값이 평균선들보다 위인가 아래인가, 그게 무슨 뜻인가
2. 최근 흐름 (5일·20일·60일 수익률을 같이 보고)
3. 1년 최고·최저 사이 어디쯤인가
4. 거래가 늘고 있는가 줄고 있는가
5. 변동성이 큰 편인가

★ 기술적 지표는 '지금까지 이랬다' 이지 '앞으로 이럴 것' 이 아닙니다.
  그 점을 마지막에 한 줄로 적으세요."""),

    "펀더멘탈부": (FAST, "실적과 값이 싼지 비싼지를 보는 부서", """
다음 순서로 6줄 이내:
1. 매출이 늘고 있는가 (작년 같은 분기와 견준 값을 쓰세요)
2. 영업이익은 어떤가. 매출은 느는데 이익이 줄면 그 점을 짚으세요
3. ROE·영업이익률의 방향
4. 부채비율이 어떤가
5. PER·PBR 이 같은 업종 가운데값과 견줘 어떤가
6. 배당은 어떤가 (자료 있을 때만)

★ 분기 실적은 계절을 탑니다. 앞 분기가 아니라 **작년 같은 분기**와
  견주세요. 자료에 그렇게 계산된 값이 들어 있습니다."""),

    "마켓부": (FAST, "시장 국면과 그 회사에 생긴 일을 보는 부서", """
다음 순서로 5줄 이내:
1. 지금 시장이 어떤 국면인가 (지수·금리·공포지수·환율을 같이 보고)
2. 그 국면이 이런 회사에 유리한가 불리한가
3. 최근 공시 중 눈에 띄는 것 (제목만 보고 아는 범위에서)
4. 증권사 리포트가 뭐라고 하는가
5. 이 회사에 생긴 일과 시장 전체를 나눠서 보면 어떤가

★ 공시는 제목만 주어집니다. 제목으로 알 수 없는 속뜻을 지어내지
  마세요. "제목만으로는 알 수 없다" 고 쓰면 됩니다."""),

    "리스크관리부": (DEEP, "아이디어에 반대하고 자본을 지키는 부서", """
당신의 일은 앞 세 부서에 **반대하는 것**입니다. 좋게 봐주는 것이
아니라, 이 종목을 샀을 때 **어떻게 잃게 되는지**를 찾는 것입니다.

다음을 반드시 씁니다 (7줄 이내):
1. 앞 부서 보고서에서 **가장 약한 대목** 하나를 짚으세요
2. 이 종목을 샀을 때 돈을 잃는 가장 그럴듯한 경로
3. 팔고 싶을 때 팔 수 있는가 (거래대금을 보세요)
4. 빚은 감당할 수준인가
5. 조심할 일 공시·돈 구한 공시가 있으면 무슨 뜻인가
6. 증권사 의견 쏠림 — 매수가 많다는 것은 근거가 아닙니다
7. **이 판단이 틀리려면 무엇이 사실이어야 하는가**

★ 아무 위험도 못 찾겠으면 그렇게 쓰되, 왜 그런지 근거를 대세요.
  '위험 없음' 은 대개 안 본 것입니다."""),

    "운용부": (DEEP, "네 부서를 모아 결론을 내는 부서", """
네 부서의 보고서를 읽고 결론을 냅니다.

반드시 이 차례로:
1. **의견** — 다음 셋 중 하나만: `관심` / `보류` / `제외`
   · 관심 = 더 알아볼 값어치가 있다
   · 보류 = 지금은 판단할 근거가 모자라다
   · 제외 = 지금 보기에 안 맞는다
   ※ '사세요' 라고 쓰지 않습니다. 사는 것은 사람이 정합니다.
2. **한 줄 이유** — 왜 그렇게 봤는가
3. **가장 크게 갈린 지점** — 부서들 의견이 어디서 엇갈렸는가
4. **이 판단이 무너지는 조건** — 무엇이 사실로 드러나면 생각을 바꿔야
   하는가. 나중에 되돌아볼 수 있게 **확인 가능한 것**으로 쓰세요.
   (예: "다음 분기 매출이 또 줄면")
5. **직접 확인할 것** — 사람이 원문을 봐야 할 것 한두 가지

★ 이 보고서는 참고 자료이지 권유가 아닙니다. 마지막에 그 점을
  한 줄로 적으세요."""),
}


@dataclass
class Report:
    desk: str
    text: str
    model: str


def ask(system: str, user: str, model: str, max_tokens: int = 900) -> str:
    """Claude 에게 한 번 묻습니다. 부품 없이 표준 도구만 씁니다."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise DeskError(
            "ANTHROPIC_API_KEY 가 없습니다.\n"
            "  GitHub > Settings > Secrets 에 넣어주세요.\n"
            "  ★ 열쇠를 채팅에 붙여넣지 마세요 ★")

    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode("utf-8")

    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": API_VERSION,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        # 열쇠는 절대 찍지 않습니다
        raise DeskError(f"Claude 호출 실패 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DeskError(f"Claude 에 닿지 못했습니다: {exc.reason}") from exc

    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(parts).strip()


def run_desk(name: str, 자료: dict, 앞선보고: list[Report] | None = None,
             dry: bool = False) -> Report:
    """부서 하나를 돌립니다."""
    model, 역할, 시킬일 = 부서지침[name]
    system = f"{공통}\n\n당신은 **{name}** 입니다. {역할}.\n{시킬일}"

    덩이 = [f"## 자료\n```json\n{json.dumps(자료, ensure_ascii=False, indent=1, default=str)}\n```"]
    if 앞선보고:
        덩이.append("## 앞선 부서 보고서\n" + "\n\n".join(
            f"### {r.desk}\n{r.text}" for r in 앞선보고))
    user = "\n\n".join(덩이)

    if dry:
        return Report(name, f"[시험] 지침 {len(system):,}자 · 자료 {len(user):,}자 "
                            f"· 모델 {model}", model)
    return Report(name, ask(system, user, model), model)
