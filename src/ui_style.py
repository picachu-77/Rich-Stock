"""
화면 디자인(글자 크기·색·간격·모바일 대응)을 한 곳에 모아둔 파일.

왜 필요한가요?
  대시보드와 용어사전이 서로 다른 모습이면 어색하고, 화면을 고칠 때마다
  두 파일을 똑같이 손봐야 합니다. 여기 한 곳만 고치면 모든 화면이 함께 바뀝니다.

어떻게 쓰나요?
  각 화면 파일 맨 위에서 apply_style() 을 한 번 부르면 끝입니다.

휴대폰 대응
  아래 @media (max-width: 640px) 부분이 '화면 가로가 640px보다 좁을 때'
  적용되는 규칙입니다. 휴대폰에서는 글자를 조금 키우고, 가로로 늘어선 칸들을
  2개씩 줄바꿈해서 찌그러지지 않게 합니다.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
  /* ── 1. Streamlit 이 자동으로 붙이는 영어 요소 감추기 ───────── */
  [data-testid="stToolbar"]      { visibility: hidden; height: 0; position: fixed; }
  [data-testid="stDecoration"]   { display: none; }
  [data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
  #MainMenu                      { visibility: hidden; height: 0; }
  footer                         { visibility: hidden; height: 0; }
  .stDeployButton                { display: none; }

  /* ── 2. 기본 색과 글자 ─────────────────────────────────────── */
  :root {
    --ink:        #0f172a;   /* 본문 글자색 (짙은 남색) */
    --ink-soft:   #475569;   /* 설명 글자색 (회색) */
    --line:       #e2e8f0;   /* 옅은 선 */
    --card:       #ffffff;   /* 카드 배경 */
    --card-soft:  #f8fafc;   /* 옅은 배경 */
    --brand:      #2563eb;   /* 강조색 (파랑) */
    --up:         #d92d20;   /* 상승 (빨강) */
    --down:       #1570ef;   /* 하락 (파랑) */
  }

  html, body, [data-testid="stAppViewContainer"] {
    color: var(--ink);
    -webkit-text-size-adjust: 100%;   /* 휴대폰이 멋대로 글자를 키우지 않게 */
  }

  /* 본문 글자를 조금 키우고 줄간격을 넓혀 읽기 편하게 합니다. */
  [data-testid="stAppViewContainer"] p,
  [data-testid="stAppViewContainer"] li,
  [data-testid="stMarkdownContainer"] {
    font-size: 1rem;
    line-height: 1.7;
  }

  /* 제목 */
  h1 { font-size: 1.9rem !important; font-weight: 800 !important; letter-spacing: -.5px; }
  h2 { font-size: 1.35rem !important; font-weight: 700 !important; margin-top: .4rem !important; }
  h3 { font-size: 1.12rem !important; font-weight: 700 !important; }

  /* 안내 문구(캡션)는 작지만 흐리지 않게 — 흐린 회색은 읽기 어렵습니다 */
  [data-testid="stCaptionContainer"] {
    color: var(--ink-soft) !important;
    font-size: .9rem !important;
    line-height: 1.6 !important;
  }

  /* 본문 좌우 여백 (넓은 화면에서 너무 붙지 않게) */
  .block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

  /* ── 3. 숫자 요약 카드 (metric) ─────────────────────────────── */
  [data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: .85rem 1rem;
    box-shadow: 0 1px 2px rgba(15,23,42,.04);
  }
  [data-testid="stMetricLabel"] p {
    font-size: .88rem !important;
    color: var(--ink-soft) !important;
    font-weight: 600 !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    line-height: 1.25 !important;
  }

  /* ── 4. 왼쪽 사이드바 ──────────────────────────────────────── */
  [data-testid="stSidebar"] { background: var(--card-soft); }
  [data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

  /* 접었다 펴는 필터 묶음을 '카드'처럼 보이게 */
  [data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--card);
    margin-bottom: .55rem;
    box-shadow: none;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-weight: 700;
    font-size: .95rem;
    padding: .55rem .75rem;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { color: var(--brand); }

  /* 입력칸 라벨을 또렷하게 */
  [data-testid="stSidebar"] label p { font-weight: 600 !important; font-size: .9rem !important; }

  /* ── 5. 본문의 접이식 카드 (용어사전 등) ────────────────────── */
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] {
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--card);
    margin-bottom: .5rem;
  }
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary {
    padding: .8rem 1rem;
    font-size: 1rem;
    line-height: 1.55;
  }
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary:hover { color: var(--brand); }

  /* ── 6. 표 ─────────────────────────────────────────────────── */
  [data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
  }

  /* ── 7. 버튼·입력칸: 손가락으로 누르기 쉬운 크기 ────────────── */
  .stButton button, .stDownloadButton button {
    min-height: 42px;
    border-radius: 9px;
    font-weight: 600;
  }
  [data-baseweb="input"], [data-baseweb="select"] { border-radius: 9px; }

  /* 가로 라디오(차트 기간 등)를 버튼처럼 보이게 */
  [data-testid="stRadio"] [role="radiogroup"] { gap: .35rem; flex-wrap: wrap; }
  [data-testid="stRadio"] label {
    border: 1px solid var(--line);
    background: var(--card);
    border-radius: 999px;
    padding: .3rem .8rem;
    margin: 0 !important;
  }

  /* ── 8. 휴대폰(가로 640px 이하)에서만 적용되는 규칙 ─────────── */
  @media (max-width: 640px) {
    .block-container { padding: 1.1rem .8rem 2.5rem .8rem; }

    h1 { font-size: 1.45rem !important; }
    h2 { font-size: 1.15rem !important; }

    /* 가로로 늘어선 칸을 2개씩 줄바꿈 (찌그러짐 방지)
       Streamlit 버전에 따라 칸의 이름표가 stColumn / column 두 가지라 둘 다 적어둡니다. */
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
      flex: 1 1 46% !important;
      min-width: 46% !important;
      width: 46% !important;
    }

    [data-testid="stMetric"] { padding: .6rem .7rem; }
    [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
    [data-testid="stMetricLabel"] p { font-size: .8rem !important; }

    /* 입력칸이 작으면 아이폰에서 화면이 확대되므로 16px 이상 유지 */
    input, select, textarea { font-size: 16px !important; }
  }
</style>
"""


def apply_style() -> None:
    """모든 화면 공통 디자인을 적용합니다. 화면 파일 맨 위에서 한 번 부르세요."""
    st.markdown(_CSS, unsafe_allow_html=True)
