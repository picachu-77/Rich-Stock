# -*- coding: utf-8 -*-
"""
데이터베이스에서 '전 종목 최신 시세 + 지표'를 읽어오는 공용 파일.

왜 따로 있나요?
  대시보드(app.py)와 우량주 찾기(pages) 화면이 똑같은 데이터를 씁니다.
  같은 코드를 두 곳에 두면 한쪽만 고쳐서 어긋나기 쉬우므로 여기 한 곳에 모았습니다.
"""

from __future__ import annotations

import warnings

import pandas as pd
import streamlit as st

from src.db import get_conn
from src.ksic import sector_group, sector_name

# pandas 가 psycopg2 연결을 쓸 때 내는 안내 경고를 숨깁니다.
warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)


PERIODS = {
    "1개월": "1 month",
    "3개월": "3 months",
    "6개월": "6 months",
    "1년": "1 year",
    "3년": "3 years",
}
RETURN_COLS = [f"수익률 {label}(%)" for label in PERIODS]

# ★ '얼마나 옛날 값까지 N개월 전으로 인정할지' ★
#
# 왜 필요한가요?
#   'N개월 전 종가' 를 찾을 때, 딱 그날이 휴장일일 수 있으니 그 이전
#   가장 가까운 거래일을 씁니다. 그런데 제한을 두지 않으면 **몇 년 전**
#   값까지 거슬러 올라가 버립니다.
#
#   실제로 이런 일이 있었습니다. 창고를 새로 만들어 자료가 드문드문할 때,
#   1개월·3개월·6개월·1년 수익률이 모두 똑같이 +270.94% 로 나왔습니다.
#   넷 다 3년 전 종가 하나를 보고 계산했기 때문입니다.
#   '1개월에 270% 올랐다' 는 완전히 틀린 말이고, 그걸 보고 판단하면
#   큰일 납니다.
#
# 14일인 이유
#   설·추석 연휴가 주말과 붙어도 쉬는 날은 일주일을 넘지 않습니다.
#   14일이면 넉넉하고, 그보다 멀면 '자료가 없는 것' 으로 봅니다.
#   자료가 없으면 빈칸으로 둡니다. 틀린 숫자보다 빈칸이 낫습니다.
NEAR_DAYS = 14


# ── 데이터 읽기 (10분간 결과를 재사용해서 빠르게) ──────────────
@st.cache_data(ttl=600, show_spinner="데이터를 불러오는 중...")
def load_overview() -> pd.DataFrame:
    """
    전 종목의 최신 시세 + 기간별 수익률을 한 번에 계산해서 가져옵니다.

    수익률 계산 방식:
      (최근 종가 ÷ N개월 전 종가 - 1) × 100
      N개월 전이 휴장일이면, 그 이전 가장 가까운 거래일 종가를 씁니다.
      다만 NEAR_DAYS(14일)보다 더 멀리까지 거슬러 올라가지는 않습니다.
      그만큼 자료가 비어 있으면 수익률을 빈칸으로 둡니다. → NEAR_DAYS 설명
    """
    lateral_sql = "\n".join(
        f"""
        LEFT JOIN LATERAL (
            SELECT p.close
              FROM daily_price p
             WHERE p.code = c.code
               AND p.trade_date <= c.trade_date - INTERVAL '{interval}'
               AND p.trade_date >= c.trade_date - INTERVAL '{interval}'
                                                 - INTERVAL '{NEAR_DAYS} days'
             ORDER BY p.trade_date DESC
             LIMIT 1
        ) AS r{i} ON TRUE"""
        for i, interval in enumerate(PERIODS.values())
    )
    select_returns = ", ".join(f"r{i}.close AS past{i}" for i in range(len(PERIODS)))

    # ★ 있는 칸만 골라서 조회합니다 ★
    #   업종·대표이사 같은 칸은 나중에 추가된 것이라, 아직 표를 갱신하지 않은
    #   데이터베이스에는 없을 수 있습니다. 없는 칸을 조회하면 화면 전체가
    #   오류로 멈추므로, 먼저 어떤 칸이 있는지 물어보고 있는 것만 가져옵니다.
    with get_conn() as conn:
        existing = set(
            pd.read_sql(
                """
                SELECT column_name FROM information_schema.columns
                 WHERE table_name = 'ticker';
                """,
                conn,
            )["column_name"]
        )
        profile_cols = [
            c for c in ("sector_code", "sector_name", "ceo_name", "est_date", "homepage")
            if c in existing
        ]
        profile_sql = "".join(f"\n           t.{c}," for c in profile_cols)

        sql = f"""
    WITH bound AS (
        SELECT max(trade_date) AS last_d FROM daily_price
    ),
    recent AS (
        SELECT p.*
          FROM daily_price p, bound b
         WHERE p.trade_date >= b.last_d - INTERVAL '30 days'
    ),
    cur AS (
        SELECT DISTINCT ON (code)
               code, trade_date, close, change_pct, volume, market_cap,
               per, pbr, eps, bps, div_yield
          FROM recent
         ORDER BY code, trade_date DESC
    )
    SELECT t.code, t.name, t.market, t.kind, t.is_active,{profile_sql}
           c.trade_date, c.close, c.change_pct, c.volume, c.market_cap,
           c.per, c.pbr, c.eps, c.bps, c.div_yield,
           f.roe, f.debt_ratio, f.op_margin, f.payout_ratio,
           f.fiscal_year, f.fiscal_quarter,
           {select_returns}
      FROM cur c
      JOIN ticker t ON t.code = c.code
      -- 재무지표는 '있으면 붙이고 없으면 빈칸'(LEFT JOIN)으로 가져옵니다.
      -- 그래야 재무제표가 없는 ETF 도 목록에서 사라지지 않습니다.
      -- 종목별로 가장 최근 분기 한 줄만 가져옵니다.
      LEFT JOIN LATERAL (
          SELECT fi.roe, fi.debt_ratio, fi.op_margin, fi.payout_ratio,
                 fi.fiscal_year, fi.fiscal_quarter
            FROM financial fi
           WHERE fi.code = c.code
           ORDER BY fi.fiscal_year DESC, fi.fiscal_quarter DESC
           LIMIT 1
      ) AS f ON TRUE
      {lateral_sql}
     WHERE t.is_active = TRUE;
    """
        df = pd.read_sql(sql, conn)

    if df.empty:
        return df

    # 수익률 계산
    for i, label in enumerate(PERIODS):
        past = pd.to_numeric(df[f"past{i}"], errors="coerce")
        cur = pd.to_numeric(df["close"], errors="coerce")
        df[f"수익률 {label}(%)"] = ((cur / past - 1) * 100).round(2)
        df.drop(columns=[f"past{i}"], inplace=True)

    df["종류"] = df["kind"].map({"STOCK": "주식", "ETF": "ETF"}).fillna(df["kind"])
    df["시장"] = df["market"]

    # ── 회사 기본정보 (src/company_profile.py 가 채워 넣습니다) ──
    # 아직 한 번도 수집하지 않았다면 빈칸이며, 화면은 '정보 없음'으로 표시합니다.
    #
    # 업종 이름은 저장된 '업종코드'로부터 화면에서 만듭니다.
    # 이렇게 해두면 나중에 업종을 더 잘게 나누고 싶을 때 src/ksic.py 만 고치면 되고,
    # DART 에서 다시 받아올 필요가 없습니다.
    if "sector_code" in df:
        df["업종"] = df["sector_code"].map(sector_name)
        df["업종(큰묶음)"] = df["sector_code"].map(sector_group)
        # 코드가 없고 예전에 저장된 이름만 있는 경우를 위한 대비책
        if "sector_name" in df:
            fallback = df["sector_name"].fillna("업종 미상")
            df["업종"] = df["업종"].where(df["업종"] != "업종 미상", fallback)
    else:
        df["업종"] = "업종 미상"
        df["업종(큰묶음)"] = "업종 미상"
    df["대표이사"] = df["ceo_name"] if "ceo_name" in df else None
    df["홈페이지"] = df["homepage"] if "homepage" in df else None
    if "est_date" in df:
        est = pd.to_datetime(df["est_date"], errors="coerce")
        # 업력 = 설립일로부터 지난 햇수 (오래된 회사일수록 부침을 견뎌왔다는 뜻)
        df["업력(년)"] = ((pd.Timestamp.today() - est).dt.days / 365.25).round(0).astype("Float64")
    else:
        df["업력(년)"] = pd.NA
    df["시가총액(억)"] = (
        pd.to_numeric(df["market_cap"], errors="coerce") / 100_000_000
    ).round(0)
    df["등락률(%)"] = pd.to_numeric(df["change_pct"], errors="coerce").round(2)
    df["종가"] = pd.to_numeric(df["close"], errors="coerce")
    df["거래량"] = pd.to_numeric(df["volume"], errors="coerce")
    df.rename(columns={"code": "종목코드", "name": "종목명"}, inplace=True)

    # ── 투자지표 (거래소 제공) ──
    # ★ PER·PBR 이 0 이면 '값 없음' 입니다 ★
    #   거래소는 ETF 처럼 지표가 없는 종목이나 적자 기업의 PER 을 0 으로
    #   내려보냅니다. 0 을 그대로 두면 목록에서 'PER 낮은 순' 으로 줄 세울 때
    #   맨 앞에 나와서, 가장 싼 종목처럼 보이는 착각을 일으킵니다.
    #   주식의 PER·PBR 이 정확히 0 인 경우는 없으므로 빈칸으로 바꿉니다.
    per = pd.to_numeric(df["per"], errors="coerce").round(2)
    pbr = pd.to_numeric(df["pbr"], errors="coerce").round(2)
    df["PER"] = per.where(per > 0)
    df["PBR"] = pbr.where(pbr > 0)
    df["EPS(원)"] = pd.to_numeric(df["eps"], errors="coerce")
    df["BPS(원)"] = pd.to_numeric(df["bps"], errors="coerce")
    df["배당수익률(%)"] = pd.to_numeric(df["div_yield"], errors="coerce").round(2)

    # ── 재무지표 (DART 제공) ──
    df["ROE(%)"] = pd.to_numeric(df["roe"], errors="coerce").round(2)
    df["부채비율(%)"] = pd.to_numeric(df["debt_ratio"], errors="coerce").round(2)
    df["영업이익률(%)"] = pd.to_numeric(df["op_margin"], errors="coerce").round(2)
    df["배당성향(%)"] = pd.to_numeric(df["payout_ratio"], errors="coerce").round(2)

    # 재무지표가 어느 시점 것인지 함께 표시합니다 (예: 2025년 사업(연간))
    q_name = {1: "1분기", 2: "반기", 3: "3분기", 4: "연간"}
    df["재무 기준"] = [
        f"{int(y)}년 {q_name.get(int(q), q)}" if pd.notna(y) and pd.notna(q) else None
        for y, q in zip(df["fiscal_year"], df["fiscal_quarter"])
    ]

    # ★ 빈 값이 화면에 'None' 이라는 글자로 찍히지 않게 하는 처리 ★
    # 파이썬의 '숫자 아님(NaN)' 을 그대로 두면 Streamlit 이 None 이라고 적습니다.
    # 아래처럼 '값 없음을 표현할 수 있는 숫자형'으로 바꾸면 깔끔한 빈칸이 됩니다.
    for col in ["종가", "거래량", "시가총액(억)", "EPS(원)", "BPS(원)"]:
        df[col] = df[col].astype("Float64").round(0).astype("Int64")
    for col in (
        ["등락률(%)", "PER", "PBR", "배당수익률(%)",
         "ROE(%)", "부채비율(%)", "영업이익률(%)", "배당성향(%)"]
        + RETURN_COLS
    ):
        df[col] = df[col].astype("Float64")

    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_track_record(quarters: int = 8) -> pd.DataFrame:
    """
    회사의 '실적 꾸준함'을 종목별로 한 번에 계산해서 가져옵니다.

    왜 필요한가요?
      "경영을 잘하는 회사인가"를 사람 이름으로 판단할 수는 없습니다.
      대신 지나온 실적이 그 답을 어느 정도 보여줍니다.
      한 해만 반짝 잘한 회사보다, 여러 해 꾸준히 흑자를 내고 매출을 늘려온
      회사가 더 믿을 만하다고 보는 것입니다.

    계산하는 것 (최근 quarters 개 보고서 기준)
      흑자분기수   : 순이익이 0보다 컸던 보고서 수
      보고서수     : 비교에 쓴 보고서 수
      흑자비율(%)  : 흑자분기수 ÷ 보고서수 × 100
      매출성장(%)  : 가장 오래된 보고서 대비 가장 최근 보고서의 매출 증가율
      배당지속(회) : 배당성향이 0보다 컸던 보고서 수
    """
    sql = f"""
    WITH recent AS (
        SELECT f.*,
               row_number() OVER (
                   PARTITION BY f.code
                   ORDER BY f.fiscal_year DESC, f.fiscal_quarter DESC
               ) AS rn
          FROM financial f
    ),
    picked AS (
        SELECT * FROM recent WHERE rn <= {int(quarters)}
    )
    SELECT code,
           count(*)                                       AS "보고서수",
           count(*) FILTER (WHERE net_income > 0)         AS "흑자분기수",
           count(*) FILTER (WHERE payout_ratio > 0)       AS "배당지속",
           -- rn 이 작을수록 최근입니다. 매출이 있는 것만 모아 맨 앞/맨 뒤를 씁니다.
           (array_agg(revenue ORDER BY rn ASC)
                FILTER (WHERE revenue IS NOT NULL))[1]    AS "최근매출",
           (array_agg(revenue ORDER BY rn DESC)
                FILTER (WHERE revenue IS NOT NULL))[1]    AS "과거매출",
           -- 위험 신호 판단에 쓰는 값들 (가장 최근 보고서 기준)
           (array_agg(total_equity ORDER BY rn ASC)
                FILTER (WHERE total_equity IS NOT NULL))[1] AS "최근자본",
           (array_agg(net_income ORDER BY rn ASC)
                FILTER (WHERE net_income IS NOT NULL))[1]   AS "최근순이익"
      FROM picked
     GROUP BY code;
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn)
    except Exception:  # noqa: BLE001
        # 재무 이력이 없어도 나머지 화면은 정상 동작해야 합니다.
        return pd.DataFrame(
            columns=["종목코드", "보고서수", "흑자분기수", "흑자비율(%)",
                     "매출성장(%)", "배당지속", "최근자본", "최근순이익"]
        )

    if df.empty:
        return df

    df["흑자비율(%)"] = (
        pd.to_numeric(df["흑자분기수"], errors="coerce")
        / pd.to_numeric(df["보고서수"], errors="coerce") * 100
    ).round(1)

    past = pd.to_numeric(df["과거매출"], errors="coerce")
    now = pd.to_numeric(df["최근매출"], errors="coerce")
    # 과거 매출이 0이거나 없으면 성장률을 계산할 수 없습니다.
    df["매출성장(%)"] = ((now / past.where(past > 0) - 1) * 100).round(1)

    df.rename(columns={"code": "종목코드"}, inplace=True)
    for col in ["흑자비율(%)", "매출성장(%)"]:
        df[col] = df[col].astype("Float64")
    return df[["종목코드", "보고서수", "흑자분기수", "흑자비율(%)",
               "매출성장(%)", "배당지속", "최근자본", "최근순이익"]]


@st.cache_data(ttl=600, show_spinner=False)
def load_52w() -> pd.DataFrame:
    """
    종목별 '최근 1년(52주) 최고가·최저가'를 한 번에 가져옵니다.

    왜 필요한가요?
      지금 주가가 1년 범위의 어디쯤인지 알아야 '많이 떨어졌으니 싸다'는
      착각을 피할 수 있습니다. 고점 대비 얼마나 내려왔는지, 바닥 근처인지
      꼭대기 근처인지를 한눈에 보기 위한 값입니다.
    """
    sql = """
    WITH bound AS (
        SELECT max(trade_date) AS last_d FROM daily_price
    )
    SELECT p.code,
           max(p.close) AS "52주최고",
           min(p.close) AS "52주최저"
      FROM daily_price p, bound b
     WHERE p.trade_date >= b.last_d - INTERVAL '1 year'
       AND p.close IS NOT NULL
     GROUP BY p.code;
    """
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["종목코드", "52주최고", "52주최저"])

    if df.empty:
        return df
    df.rename(columns={"code": "종목코드"}, inplace=True)
    for c in ["52주최고", "52주최저"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Float64")
    return df
