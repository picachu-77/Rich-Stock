"""
화면 디자인(글자 크기·색·간격·휴대폰 대응)을 한 곳에 모아둔 파일.

왜 필요한가요?
  대시보드와 용어사전이 서로 다른 모습이면 어색하고, 화면을 고칠 때마다
  두 파일을 똑같이 손봐야 합니다. 여기 한 곳만 고치면 모든 화면이 함께 바뀝니다.

어떻게 쓰나요?
  각 화면 파일 맨 위에서 apply_style() 을 한 번 부르면 끝입니다.
  대시보드처럼 사이드바(필터)가 있는 화면은 mobile_sidebar_button() 도 함께 부르면
  휴대폰에서 화면 아래에 '필터' 버튼이 떠서 누르기 쉬워집니다.

휴대폰 대응
  아래 @media (max-width: 640px) 부분이 '화면 가로가 640px보다 좁을 때'
  적용되는 규칙입니다. 컴퓨터 화면에는 영향을 주지 않습니다.

  ▸ 컴퓨터에서만 보일 것은  st.container(key="only_desktop") 안에,
    휴대폰에서만 보일 것은  st.container(key="only_mobile") 안에 넣으면
    아래 규칙이 알아서 하나만 보여줍니다.
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
  /* Streamlit 이 화면 맨 위에 두는 빈 머리띠. 안에 든 버튼을 모두 감췄으므로
     자리만 차지합니다. 높이를 줄여 그만큼 본문을 위로 끌어올립니다. */
  [data-testid="stHeader"] {
    height: 2.6rem !important; min-height: 2.6rem !important;
    background: transparent;
  }

  /* ── 1-2. 눈에 안 보이는 칸이 차지하는 자리 없애기 ─────────── */
  /* 스타일·스크립트를 넣기 위한 칸들은 화면에 아무것도 그리지 않지만,
     Streamlit 이 칸마다 16px 간격을 넣어서 화면 위쪽이 80px 가량 빕니다.
     아예 자리를 없애 그만큼 본문을 끌어올립니다.
     ※ 이 앱은 눈에 보이는 components.html 을 쓰지 않으므로 안전합니다. */
  [data-testid="stElementContainer"]:has(> iframe.stIFrame) { display: none !important; }
  [data-testid="stElementContainer"]:has(style)             { display: none !important; }

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

  [data-testid="stAppViewContainer"] p,
  [data-testid="stAppViewContainer"] li,
  [data-testid="stMarkdownContainer"] { font-size: 1rem; line-height: 1.7; }

  h1 { font-size: 1.9rem !important; font-weight: 800 !important; letter-spacing: -.5px; }
  h2 { font-size: 1.35rem !important; font-weight: 700 !important; margin-top: .4rem !important; }
  h3 { font-size: 1.12rem !important; font-weight: 700 !important; }

  [data-testid="stCaptionContainer"] {
    color: var(--ink-soft) !important;
    font-size: .9rem !important;
    line-height: 1.6 !important;
  }

  /* 첫 화면에서 정작 봐야 할 표·카드가 아래로 밀리지 않도록 위 여백을 줄입니다 */
  .block-container { padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1500px; }

  /* ── 3. 숫자 요약 카드 (metric) ─────────────────────────────── */
  [data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: .7rem .85rem;
    box-shadow: 0 1px 2px rgba(15,23,42,.04);
  }
  [data-testid="stMetricLabel"] p {
    font-size: .88rem !important; color: var(--ink-soft) !important; font-weight: 600 !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.45rem !important; font-weight: 700 !important; line-height: 1.25 !important;
  }

  /* ── 4. 왼쪽 사이드바 ──────────────────────────────────────── */
  [data-testid="stSidebar"] { background: var(--card-soft); }
  [data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
  [data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--line); border-radius: 10px; background: var(--card);
    margin-bottom: .55rem; box-shadow: none;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary {
    font-weight: 700; font-size: .95rem; padding: .55rem .75rem;
  }
  [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover { color: var(--brand); }
  [data-testid="stSidebar"] label p { font-weight: 600 !important; font-size: .9rem !important; }

  /* ── 5. 본문의 접이식 카드 (용어사전 등) ────────────────────── */
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] {
    border: 1px solid var(--line); border-radius: 12px; background: var(--card); margin-bottom: .5rem;
  }
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary {
    padding: .8rem 1rem; font-size: 1rem; line-height: 1.55;
  }
  [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary:hover { color: var(--brand); }

  /* ── 6. 표 ─────────────────────────────────────────────────── */
  [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  /* 표 안 글자를 조금 키웁니다. 숫자가 많은 화면이라 작으면 읽기 힘듭니다 */
  [data-testid="stDataFrame"] [data-testid="stTable"] { font-size: .93rem; }

  /* ── 7. 버튼·입력칸 ────────────────────────────────────────── */
  .stButton button, .stDownloadButton button { min-height: 42px; border-radius: 9px; font-weight: 600; }
  [data-baseweb="input"], [data-baseweb="select"] { border-radius: 9px; }

  /* 가로 라디오(차트 기간 등)를 알약 버튼처럼 */
  [data-testid="stRadio"] [role="radiogroup"] { gap: .35rem; flex-wrap: wrap; }
  [data-testid="stRadio"] label {
    border: 1px solid var(--line); background: var(--card); border-radius: 999px;
    padding: .35rem .85rem; margin: 0 !important;
    transition: background .12s, border-color .12s;
  }
  [data-testid="stRadio"] label:hover { border-color: #94a3b8; background: var(--card-soft); }

  /* ★ 고른 알약을 파랗게 채워 한눈에 보이게 합니다 ★
     기본 상태로는 작은 동그라미 하나만 달라져서, 무엇을 골랐는지 알아보기 어렵습니다. */
  [data-testid="stRadio"] label:has(input:checked) {
    background: #eff6ff; border-color: var(--brand);
  }
  [data-testid="stRadio"] label:has(input:checked) p {
    color: #1d4ed8 !important; font-weight: 700 !important;
  }

  /* 탭(목록 / 차트 / 재무)을 크고 또렷하게 */
  [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 2px solid var(--line); }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    font-weight: 700; font-size: 1rem; padding: .6rem 1rem;
  }
  /* 지금 보고 있는 탭을 진하게 (기본값은 밑줄만 있어 눈에 잘 안 띕니다) */
  [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {
    color: var(--brand) !important;
  }

  /* ── 8. 휴대폰용 종목 카드 (표 대신 보여주는 목록) ──────────── */
  .stock-card {
    border: 1px solid var(--line); border-radius: 12px; background: var(--card);
    padding: .75rem .85rem; margin-bottom: .5rem;
  }
  .stock-card .sc-top { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; }
  .stock-card .sc-name { font-weight: 800; font-size: 1.05rem; }
  .stock-card .sc-code { color: var(--ink-soft); font-size: .8rem; font-weight: 600; }
  .stock-card .sc-price { font-weight: 800; font-size: 1.05rem; white-space: nowrap; }
  .stock-card .sc-chg { font-weight: 700; font-size: .95rem; white-space: nowrap; }
  .stock-card .sc-tags { margin: .35rem 0 .45rem 0; }
  .stock-card .sc-tag {
    display: inline-block; font-size: .72rem; font-weight: 700; color: var(--ink-soft);
    background: var(--card-soft); border: 1px solid var(--line);
    border-radius: 999px; padding: .1rem .5rem; margin-right: .25rem;
  }
  .stock-card .sc-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: .15rem .6rem;
    font-size: .85rem; color: var(--ink-soft); border-top: 1px dashed var(--line); padding-top: .45rem;
  }
  .stock-card .sc-grid b { color: var(--ink); font-weight: 700; }
  .up   { color: var(--up)   !important; }
  .down { color: var(--down) !important; }

  /* ── 8-2. 위험 신호 딱지 ───────────────────────────────────── */
  .risk-badge {
    display: inline-block; font-size: .74rem; font-weight: 800;
    border-radius: 999px; padding: .12rem .5rem; margin: .15rem .25rem 0 0;
    border: 1px solid transparent; white-space: nowrap;
  }
  .risk-badge.danger { color: #b42318; background: #fef3f2; border-color: #fecdca; }
  .risk-badge.warn   { color: #b54708; background: #fffaeb; border-color: #fedf89; }
  .stock-card .sc-risk:empty { display: none; }
  .risk-box { margin: .3rem 0 .6rem 0; }

  /* ── 8-2b. 모의투자 '연습' 화면 ────────────────────────────
     연습 단계 목록 · 습관 점수 막대.
     한 줄에 '무엇을 / 몇 점 / 지금 얼마' 가 같이 보여야 훑어보기 좋습니다. */
  .mission {
    border: 1px solid var(--line); border-radius: 10px;
    padding: .5rem .7rem; margin: .3rem 0; background: #fff;
    font-size: .9rem; line-height: 1.5;
  }
  .mission.done { background: #f6fef9; border-color: #a6f4c5; color: #05603a; }
  .mission-desc { color: var(--ink-soft); font-size: .82rem; }

  .score-box {
    border: 1px solid var(--line); border-radius: 12px;
    padding: .8rem 1rem; margin: .2rem 0 .8rem 0; background: #f8fafc;
  }
  .score-num   { font-size: 2.2rem; font-weight: 900; color: var(--ink); }
  .score-max   { font-size: .9rem; color: var(--ink-soft); margin-left: .3rem; }
  .score-grade {
    margin-left: .6rem; font-size: .78rem; font-weight: 800;
    border-radius: 999px; padding: .18rem .6rem;
    background: #eff8ff; color: #175cd3; border: 1px solid #b2ddff;
  }
  .score-say { margin-top: .35rem; font-size: .88rem; color: var(--ink-soft); }

  .habit { margin: .55rem 0 .1rem 0; font-size: .9rem; }
  .habit-score {
    margin-left: .5rem; font-weight: 800; font-size: .82rem;
    border-radius: 999px; padding: .1rem .5rem;
  }
  .habit-score.good { color: #027a48; background: #ecfdf3; }
  .habit-score.mid  { color: #b54708; background: #fffaeb; }
  .habit-score.bad  { color: #b42318; background: #fef3f2; }
  .habit-val { margin-left: .5rem; color: var(--ink-soft); font-size: .82rem; }
  .habit-bar {
    height: 7px; border-radius: 999px; background: #eef2f6;
    margin-top: .3rem; overflow: hidden;
  }
  .habit-bar i { display: block; height: 100%; border-radius: 999px; }
  .habit-bar i.good { background: #12b76a; }
  .habit-bar i.mid  { background: #f79009; }
  .habit-bar i.bad  { background: #f04438; }

  /* 복기 카드 — 계획대로 했는지 한 줄로 */
  .rv {
    border: 1px solid var(--line); border-left-width: 4px; border-radius: 10px;
    padding: .55rem .75rem; margin: .35rem 0; background: #fff; font-size: .9rem;
  }
  .rv.ok { border-left-color: #12b76a; background: #f6fef9; }
  .rv.no { border-left-color: #f04438; background: #fffbfa; }
  .rv-head { font-weight: 800; }
  .rv-sub  { color: var(--ink-soft); font-size: .82rem; margin-top: .2rem; }

  /* ── 8-3. 52주 위치 막대 ───────────────────────────────────── */
  .w52 { margin: .5rem 0 .1rem 0; }
  .w52-head, .w52-ends {
    display: flex; justify-content: space-between;
    font-size: .78rem; color: var(--ink-soft); font-weight: 600;
  }
  .w52-head { margin-bottom: .2rem; }
  .w52-ends { margin-top: .15rem; }
  .w52-bar {
    position: relative; height: 8px; border-radius: 999px;
    background: linear-gradient(90deg, #dbeafe 0%, #e2e8f0 50%, #fee4e2 100%);
  }
  .w52-dot {
    position: absolute; top: -3px; width: 14px; height: 14px; margin-left: -7px;
    border-radius: 50%; background: #0f172a; border: 2px solid #fff;
    box-shadow: 0 1px 3px rgba(15,23,42,.35);
  }

  /* ── 8-4. 밸류에이션 밴드 (지금 값이 3년 중 어디쯤인지) ────── */
  .vb { margin: .1rem 0 1.1rem 0; }
  .vb-head {
    display: flex; justify-content: space-between; align-items: center;
    gap: .5rem; margin-bottom: .35rem;
  }
  .vb-title { font-size: .98rem; font-weight: 600; color: var(--ink-soft); }
  .vb-title b { font-size: 1.15rem; font-weight: 800; color: var(--ink); }
  .vb-tag {
    font-size: .76rem; font-weight: 800; border-radius: 999px;
    padding: .16rem .6rem; border: 1px solid transparent; white-space: nowrap;
  }
  /* 싼 쪽은 파랑(사기 좋은 구간), 비싼 쪽은 빨강(조심할 구간) */
  .vb-tag.cheap    { color: #1849a9; background: #eff8ff; border-color: #b2ddff; }
  .vb-tag.cheapish { color: #175cd3; background: #f5faff; border-color: #d1e9ff; }
  .vb-tag.mid      { color: #475569; background: #f8fafc; border-color: #e2e8f0; }
  .vb-tag.richish  { color: #b54708; background: #fffaeb; border-color: #fedf89; }
  .vb-tag.rich     { color: #b42318; background: #fef3f2; border-color: #fecdca; }

  .vb-bar {
    position: relative; height: 10px; border-radius: 999px;
    background: linear-gradient(90deg, #dbeafe 0%, #eef2f7 50%, #fee4e2 100%);
  }
  /* 배당수익률은 높은 쪽이 유리하므로 색 방향을 뒤집습니다 */
  .vb-bar.flip {
    background: linear-gradient(90deg, #fee4e2 0%, #eef2f7 50%, #dbeafe 100%);
  }
  .vb-dot {
    position: absolute; top: -4px; width: 18px; height: 18px; margin-left: -9px;
    border-radius: 50%; background: #0f172a; border: 3px solid #fff;
    box-shadow: 0 1px 4px rgba(15,23,42,.4);
  }
  .vb-ticks, .vb-ends {
    display: flex; justify-content: space-between;
    font-size: .74rem; color: var(--ink-soft); font-weight: 600;
  }
  .vb-ticks { margin-top: .3rem; }
  .vb-ends  { margin-top: .1rem; font-size: .72rem; opacity: .8; }

  /* ── 8-5. 종목 비교 표 (2~4개 나란히 보기) ─────────────────── */
  .cmp-wrap { overflow-x: auto; }
  table.cmp {
    border-collapse: collapse; width: 100%; font-size: .9rem;
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  }
  table.cmp th, table.cmp td {
    padding: .5rem .6rem; border-bottom: 1px solid var(--line); text-align: right;
    white-space: nowrap;
  }
  table.cmp th.metric, table.cmp td.metric {
    text-align: left; font-weight: 700; color: var(--ink-soft);
    background: var(--card-soft); position: sticky; left: 0; z-index: 1;
  }
  table.cmp thead th {
    text-align: right; font-weight: 800; color: var(--ink);
    background: var(--card-soft); border-bottom: 2px solid var(--line);
  }
  table.cmp tbody tr:last-child td { border-bottom: 0; }
  /* 그 줄에서 가장 유리한 값에 표시 */
  table.cmp td.best { background: #f0fdf4; font-weight: 800; color: #027a48; }
  table.cmp td.best::after { content: " ★"; font-size: .7rem; color: #12b76a; }

  /* ── 8-6. 키보드로 옮겨 다닐 때 지금 위치 표시 ──────────────── */
  /* 마우스 없이 Tab 키로 조작하는 분을 위해, 지금 선택된 곳을 또렷하게 */
  .stButton button:focus-visible,
  [data-baseweb="input"] input:focus-visible,
  [data-testid="stRadio"] label:has(input:focus-visible),
  [data-testid="stTabs"] [data-baseweb="tab"]:focus-visible {
    outline: 3px solid #93c5fd !important;
    outline-offset: 2px !important;
  }

  /* 움직임을 줄이도록 설정한 기기에서는 전환 효과를 끕니다 */
  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
  }

  /* ── 9. 기기별로 하나만 보여주기 ───────────────────────────── */
  /* 이름이 only_mobile / only_desktop 으로 시작하면 모두 적용됩니다.
     한 화면에서 여러 곳에 쓰려면 이름 뒤에 구분을 붙이세요. (예: only_desktop_cols) */
  [class*="st-key-only_mobile"] { display: none; }   /* 기본(컴퓨터): 휴대폰용 감춤 */

  /* ── 10. 휴대폰(가로 640px 이하)에서만 적용되는 규칙 ────────── */
  @media (max-width: 640px) {
    [class*="st-key-only_mobile"]  { display: block; }   /* 휴대폰: 카드 목록 보이기 */
    [class*="st-key-only_desktop"] { display: none; }    /* 휴대폰: 컴퓨터 전용 감추기 */

    /* 아래 여백은 떠 있는 필터 버튼에 가리지 않을 만큼만 둡니다 */
    .block-container { padding: .6rem .8rem 4.5rem .8rem; }

    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.12rem !important; }

    /* 본문 글자를 살짝 키워 읽기 편하게 (숫자가 많은 화면입니다) */
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] li { font-size: 1.02rem; line-height: 1.65; }

    /* 가로로 늘어선 칸을 2개씩 줄바꿈 (마지막 칸이 혼자 넓어지지 않도록 고정) */
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
      flex: 0 1 calc(50% - .25rem) !important;
      min-width: calc(50% - .25rem) !important;
      width: calc(50% - .25rem) !important;
    }

    [data-testid="stMetric"] { padding: .55rem .65rem; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    [data-testid="stMetricLabel"] p { font-size: .78rem !important; }

    /* 탭을 손가락으로 누르기 쉽게, 좁으면 가로 스크롤 */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
      overflow-x: auto; scrollbar-width: none;
    }
    [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar { display: none; }
    /* 탭 4개가 한 줄에 들어가도록 좌우 여백과 글자를 줄입니다.
       그래도 넘치면 옆으로 밀어서 볼 수 있습니다. */
    [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 0 !important; }
    [data-testid="stTabs"] [data-baseweb="tab"] {
      padding: .5rem .3rem; font-size: .82rem; white-space: nowrap;
    }
    /* 탭 안의 그림문자를 조금 줄여 자리를 아낍니다 */
    [data-testid="stTabs"] [data-baseweb="tab"] p { letter-spacing: -.3px; }

    /* 접이식 카드 제목이 3줄씩 길어지지 않게 2줄로 제한 */
    [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
      display: -webkit-box !important;   /* Streamlit 기본값을 덮어써야 줄 제한이 걸립니다 */
      -webkit-line-clamp: 2; -webkit-box-orient: vertical;
      overflow: hidden; font-size: .95rem; line-height: 1.45;
    }

    /* 알약 버튼(높은 순/낮은 순 등)이 든 칸은 한 줄을 다 쓰게 합니다.
       반 칸만 주면 알약 두 개가 안 들어가 줄이 넘어갑니다. */
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:has([data-testid="stRadioGroup"][data-orientation="horizontal"]) {
      flex: 0 1 100% !important; min-width: 100% !important; width: 100% !important;
    }

    /* 휴대폰에서는 머리띠를 더 줄입니다 */
    [data-testid="stHeader"] { height: 2.2rem !important; min-height: 2.2rem !important; }

    /* 밸류에이션 막대: 눈금 5개는 휴대폰에서 겹치므로 가운데 3개만 남깁니다 */
    .vb-q { display: none; }
    .vb-title b { font-size: 1.05rem; }

    /* 비교표: 종목 이름 칸을 고정하고 나머지는 옆으로 밀어 봅니다 */
    table.cmp { font-size: .82rem; }
    table.cmp th, table.cmp td { padding: .4rem .45rem; }

    /* 입력칸이 작으면 아이폰에서 화면이 확대되므로 16px 이상 유지 */
    input, select, textarea { font-size: 16px !important; }
  }
</style>
"""


def apply_style() -> None:
    """모든 화면 공통 디자인을 적용합니다. 화면 파일 맨 위에서 한 번 부르세요."""
    st.markdown(_CSS, unsafe_allow_html=True)


# 휴대폰에서 화면 아래에 떠 있는 '필터' 버튼.
# 원래 필터를 열려면 화면 왼쪽 위의 작은 '≫' 를 눌러야 하는데 찾기 어렵습니다.
# 이 버튼을 누르면 그 '≫' 를 대신 눌러줍니다.
#
# ★ 왜 '왼쪽' 아래인가요? ★
#   카카오톡·네이버 같은 앱 안에서 링크를 열면, 그 앱이 화면 오른쪽 아래에
#   자기 버튼(공유·목록 등)을 띄웁니다. 그 자리에 두면 우리 버튼이 가려져
#   보이지도 눌리지도 않습니다. 왼쪽 아래는 대개 비어 있어서 그쪽에 둡니다.
#
#   아래 여백을 넉넉히 두는 이유
#     아이폰은 화면 맨 아래에 홈 막대가 있고, 브라우저도 아래에 주소·이동
#     막대를 둡니다. env(safe-area-inset-bottom) 은 그 높이를 기기가
#     알려주는 값입니다. 그만큼 위로 띄워야 버튼이 걸치지 않습니다.
_SIDEBAR_BTN = """
<script>
(function () {
  const doc = window.parent && window.parent.document;
  if (!doc || doc.__mobileFilterBtn) return;
  doc.__mobileFilterBtn = true;

  const btn = doc.createElement('button');
  btn.textContent = '☰ 필터';          /* ☰ 필터 */
  btn.setAttribute('type', 'button');
  /* 화면 한가운데에 두면 본문 글자를 가립니다. 왼쪽 아래 구석으로 보냅니다.
     (오른쪽 아래는 카카오톡·네이버 앱의 버튼이 차지하는 자리입니다)      */
  btn.style.cssText = [
    'position:fixed', 'left:12px',
    'bottom:calc(18px + env(safe-area-inset-bottom, 0px))',
    'z-index:2147483000', 'padding:.62rem 1.1rem', 'border-radius:999px',
    'border:0', 'background:#2563eb', 'color:#fff', 'font-weight:700',
    'font-size:14px', 'box-shadow:0 4px 14px rgba(15,23,42,.35)', 'cursor:pointer',
    'display:none', 'opacity:1',
  ].join(';');

  btn.addEventListener('click', function () {
    // 접혀 있는 사이드바를 여는 진짜 버튼을 찾아 대신 눌러줍니다.
    // 사이드바를 여는 진짜 버튼의 이름표는 Streamlit 판올림마다 바뀝니다.
    // 그래서 그동안 쓰였던 이름을 차례로 찾아봅니다. 하나라도 있으면 됩니다.
    const 이름표 = ['stExpandSidebarButton', 'stSidebarCollapsedControl',
                    'stSidebarCollapseButton', 'collapsedControl'];
    let opener = null;
    for (const t of 이름표) {
      opener = doc.querySelector('[data-testid="' + t + '"] button')
            || doc.querySelector('[data-testid="' + t + '"]');
      if (opener) break;
    }
    if (opener) opener.click();
  });

  doc.body.appendChild(btn);

  // 화면이 좁고(휴대폰) 사이드바가 접혀 있을 때만 버튼을 보여줍니다.
  function refresh() {
    const narrow = doc.defaultView.innerWidth <= 640;
    const sidebarOpen = !!doc.querySelector('[data-testid="stSidebar"][aria-expanded="true"]');
    btn.style.display = (narrow && !sidebarOpen) ? 'block' : 'none';
  }
  refresh();
  doc.defaultView.addEventListener('resize', refresh);
  new MutationObserver(refresh).observe(doc.body, { childList: true, subtree: true,
                                                    attributes: true, attributeFilter: ['aria-expanded'] });
})();
</script>
"""


def mobile_sidebar_button() -> None:
    """휴대폰에서 화면 아래에 '☰ 필터' 버튼을 띄웁니다. (사이드바가 있는 화면에서만 사용)"""
    # 예전에 쓰던 st.components.v1.html 은 2026-06-01 자로 없어질 예정이라
    # 같은 일을 하는 st.iframe 으로 바꿨습니다. → src/ui_korean.py 의 _embed()
    from .ui_korean import _embed

    _embed(_SIDEBAR_BTN)
    st.markdown(
        '<style>[data-testid="stElementContainer"]:has(> iframe) { display: none; }</style>',
        unsafe_allow_html=True,
    )
