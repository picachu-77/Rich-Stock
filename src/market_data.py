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


# ── 데이터 읽기 (10분간 결과를 재사용해서 빠르게) ──────────────
@st.cache_data(ttl=600, show_spinner="데이터를 불러오는 중...")
def load_overview() -> pd.DataFrame:
    """
    전 종목의 최신 시세 + 기간별 수익률을 한 번에 계산해서 가져옵니다.

    수익률 계산 방식:
      (최근 종가 ÷ N개월 전 종가 - 1) × 100
      N개월 전이 휴장일이면, 그 이전 가장 가까운 거래일 종가를 씁니다.
    """
    lateral_sql = "\n".join(
        f"""
        LEFT JOIN LATERAL (
            SELECT p.close
              FROM daily_price p
             WHERE p.code = c.code
               AND p.trade_date <= c.trade_date - INTERVAL '{interval}'
             ORDER BY p.trade_date DESC
             LIMIT 1
        ) AS r{i} ON TRUE"""
        for i, interval in enumerate(PERIODS.values())
    )
    select_returns = ", ".join(f"r{i}.close AS past{i}" for i in range(len(PERIODS)))

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
    SELECT t.code, t.name, t.market, t.kind, t.is_active,
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

    with get_conn() as conn:
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
    df["시가총액(억)"] = (
        pd.to_numeric(df["market_cap"], errors="coerce") / 100_000_000
    ).round(0)
    df["등락률(%)"] = pd.to_numeric(df["change_pct"], errors="coerce").round(2)
    df["종가"] = pd.to_numeric(df["close"], errors="coerce")
    df["거래량"] = pd.to_numeric(df["volume"], errors="coerce")
    df.rename(columns={"code": "종목코드", "name": "종목명"}, inplace=True)

    # ── 투자지표 (거래소 제공) ──
    df["PER"] = pd.to_numeric(df["per"], errors="coerce").round(2)
    df["PBR"] = pd.to_numeric(df["pbr"], errors="coerce").round(2)
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
