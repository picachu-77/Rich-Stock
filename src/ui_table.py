# -*- coding: utf-8 -*-
"""
표에서 '값 없음' 을 깔끔한 빈칸으로 보여주기 위한 도구.

왜 필요한가요?
  Streamlit 은 값이 없는 숫자 칸에 **'None'** 이라고 영어로 적습니다.
  한글 화면에 영어가 섞여 보기 나쁘고, 초보자는 그게 무슨 뜻인지 모릅니다.
  (ETF 는 PER 이 없고, 재무 자료가 안 들어온 회사는 ROE 가 없습니다)

어떻게 해결하나요?
  숫자를 미리 보기 좋은 '글자' 로 바꿔서 넘깁니다. 값이 없으면 빈 글자로
  두면 칸이 그냥 비어 보입니다.

★ 대신 잃는 것 ★
  글자가 되면 열 제목을 눌렀을 때 **글자순**으로 줄을 섭니다.
  숫자로는 9.5 가 14.85 보다 작지만, 글자로는 '14.85' 가 앞에 옵니다.
  그래서 이 도구를 쓰는 화면은 **화면에 있는 '정렬 기준' 칸으로 정렬**해야
  하며, 열 제목 클릭은 참고용으로만 쓰셔야 합니다.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# 열마다 소수점을 몇 자리까지 보여줄지
DECIMALS: dict[str, int] = {
    "PER": 2, "PBR": 2,
    "배당수익률(%)": 2, "ROE(%)": 2, "영업이익률(%)": 2,
    "수익률(%)": 2, "실현수익률(%)": 2,
    "등락률(%)": 2, "고점대비(%)": 1,
    "부채비율(%)": 0, "52주위치(%)": 0,
}
DEFAULT_DECIMALS = 0


def digits_for(col: str) -> int:
    """
    이 열은 소수점 몇 자리까지 보여줄지 정합니다.

    '수익률 1년(%)' · '평균수익률(%)' 처럼 앞뒤에 말이 붙은 열도 수익률이므로
    2자리로 둡니다.
    (0자리로 두면 -0.4% 가 '-0' 으로 보여 오류처럼 읽힙니다)
    """
    if col in DECIMALS:
        return DECIMALS[col]
    # '평균수익률(%)' · '실현수익률(%)' 처럼 앞에 말이 붙어도 수익률입니다.
    if "수익률" in col:
        return 2
    return DEFAULT_DECIMALS


def fmt(value, digits: int = 0) -> str:
    """숫자 하나를 화면용 글자로. 값이 없으면 빈 글자('')."""
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):,.{digits}f}"


def as_text(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    고른 열을 화면용 글자 표로 바꿉니다.

    숫자 열만 바꾸고, 종목명·시장 같은 글자 열은 그대로 둡니다.
    """
    out = pd.DataFrame(index=df.index)
    for col in columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            digits = digits_for(col)
            out[col] = [fmt(v, digits) for v in s]
        else:
            # 글자 열도 값이 없으면 'None' 이 찍히므로 빈 글자로 바꿉니다.
            out[col] = ["" if pd.isna(v) else str(v) for v in s]
    return out


def text_columns(df: pd.DataFrame, columns: list[str],
                 helps: dict[str, str] | None = None,
                 labels: dict[str, str] | None = None) -> dict:
    """
    st.dataframe 에 넘길 column_config 를 만듭니다.

    숫자였던 열은 오른쪽 정렬로 둡니다. 숫자는 오른쪽으로 맞춰야
    자릿수가 세로로 나란히 서서 크기를 비교하기 쉽습니다.
    """
    helps = helps or {}
    labels = labels or {}
    cfg = {}
    for col in columns:
        right = pd.api.types.is_numeric_dtype(df[col])
        cfg[col] = st.column_config.TextColumn(
            labels.get(col, col),
            help=helps.get(col),
            alignment="right" if right else None,
        )
    return cfg


def color_map(df: pd.DataFrame, columns: list[str],
              up_down_cols: list[str]) -> pd.DataFrame:
    """
    오른 값은 빨강, 내린 값은 파랑으로 칠할 '색 표' 를 만듭니다.
    (국내 증시 관행)

    글자로 바꾼 표에는 숫자가 없으므로, 원래 숫자 표(df)를 보고 색을 정합니다.
    """
    style = pd.DataFrame("", index=df.index, columns=columns)
    for col in up_down_cols:
        if col not in columns or col not in df.columns:
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        style[col] = [
            "" if pd.isna(v) else
            ("color:#d92d20;font-weight:600" if v > 0 else
             ("color:#1570ef;font-weight:600" if v < 0 else ""))
            for v in values
        ]
    return style
