"""
주식 용어 사전 화면.

이 화면은 데이터베이스를 전혀 쓰지 않습니다.
용어 내용은 모두 src/glossary_data.py 한 곳에 들어 있고,
이 파일은 그것을 예쁘게 보여주는 역할만 합니다.

용어를 추가하고 싶으면 이 파일이 아니라
src/glossary_data.py 의 TERMS 목록에 한 덩어리만 붙여넣으면 됩니다.
유튜브 링크는 검색어만 적으면 자동으로 만들어집니다.
"""

from __future__ import annotations

from urllib.parse import quote_plus

import streamlit as st

from src.glossary_data import CATEGORY_ORDER, TERMS
from src.ui_korean import apply_korean_ui
from src.ui_style import apply_style

st.set_page_config(
    page_title="주식 용어 사전",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={},
)

# 대시보드와 똑같은 공통 디자인을 적용합니다. → src/ui_style.py
apply_style()

# 이 화면에만 필요한 모양(용어 카드 속 예시 상자, 유튜브 버튼)
st.markdown(
    """
    <style>
      .term-detail { line-height: 1.8; margin: .1rem 0 .9rem 0; font-size: 1rem; }

      /* 숫자 예시 상자 */
      .term-ex {
        background: #f0fdfa;
        border-left: 4px solid #0e9384;
        padding: .7rem .95rem;
        border-radius: 8px;
        margin: 0 0 .9rem 0;
        line-height: 1.7;
      }

      /* 유튜브 링크를 '버튼'처럼 보이게 (손가락으로 누르기 쉽게) */
      .term-yt a {
        display: inline-block;
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #b42318;
        font-weight: 700;
        text-decoration: none;
        padding: .5rem .9rem;
        border-radius: 999px;
        min-height: 40px;
        line-height: 1.6;
      }
      .term-yt a:hover { background: #fee4e2; border-color: #fda29b; }

      /* 분류 제목 */
      .cat-head {
        border-left: 5px solid #2563eb;
        padding-left: .6rem;
        margin: 1.4rem 0 .7rem 0;
        font-size: 1.2rem;
        font-weight: 800;
      }
      .cat-head span { color: #64748b; font-weight: 600; font-size: .9rem; }

      @media (max-width: 640px) {
        .term-detail, .term-ex { font-size: .97rem; }
        .term-yt a { width: 100%; text-align: center; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_korean_ui()

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query="


def youtube_link(query: str) -> str:
    """
    검색어를 유튜브 '검색 결과' 주소로 바꿉니다.
    (특정 영상이 아니라 검색 결과라서, 영상이 사라져도 링크가 깨지지 않습니다)

    quote_plus 는 한글·띄어쓰기를 인터넷 주소에 넣을 수 있는 형태로 바꿔주는 도구입니다.
    """
    return YOUTUBE_SEARCH_URL + quote_plus(query)


def matches(term: dict, words: list[str]) -> bool:
    """검색어(여러 단어 가능)가 용어 어딘가에 들어 있으면 True."""
    haystack = " ".join(
        [term["term"], term["category"], term["short"], term["detail"], term.get("example", "")]
    ).lower()
    return all(w in haystack for w in words)


def render_term(term: dict, opened: bool) -> None:
    """용어 하나를 접었다 펼 수 있는 카드로 그립니다."""
    with st.expander(f"**{term['term']}** — {term['short']}", expanded=opened):
        st.markdown(
            f"<p class='term-detail'>{term['detail']}</p>", unsafe_allow_html=True
        )
        if term.get("example"):
            st.markdown(
                f"<div class='term-ex'>🧮 <b>예시</b> — {term['example']}</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            "<p class='term-yt'>"
            f"<a href='{youtube_link(term['yt'])}' target='_blank' rel='noopener'>"
            f"▶ 유튜브에서 '{term['term']}' 영상 보기</a></p>",
            unsafe_allow_html=True,
        )


# ── 본문 ─────────────────────────────────────────────────────
st.title("📖 주식 용어 사전")

st.info(
    "이 뜻풀이는 투자 판단을 돕기 위한 일반 정보이며, "
    "특정 종목 매수·매도 추천이 아닙니다."
)

st.caption(
    f"모두 {len(TERMS)}개 용어 · 각 용어는 **한 줄 뜻 → 자세한 설명 → 숫자 예시 → "
    "유튜브 영상 찾기** 순서로 되어 있습니다. 용어 제목을 클릭하면 펼쳐집니다."
)

# ── 검색 · 분류 고르기 ────────────────────────────────────────
c1, c2 = st.columns([2, 3])

with c1:
    keyword = st.text_input(
        "🔎 용어 검색",
        placeholder="예: PER, 배당, 손절",
        help="용어 이름뿐 아니라 설명 속 단어로도 찾을 수 있습니다. "
             "여러 단어를 띄어쓰기로 넣으면 모두 포함된 용어만 나옵니다.",
    )

with c2:
    chosen = st.multiselect(
        "📂 분류 고르기 (비워두면 전체)",
        CATEGORY_ORDER,
        default=[],
        help="보고 싶은 분류만 골라서 볼 수 있습니다.",
    )

open_all = st.toggle(
    "모든 용어 펼쳐 보기",
    value=False,
    help="켜면 설명이 한 번에 다 보입니다. 끄면 제목만 보여 훑어보기 좋습니다.",
)

words = [w.lower() for w in keyword.split() if w.strip()]
searching = bool(words)

hits = [t for t in TERMS if (not words or matches(t, words))]
if chosen:
    hits = [t for t in hits if t["category"] in chosen]

st.divider()

if not hits:
    st.warning(
        f"'{keyword}' 와 맞는 용어가 없습니다. 다른 단어로 찾아보세요. "
        "(예: 'PER' 대신 '주가수익')"
    )
    st.stop()

if searching:
    st.success(f"검색 결과 {len(hits)}개 — 아래 항목은 자동으로 펼쳐져 있습니다.")

# ── 분류별로 묶어서 보여주기 ──────────────────────────────────
for category in CATEGORY_ORDER:
    group = [t for t in hits if t["category"] == category]
    if not group:
        continue

    st.markdown(
        f"<div class='cat-head'>{category} <span>· {len(group)}개</span></div>",
        unsafe_allow_html=True,
    )
    for term in group:
        # 검색 중이거나 '모두 펼치기'를 켜면, 설명이 바로 보이게 펼쳐줍니다.
        render_term(term, opened=searching or open_all)
    st.write("")

st.divider()
st.caption(
    "용어를 더 넣고 싶으시면 `src/glossary_data.py` 파일의 TERMS 목록에 "
    "한 덩어리만 추가하면 됩니다. 유튜브 링크는 검색어만 적으면 자동으로 만들어집니다."
)
