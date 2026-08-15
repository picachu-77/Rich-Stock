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
import streamlit.components.v1 as components

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

  /* ── 7. 버튼·입력칸 ────────────────────────────────────────── */
  .stButton button, .stDownloadButton button { min-height: 42px; border-radius: 9px; font-weight: 600; }
  [data-baseweb="input"], [data-baseweb="select"] { border-radius: 9px; }

  /* 가로 라디오(차트 기간 등)를 알약 버튼처럼 */
  [data-testid="stRadio"] [role="radiogroup"] { gap: .35rem; flex-wrap: wrap; }
  [data-testid="stRadio"] label {
    border: 1px solid var(--line); background: var(--card); border-radius: 999px;
    padding: .3rem .8rem; margin: 0 !important;
  }

  /* 탭(목록 / 차트 / 재무)을 크고 또렷하게 */
  [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 2px solid var(--line); }
  [data-testid="stTabs"] [data-baseweb="tab"] {
    font-weight: 700; font-size: 1rem; padding: .6rem 1rem;
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

  /* ── 9. 기기별로 하나만 보여주기 ───────────────────────────── */
  .st-key-only_mobile { display: none; }          /* 기본(컴퓨터): 휴대폰용 감춤 */

  /* ── 10. 휴대폰(가로 640px 이하)에서만 적용되는 규칙 ────────── */
  @media (max-width: 640px) {
    .st-key-only_mobile  { display: block; }      /* 휴대폰: 카드 목록 보이기 */
    .st-key-only_desktop { display: none; }       /* 휴대폰: 넓은 표 감추기 */

    .block-container { padding: 1rem .8rem 5rem .8rem; }

    h1 { font-size: 1.45rem !important; }
    h2 { font-size: 1.15rem !important; }

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
    [data-testid="stTabs"] [data-baseweb="tab-list"] { overflow-x: auto; }
    [data-testid="stTabs"] [data-baseweb="tab"] { padding: .55rem .7rem; font-size: .95rem; }

    /* 접이식 카드 제목이 3줄씩 길어지지 않게 2줄로 제한 */
    [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
      display: -webkit-box !important;   /* Streamlit 기본값을 덮어써야 줄 제한이 걸립니다 */
      -webkit-line-clamp: 2; -webkit-box-orient: vertical;
      overflow: hidden; font-size: .95rem; line-height: 1.45;
    }

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
_SIDEBAR_BTN = """
<script>
(function () {
  const doc = window.parent && window.parent.document;
  if (!doc || doc.__mobileFilterBtn) return;
  doc.__mobileFilterBtn = true;

  const btn = doc.createElement('button');
  btn.textContent = '☰ 필터';          /* ☰ 필터 */
  btn.setAttribute('type', 'button');
  btn.style.cssText = [
    'position:fixed', 'left:50%', 'transform:translateX(-50%)', 'bottom:14px',
    'z-index:9990', 'padding:.7rem 1.4rem', 'border-radius:999px',
    'border:0', 'background:#2563eb', 'color:#fff', 'font-weight:700',
    'font-size:15px', 'box-shadow:0 4px 14px rgba(37,99,235,.4)', 'cursor:pointer',
    'display:none',
  ].join(';');

  btn.addEventListener('click', function () {
    // 접혀 있는 사이드바를 여는 진짜 버튼을 찾아 대신 눌러줍니다.
    const opener = doc.querySelector('[data-testid="stSidebarCollapsedControl"] button')
                || doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
                || doc.querySelector('[data-testid="collapsedControl"] button');
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
    components.html(_SIDEBAR_BTN, height=0, width=0)
    st.markdown(
        '<style>.stElementContainer:has(iframe[height="0"]) { display: none; }</style>',
        unsafe_allow_html=True,
    )
