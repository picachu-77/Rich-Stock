# -*- coding: utf-8 -*-
"""
종목을 이름·코드·초성으로 찾아주는 파일.

왜 따로 만들었나요?
  단순히 "이름에 그 글자가 들어있나" 만 보면 쓰기 불편합니다.
    · '삼성' 을 치면 삼성전자보다 이름이 긴 회사가 먼저 나올 수 있고
    · '삼성 전자' 처럼 띄어 쓰면 아무것도 안 나오고
    · 'ㅅㅅㅈㅈ' 같은 초성으로는 아예 찾을 수 없습니다

  그래서 여기서 세 가지를 함께 처리합니다.
    1) 띄어쓰기를 무시하고 찾기      ('삼성 전자' → 삼성전자)
    2) 초성으로 찾기                 ('ㅅㅅㅈㅈ' → 삼성전자)
    3) 가장 그럴듯한 것부터 보여주기 (정확히 일치 → 앞부분 일치 → 포함)
"""

from __future__ import annotations

import pandas as pd

# 한글 초성 19개 (유니코드에 정해진 순서 그대로입니다)
CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"

_HANGUL_START = 0xAC00      # '가'
_HANGUL_END = 0xD7A3        # '힣'


def chosung_of(text: str) -> str:
    """
    글자에서 초성만 뽑아냅니다.

        chosung_of("삼성전자")  →  "ㅅㅅㅈㅈ"
        chosung_of("KODEX 200") →  "KODEX200"   (한글이 아니면 그대로 둡니다)

    한글 한 글자는 '초성 19개 × 중성 21개 × 종성 28개' 순서로 배열되어 있어서,
    '가' 로부터 몇 번째인지를 588(=21×28)로 나누면 초성 번호가 나옵니다.
    """
    out = []
    for ch in str(text):
        code = ord(ch)
        if _HANGUL_START <= code <= _HANGUL_END:
            out.append(CHOSUNG[(code - _HANGUL_START) // 588])
        elif not ch.isspace():
            out.append(ch)
    return "".join(out)


def is_chosung_query(query: str) -> bool:
    """
    검색어가 초성만으로 되어 있는지 확인합니다. ('ㅅㅅㅈㅈ' → True)

    초성만 입력했을 때만 초성 검색을 켭니다. 그러지 않으면 '가나' 처럼
    보통 이름을 쳤을 때도 엉뚱한 종목이 잔뜩 딸려 나옵니다.
    """
    q = str(query).replace(" ", "")
    return bool(q) and all(ch in CHOSUNG for ch in q)


def _norm(text) -> str:
    """비교하기 좋게 다듬습니다. (띄어쓰기 없애고 영문은 대문자로)"""
    return str(text).replace(" ", "").upper() if pd.notna(text) else ""


def search(df: pd.DataFrame, query: str, limit: int = 8) -> pd.DataFrame:
    """
    종목을 찾아 '그럴듯한 순서' 로 돌려줍니다.

    점수 (높을수록 먼저 보여줍니다)
        100  종목코드가 정확히 일치            (005930 → 삼성전자)
         90  종목명이 정확히 일치              (삼성전자 → 삼성전자)
         80  종목명이 검색어로 시작            (삼성 → 삼성전자, 삼성물산)
         70  종목코드가 검색어로 시작
         60  종목명 안에 검색어가 들어 있음    (전자 → 삼성전자, LG전자)
         50  초성이 일치                       (ㅅㅅㅈㅈ → 삼성전자)

    같은 점수끼리는 시가총액이 큰 회사를 먼저 보여줍니다.
    큰 회사일수록 찾는 사람이 많기 때문입니다.
    """
    if df.empty:
        return df.head(0)

    q = _norm(query)
    if not q:
        return df.head(0)

    names = df["종목명"].map(_norm)
    codes = df["종목코드"].map(_norm)

    score = pd.Series(0, index=df.index, dtype="int64")

    # 낮은 점수부터 덮어써서, 마지막에 가장 높은 점수만 남게 합니다.
    if is_chosung_query(query):
        cho = df["종목명"].map(chosung_of)
        score[cho.str.contains(q, regex=False, na=False)] = 50

    score[names.str.contains(q, regex=False, na=False)] = 60
    score[codes.str.startswith(q, na=False)] = 70
    score[names.str.startswith(q, na=False)] = 80
    score[names == q] = 90
    score[codes == q] = 100

    hit = df[score > 0].copy()
    if hit.empty:
        return hit

    hit["_점수"] = score[score > 0]
    # 시가총액이 없는 종목(ETF 등)은 -1 로 두어 뒤로 보냅니다.
    hit["_크기"] = pd.to_numeric(hit.get("시가총액(억)"), errors="coerce").fillna(-1)

    hit = hit.sort_values(["_점수", "_크기"], ascending=[False, False])
    return hit.head(limit).drop(columns=["_점수", "_크기"])
