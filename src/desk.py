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
#
# ★ 단기와 장기는 아예 다른 거르기입니다 ★
#   같은 종목이 단기로는 좋고 장기로는 나쁠 수 있고, 그 반대도 됩니다.
#   한 가지로 걸러놓고 "단기용인지 장기용인지" 를 AI 에게 묻는 것은
#   순서가 거꾸로입니다. 애초에 찾는 것이 다릅니다.
#
#     장기 — 실적이 꾸준히 늘고, 빚이 적고, 값이 과하지 않은 회사
#     단기 — 최근 흐름과 거래가 살아난 회사
#
# ★ 둘 다에 공통으로 걸어두는 것 ★
#   하루 거래대금 최소선. 아무리 좋아 보여도 **팔고 싶을 때 못 파는**
#   종목은 후보가 아닙니다. 사는 것은 언제나 쉽습니다.

_공통 = """
           AND t.is_active
           AND t.kind <> 'ETF'
           AND t.currency = 'KRW'
           AND l.market_cap >= %(cap)s
           AND l.거래대금억 >= %(value)s
"""

_LAST = """
        WITH last AS (
          SELECT DISTINCT ON (dp.code)
                 dp.code, dp.close, dp.change_pct, dp.volume, dp.market_cap,
                 dp.per, dp.pbr,
                 (dp.volume::numeric * dp.close) / 100000000 AS 거래대금억
            FROM daily_price dp
           WHERE dp.trade_date >= (SELECT max(trade_date) FROM daily_price) - 7
           ORDER BY dp.code, dp.trade_date DESC
        )
"""


def screen_long(conn, limit: int = 10, min_cap_eok: int = 1000,
                min_value_eok: float = 10.0) -> list[tuple]:
    """
    장기 — 들고 있을 회사를 찾습니다.

    보는 것:
      · 매출이 작년 같은 분기보다 늘었는가   (계절을 타므로 같은 분기끼리)
      · 영업이익이 흑자인가
      · ROE 가 쓸 만한가, 부채비율이 과하지 않은가
      · 값이 터무니없지 않은가 (PER)

    ★ 왜 PER 상한을 두나 ★
      좋은 회사라도 너무 비싸게 사면 오래 들고 있어도 손해입니다.
      다만 PER 이 낮다고 싼 것도 아닙니다 — 그 판단은 03 펀더멘탈부가
      업종 가운데값과 견줘서 합니다. 여기서는 터무니없는 것만 걷어냅니다.
    """
    return fetch_all(conn, _LAST + """
        , 최근 AS (
          SELECT DISTINCT ON (code) code, fiscal_year, fiscal_quarter,
                 revenue, operating_profit, roe, debt_ratio
            FROM financial
           ORDER BY code, fiscal_year DESC, fiscal_quarter DESC
        )
        SELECT t.code, t.name, t.sector_name, l.close, l.market_cap,
               l.거래대금억, f.roe, f.debt_ratio, l.per
          FROM ticker t
          JOIN last l  ON l.code = t.code
          JOIN 최근 f  ON f.code = t.code
          -- 작년 같은 분기
          JOIN financial p ON p.code = t.code
                          AND p.fiscal_year = f.fiscal_year - 1
                          AND p.fiscal_quarter = f.fiscal_quarter
         WHERE TRUE """ + _공통 + """
           AND f.operating_profit > 0
           AND f.revenue > p.revenue
           AND f.roe >= %(roe)s
           AND f.debt_ratio <= %(debt)s
           AND (l.per IS NULL OR (l.per > 0 AND l.per <= %(per)s))
         ORDER BY f.roe DESC
         LIMIT %(limit)s
    """, {"cap": min_cap_eok, "value": min_value_eok, "roe": 8.0,
          "debt": 150.0, "per": 40.0, "limit": limit})


def screen_short(conn, limit: int = 10, min_cap_eok: int = 1000,
                 min_value_eok: float = 30.0) -> list[tuple]:
    """
    단기 — 지금 움직이고 있는 회사를 찾습니다.

    보는 것:
      · 최근 5일 거래대금이 그 앞 20일보다 눈에 띄게 늘었는가
      · 20일 평균 위에 있는가
      · 변동성이 감당 못 할 정도는 아닌가

    ★ 거래대금 최소선을 장기보다 높게 잡습니다 ★
      단기는 들어갔다 나오는 일이라 더 자주 팝니다. 한산한 종목에서
      단기로 움직이면 사고팔 때마다 값이 밀립니다.

    ★ 변동성에 상한을 둡니다 ★
      많이 흔들리는 종목이 '기회' 처럼 보이지만, 그건 올라갈 폭이
      크다는 뜻인 만큼 내려갈 폭도 크다는 뜻입니다. 초보자가 가장
      크게 다치는 자리라 아예 후보에서 뺍니다.

    ★ 이 거르기는 '오를 종목' 을 찾는 것이 아닙니다 ★
      최근에 사람들이 몰렸다는 사실만 말합니다. 그게 왜인지,
      계속될 것인지는 02~05 부서가 봅니다.
    """
    return fetch_all(conn, _LAST + """
        , 흐름 AS (
          SELECT code,
                 avg(close) FILTER (WHERE rn <= 20)                AS ma20,
                 avg(volume::numeric * close) FILTER (WHERE rn <= 5)  / 1e8 AS 최근5,
                 avg(volume::numeric * close) FILTER (WHERE rn BETWEEN 6 AND 25) / 1e8 AS 이전20,
                 stddev_pop(수익률) FILTER (WHERE rn <= 60) * sqrt(252) * 100 AS 변동성
            FROM (
              SELECT code, close, volume,
                     row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn,
                     close / NULLIF(lag(close) OVER (PARTITION BY code ORDER BY trade_date), 0) - 1 AS 수익률
                FROM daily_price
               WHERE trade_date >= (SELECT max(trade_date) FROM daily_price) - 130
                 AND close IS NOT NULL
            ) x
           GROUP BY code
        )
        SELECT t.code, t.name, t.sector_name, l.close, l.market_cap,
               l.거래대금억,
               round(h.최근5::numeric, 1)   AS 최근5일거래대금억,
               round(h.이전20::numeric, 1)  AS 이전20일거래대금억,
               round(h.변동성::numeric, 1)  AS 변동성,
               round((l.close / h.ma20 - 1)::numeric * 100, 2) AS ma20대비
          FROM ticker t
          JOIN last l ON l.code = t.code
          JOIN 흐름 h ON h.code = t.code
         WHERE TRUE """ + _공통 + """
           AND h.ma20 IS NOT NULL
           AND l.close > h.ma20                      -- 20일 평균 위
           AND h.이전20 > 0
           AND h.최근5 >= h.이전20 * %(spike)s        -- 거래가 늘었다
           AND h.변동성 <= %(vol)s                    -- 너무 흔들리지 않는다
         ORDER BY (h.최근5 / h.이전20) DESC
         LIMIT %(limit)s
    """, {"cap": min_cap_eok, "value": min_value_eok, "spike": 1.5,
          "vol": 70.0, "limit": limit})


# 예전 이름. 장기 거르기를 가리킵니다.
def screen(conn, limit: int = 20, min_cap_eok: int = 1000,
           min_value_eok: float = 10.0) -> list[tuple]:
    return screen_long(conn, limit, min_cap_eok, min_value_eok)


# ══════════════════════════════════════════════════════════════
#  부서별 자료 — 계산은 여기서 끝냅니다
# ══════════════════════════════════════════════════════════════
def _pct(a: float, b: float) -> float | None:
    return None if not b else round((a / b - 1) * 100, 2)


def _rsi(closes: list[float], n: int = 14) -> float | None:
    """
    RSI — 최근에 오른 날과 내린 날의 힘을 견줍니다.

    closes 는 **최근이 앞**입니다. 계산은 오래된 쪽부터라 뒤집습니다.
    와일더의 원래 방식(지수평활)을 씁니다 — 단순평균으로 하면 증권사
    화면과 값이 달라져서 보는 사람이 '틀렸다' 고 여깁니다.
    """
    if len(closes) < n + 1:
        return None
    오래된순 = closes[::-1]
    변화 = [오래된순[i] - 오래된순[i - 1] for i in range(1, len(오래된순))]
    오름 = [max(d, 0.0) for d in 변화]
    내림 = [max(-d, 0.0) for d in 변화]
    평균오름 = sum(오름[:n]) / n
    평균내림 = sum(내림[:n]) / n
    for i in range(n, len(변화)):
        평균오름 = (평균오름 * (n - 1) + 오름[i]) / n
        평균내림 = (평균내림 * (n - 1) + 내림[i]) / n
    if 평균내림 == 0:
        return 100.0
    return round(100 - 100 / (1 + 평균오름 / 평균내림), 1)


def _ema(값들: list[float], n: int) -> list[float]:
    """지수이동평균. 값들은 오래된 것이 앞."""
    k = 2 / (n + 1)
    out = [값들[0]]
    for v in 값들[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _macd(closes: list[float]) -> dict | None:
    """
    MACD — 짧은 평균과 긴 평균이 벌어진 정도.

    12·26·9 를 그대로 씁니다. 다른 값을 쓰면 증권사 화면과 안 맞습니다.
    """
    if len(closes) < 35:
        return None
    오래된순 = closes[::-1]
    선 = [f - s for f, s in zip(_ema(오래된순, 12), _ema(오래된순, 26))]
    신호 = _ema(선, 9)
    막대, 이전막대 = 선[-1] - 신호[-1], 선[-2] - 신호[-2]
    return {
        "MACD선": round(선[-1], 2),
        "신호선": round(신호[-1], 2),
        "막대(선-신호)": round(막대, 2),
        "막대 방향": "늘고 있음" if 막대 > 이전막대 else "줄고 있음",
        "선이 신호선 위": 선[-1] > 신호[-1],
    }


def _levels(closes: list[float], now: float) -> dict:
    """
    받쳐줄 자리·막힐 자리를 **지어내지 않고** 찾습니다.

    ★ 선을 눈대중으로 긋지 않습니다 ★
      '여기가 지지선' 은 보는 사람마다 다릅니다. 대신 지난 1년 종가를
      스무 칸으로 나눠, **사람들이 실제로 오래 머물렀던 값대**를 찾습니다.
      많이 오갔던 값은 다시 왔을 때 막히거나 받쳐질 수 있는 자리입니다.

      이것도 '그럴 수 있다' 이지 '그렇게 된다' 가 아닙니다.
    """
    if len(closes) < 60:
        return {}
    lo, hi = min(closes), max(closes)
    if hi <= lo:
        return {}
    칸수 = 20
    폭 = (hi - lo) / 칸수
    통 = [0] * 칸수
    for c in closes:
        통[min(int((c - lo) / 폭), 칸수 - 1)] += 1

    def 두터운곳(아래: bool):
        후보 = []
        for i, n in enumerate(통):
            가운데 = lo + 폭 * (i + 0.5)
            맞음 = 가운데 < now if 아래 else 가운데 > now
            if 맞음:
                후보.append((n, 가운데))
        if not 후보:
            return None
        n, 값 = max(후보)
        return round(값), n

    out: dict = {}
    if (받침 := 두터운곳(True)):
        out["아래쪽에서 가장 오래 머문 값"] = 받침[0]
        out["그 값대에서 보낸 날수"] = 받침[1]
    if (막힘 := 두터운곳(False)):
        out["위쪽에서 가장 오래 머문 값"] = 막힘[0]
        out["그 값대에서 보낸 날수 "] = 막힘[1]
    return out


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

    ma20, ma60, ma120 = ma(20), ma(60), ma(120)
    # 정배열 = 짧은 평균이 긴 평균 위. 흔히 '추세가 살아 있다' 고 읽습니다.
    배열 = None
    if ma20 and ma60 and ma120:
        배열 = ("정배열 (20일 > 60일 > 120일)" if ma20 > ma60 > ma120
                else "역배열 (20일 < 60일 < 120일)" if ma20 < ma60 < ma120
                else "엇갈림")

    hi, lo = max(closes), min(closes)
    최근20 = sum(v * c for v, c in zip(vols[:20], closes[:20])) / 20 / 1e8
    이전20 = (sum(v * c for v, c in zip(vols[20:40], closes[20:40])) / 20 / 1e8
              if len(vols) >= 40 else None)

    facts = {
        "오늘 종가": now,
        "20일 평균": ma20, "60일 평균": ma60, "120일 평균": ma120,
        "평균선 배열": 배열,
        "5일 수익률(%)": _pct(now, closes[5]) if len(closes) > 5 else None,
        "20일 수익률(%)": _pct(now, closes[20]) if len(closes) > 20 else None,
        "60일 수익률(%)": _pct(now, closes[60]) if len(closes) > 60 else None,
        "1년 최고": hi, "1년 최저": lo,
        "1년 최고 대비(%)": _pct(now, hi),
        "1년 최저 대비(%)": _pct(now, lo),
        "연 변동성(%)": vol,
        "RSI(14)": _rsi(closes),
        "MACD(12,26,9)": _macd(closes),
        "최근 20일 하루 평균 거래대금(억)": round(최근20, 1),
        "그 앞 20일 하루 평균 거래대금(억)": round(이전20, 1) if 이전20 else None,
        "본 기간": f"{rows[-1][0]} ~ {rows[0][0]} ({len(rows)}거래일)",
    }
    for n in (20, 60, 120):
        m = ma(n)
        if m:
            facts[f"{n}일 평균 대비(%)"] = _pct(now, m)
    facts.update(_levels(closes, now))
    return facts


def fundamental_facts(conn, code: str) -> dict:
    """03 펀더멘탈부가 볼 것. 분기 실적과 같은 업종 견줌."""
    rows = fetch_all(conn, """
        SELECT fiscal_year, fiscal_quarter, revenue, operating_profit,
               net_income, roe, debt_ratio, op_margin,
               current_assets, current_liabilities
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
        # 유동비율 = 1년 안에 돈이 될 자산 ÷ 1년 안에 갚아야 할 빚.
        # 부채비율이 '빚이 많은가' 라면 이건 '당장 버틸 수 있는가' 입니다.
        "유동비율(%)": (round(float(r[8]) / float(r[9]) * 100, 1)
                     if r[8] and r[9] and float(r[9]) > 0 else None),
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
            "^VIX": "공포지수", "CL=F": "국제유가", "GC=F": "금",
            "DX-Y.NYB": "달러지수"}
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

■ 자료에 대하여
- **주어진 자료에만 근거해서** 말합니다. 자료에 없는 사실을 끌어오지
  않습니다. 회사 이름을 안다고 기억에 있는 것을 쓰면 안 됩니다.
- 자료에 없으면 "자료 없음" 이라고 씁니다. 그럴듯하게 메우지 않습니다.
- **확인되지 않은 수치를 임의로 만들지 마세요.** 이것이 가장 중요합니다.
- 숫자는 자료에 있는 값을 그대로 씁니다. 새 숫자를 만들지 않습니다.

■ 사실과 해석을 나눕니다
- **확인된 사실**(자료에 있는 숫자)과 **해석**(그게 무슨 뜻인가)을
  섞지 마세요. 해석할 때는 "…로 보입니다" "…일 수 있습니다" 처럼
  해석임이 드러나게 씁니다.
- 앞일을 맞히려 하지 않습니다. "오를 것" 같은 말을 쓰지 않습니다.
  지금 자료에서 **무엇이 보이는가**만 씁니다.

■ 좋은 쪽과 나쁜 쪽을 같이 봅니다
- 좋아 보이는 것만 적지 마세요. 같은 자료에서 걸리는 점이 있으면
  반드시 함께 적습니다.

■ 쓰는 법
- 짧게 씁니다. 같은 말을 되풀이하지 않습니다.
- 표를 만들지 말고 줄글로 씁니다. 좁은 화면에서 읽습니다."""

부서지침: dict[str, tuple[str, str, str]] = {
    # 이름: (모델, 역할, 시킬 일)
    "기술적분석부": (FAST, "차트와 추세, 거래를 읽는 부서", """
주어진 것은 종가·거래량에서 **계산을 끝낸 사실**입니다. 다시 계산하지
말고 뜻만 읽어주세요.

차례대로, 한 항목에 한두 줄씩:
1. **추세** — 평균선 배열(정배열/역배열/엇갈림)과 20·60·120일 평균
   대비 위치를 묶어서
2. **값대** — 1년 최고·최저 사이 어디인가. 아래위로 오래 머문 값대가
   주어지면 받쳐지거나 막힐 수 있는 자리라는 뜻입니다
3. **거래** — 최근 20일 거래대금이 그 앞 20일보다 늘었는가 줄었는가.
   값은 오르는데 거래가 줄면 꼭 짚으세요
4. **RSI** — 70 위면 많이 오른 뒤, 30 아래면 많이 내린 뒤로 읽습니다.
   다만 센 추세에서는 70 위에 오래 머물 수 있습니다
5. **MACD** — 선이 신호선 위인지, 막대가 늘고 있는지 줄고 있는지
6. **변동성** — 연 변동성이 얼마이고, 그만큼 흔들린다는 게 무슨 뜻인가

★ 반드시 ★
 · 기술적 분석만으로 **앞으로의 값을 단정하지 마세요.**
 · 살 값·팔 값·손절선을 정해주지 마세요. 사람이 정합니다.
 · 지표가 엇갈리면 엇갈린다고 쓰세요. 억지로 한 방향으로 맞추지 마세요.
 · 마지막 줄에 "기술적 지표는 지금까지 이랬다는 것이지 앞으로 이럴
   것이라는 뜻이 아닙니다" 를 적으세요."""),

    "펀더멘탈부": (FAST, "실적과 값어치를 보는 부서", """
차례대로, 한 항목에 한두 줄씩:
1. **매출 성장** — 작년 같은 분기와 견준 값으로. 몇 분기째 늘고
   있는지, 늘어나는 속도가 빨라지는지 느려지는지
2. **이익** — 영업이익과 영업이익률의 방향. 매출은 느는데 이익률이
   떨어지면 값을 깎아 팔고 있다는 뜻일 수 있습니다. 꼭 짚으세요
3. **수익성** — ROE 가 몇 해 사이 올라왔는지 내려왔는지
4. **안전성** — 부채비율과 **유동비율**을 같이. 부채비율은 '빚이
   많은가', 유동비율은 '당장 버틸 수 있는가' 로 서로 다른 것을
   말합니다. 유동비율이 100% 아래면 꼭 짚으세요
5. **값어치** — PER·PBR 을 **같은 업종 가운데값과 견줘서**. 혼자서는
   뜻이 없습니다. 업종 자료가 없으면 "견줄 자료 없음"
6. **배당** — 자료가 있을 때만

★ 반드시 ★
 · 분기 실적은 계절을 탑니다. 앞 분기가 아니라 **작년 같은 분기**와
   견주세요. 자료에 그렇게 계산된 값이 들어 있습니다.
 · 주어지지 않은 지표(ROIC·잉여현금흐름·영업활동현금흐름·재고자산·
   매출채권)는 **없다고 쓰고 넘어가세요.** 다른 숫자로 흉내 내지
   마세요.
 · 사업 부문별 실적·시장 점유율·시장 예상치(컨센서스)는 주어지지
   않습니다. 모릅니다."""),

    "마켓부": (FAST, "시장 국면과 그 회사에 생긴 일을 보는 부서", """
차례대로:
1. **돈값** — 미국 10년 금리의 값과 방향. 금리가 오르면 주식에
   불리하게 작용하는 쪽입니다
2. **불안** — 공포지수(VIX). 20 아래면 잠잠, 30 위면 겁먹은 상태로
   읽습니다. 금이 함께 오르고 있으면 묶어서 보세요
3. **환율과 원자재** — 원달러·달러지수·국제유가. 원달러만 보면 '우리
   돈이 약한 것' 인지 '달러가 센 것' 인지 구별이 안 됩니다. 달러지수를
   같이 보세요. 다만 그 회사가 수출을 하는지 원자재를 쓰는지는
   **업종 이름 말고는 주어진 자료가 없습니다.** "…라면" 으로 쓰세요
4. **오늘 시장** — 오른 종목과 내린 종목 수
5. **그 회사에 생긴 일** — 최근 공시 중 눈에 띄는 것
6. **밖에서 보는 눈** — 증권사 리포트의 의견과 목표주가

★ 반드시 ★
 · 공시는 **제목만** 주어집니다. 제목으로 알 수 없는 속뜻을 지어내지
   마세요. "제목만으로는 규모와 기간을 알 수 없다" 고 쓰면 됩니다.
 · 기준금리·물가(CPI)·고용·GDP·미중갈등 같은 것은 **주어지지
   않습니다.** 아는 척하지 마세요.
 · 시나리오는 '이렇게 되면 이럴 수 있다' 로 쓰고, 어느 쪽이 될지는
   모른다고 밝히세요."""),

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
네 부서의 보고서를 읽고 **두 관점으로 따로** 결론을 냅니다.

★ 왜 따로 내나 ★
  같은 회사가 장기로는 좋고 단기로는 들어갈 자리가 아닐 수 있고,
  그 반대도 됩니다. 하나로 뭉뚱그리면 둘 다 틀립니다.

    장기 — 몇 년 들고 있을 회사인가. 실적이 꾸준한가, 빚이 적은가,
           지금 값이 과하지 않은가. 02 기술적분석부 이야기는 거의
           중요하지 않습니다.
    단기 — 지금 몇 주~몇 달 사이 흐름이 살아 있는가. 거래가 붙었는가.
           03 펀더멘탈부의 '3년 뒤' 이야기는 거의 중요하지 않습니다.

반드시 이 차례로 씁니다.

## 장기
1. **의견** — `관심` / `보류` / `제외` 중 하나만
2. **한 줄 이유**
3. **무너지는 조건** — 무엇이 사실로 드러나면 생각을 바꿔야 하는가.
   나중에 확인할 수 있는 것으로 쓰세요. (예: "다음 분기 매출이 또 줄면")

## 단기
1. **의견** — `관심` / `보류` / `제외` 중 하나만
2. **한 줄 이유**
3. **무너지는 조건** — 위와 같되 짧은 기간에 확인할 수 있는 것으로

## 두 관점이 갈린 이유
장기와 단기 의견이 다르면 **왜 다른지** 한두 줄. 같으면 "같습니다" 라고
쓰고 넘어갑니다.

## 가장 크게 갈린 지점
부서들 의견이 어디서 엇갈렸는가. 리스크관리부의 반대가 타당하면
그렇다고 쓰세요.

## 직접 확인할 것
사람이 원문을 봐야 할 것 한두 가지.

★ '사세요' 라고 쓰지 않습니다. 사는 것은 사람이 정합니다.
★ 이 보고서는 참고 자료이지 권유가 아닙니다. 마지막에 한 줄로 적으세요.
★ 단기 의견은 특히 조심해서 쓰세요. 짧은 기간의 움직임은 앞일을
  알려주지 않습니다. '최근 이랬다' 와 '앞으로 이럴 것' 은 다릅니다."""),
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


def split_verdicts(글: str) -> tuple[str | None, str | None]:
    """
    운용부 보고서에서 장기·단기 의견을 각각 꺼냅니다.

    ★ 머리글을 기준으로 자릅니다 ★
      글 전체에서 '관심' 을 그냥 찾으면, 아래쪽 '두 관점이 갈린 이유'
      문단에 나온 '관심' 까지 집어옵니다. 각 문단 안에서만 찾습니다.
    """
    import re

    def 조각(머리: str) -> str:
        m = re.search(rf"##\s*{머리}\s*(.*?)(?=\n##|\Z)", 글, re.S)
        return m.group(1) if m else ""

    def 의견(조각글: str) -> str | None:
        # '의견' 줄에서 먼저 찾고, 없으면 조각 안 아무 데서나
        m = re.search(r"의견\s*[—\-:*]*\s*\**\s*`?(관심|보류|제외)", 조각글)
        if m:
            return m.group(1)
        m = re.search(r"(관심|보류|제외)", 조각글)
        return m.group(1) if m else None

    return 의견(조각("장기")), 의견(조각("단기"))
