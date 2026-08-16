"""
Streamlit 화면의 남은 영어를 한글로 바꿔주는 도구.

왜 필요한가요?
  Streamlit 은 표 머리글 메뉴("Sort ascending", "Hide column" 등)를 자기가 직접
  영어로 그립니다. 이 글자들은 프로그램 내부에 박혀 있어서, 설정으로 한글로
  바꾸는 방법을 공식적으로 제공하지 않습니다.

어떻게 해결하나요?
  화면에 그 메뉴가 뜨는 순간을 감시하다가, 영어 글자를 한글로 바꿔 끼웁니다.
  (원래 기능은 그대로 동작하고 글자만 바뀝니다)

주의
  Streamlit 이 나중에 업데이트되어 글자가 바뀌면, 그 항목만 다시 영어로
  보일 수 있습니다. 그때는 아래 사전에 한 줄 추가하면 됩니다.
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

# 영어 → 한글 사전
TRANSLATIONS: dict[str, str] = {
    # ── 표 머리글(열 제목) 메뉴 ──
    "Sort ascending": "오름차순 정렬",
    "Sort descending": "내림차순 정렬",
    "Statistics": "통계",
    "Format": "표시 형식",
    "Autosize": "너비 자동 맞춤",
    "Pin column": "열 고정",
    "Unpin column": "열 고정 해제",
    "Hide column": "열 숨기기",
    "Show column": "열 보이기",
    "Reset": "초기화",
    # ── 표시 형식 하위 메뉴 ──
    "Automatic": "자동",
    "Localized": "천단위 구분",
    "Plain": "기본",
    "Percent": "백분율",
    "Scientific": "지수",
    "Compact": "간략",
    "Engineering": "공학",
    "Accounting": "회계",
    "Distribution": "분포",
    "Progress": "막대",
    "Number": "숫자",
    "Text": "글자",
    # ── 통계 하위 메뉴 ──
    "Count": "개수",
    "Mean": "평균",
    "Median": "중앙값",
    "Min": "최솟값",
    "Max": "최댓값",
    "Sum": "합계",
    "Std": "표준편차",
    "Empty": "빈 값",
    "Unique": "고유값 수",
    # ── 표 우측 상단 도구 모음 ──
    "Search": "검색",
    "Download as CSV": "CSV 로 내려받기",
    "Download": "내려받기",
    "Fullscreen": "전체화면",
    "Enter fullscreen": "전체화면으로 보기",
    "Exit fullscreen": "전체화면 끝내기",
    "Close": "닫기",
    "Clear": "지우기",
    # ── 왼쪽 페이지 메뉴 ──
    # 첫 화면(app.py)의 메뉴 이름이 파일 이름 그대로 'app' 으로 나오는 것을 바꿉니다.
    "app": "종목 대시보드",
    # ── 기타 공통 ──
    "Press Enter to apply": "Enter 를 누르면 적용됩니다",
    "Deploy": "배포",
    "Rerun": "다시 실행",
    "Settings": "설정",
    "Print": "인쇄",
    "About": "정보",
}


_SCRIPT = """
<script>
(function () {
  const DICT = __DICT__;
  const doc = window.parent && window.parent.document;
  if (!doc) return;                       // 부모 화면에 접근할 수 없으면 조용히 포기
  if (doc.__koreanUiPatched) return;      // 이미 적용했으면 중복 실행 안 함
  doc.__koreanUiPatched = true;

  function translateNode(node) {
    // 1) 글자 자체 바꾸기
    if (node.nodeType === 3) {
      const key = node.nodeValue.trim();
      if (DICT[key]) node.nodeValue = node.nodeValue.replace(key, DICT[key]);
      return;
    }
    if (node.nodeType !== 1) return;

    const walker = doc.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    const texts = [];
    while (walker.nextNode()) texts.push(walker.currentNode);
    for (const t of texts) {
      const key = t.nodeValue.trim();
      if (DICT[key]) t.nodeValue = t.nodeValue.replace(key, DICT[key]);
    }

    // 2) 마우스를 올렸을 때 뜨는 설명(title, aria-label)도 바꾸기
    const targets = node.querySelectorAll ? node.querySelectorAll('[title],[aria-label]') : [];
    for (const el of targets) {
      const ti = el.getAttribute('title');
      if (ti && DICT[ti]) el.setAttribute('title', DICT[ti]);
      const al = el.getAttribute('aria-label');
      if (al && DICT[al]) el.setAttribute('aria-label', DICT[al]);
    }
  }

  translateNode(doc.body);

  // 메뉴는 클릭하는 순간 새로 만들어지므로, 화면 변화를 계속 지켜봅니다.
  new MutationObserver(function (mutations) {
    for (const m of mutations) {
      for (const n of m.addedNodes) translateNode(n);
    }
  }).observe(doc.body, { childList: true, subtree: true });
})();
</script>
"""


def josa(word: str, pair: str) -> str:
    """
    앞말에 맞는 조사를 붙여 돌려줍니다.

    한국어는 앞 글자에 받침이 있느냐에 따라 조사가 달라집니다.
        받침 있음: 삼성전자'와'  ← '자' 는 받침 없음 → '와'
        받침 있음: 한국전력'과'  ← '력' 은 받침 있음 → '과'
    종목명은 회사마다 끝 글자가 달라서, 하나로 고정해 두면 어색한 문장이
    나옵니다. 그래서 글자를 보고 골라 붙입니다.

    쓰는 법
        josa("삼성전자", "과/와")  →  "삼성전자와"
        josa("한국전력", "은/는")  →  "한국전력은"

    pair 는 '받침 있을 때/받침 없을 때' 순서로 적습니다.
    """
    with_batchim, without_batchim = pair.split("/")

    if not word:
        return word + with_batchim

    last = word[-1]
    # 한글 음절인지 확인합니다 (영어·숫자로 끝나면 판단할 수 없습니다).
    if "가" <= last <= "힣":
        has_batchim = (ord(last) - 0xAC00) % 28 != 0
    elif last.isdigit():
        # 숫자는 읽는 소리를 기준으로 합니다 (0·1·3·6·7·8 은 받침이 있습니다)
        has_batchim = last in "013678"
    else:
        # 알 수 없으면 받침이 있는 쪽으로 둡니다 (보통 더 자연스럽습니다).
        has_batchim = True

    return word + (with_batchim if has_batchim else without_batchim)


def apply_korean_ui() -> None:
    """Streamlit 기본 UI 의 영어 글자를 한글로 바꿉니다. app.py 맨 위에서 한 번 호출하세요."""
    components.html(
        _SCRIPT.replace("__DICT__", json.dumps(TRANSLATIONS, ensure_ascii=False)),
        height=0,
        width=0,
    )
    # 위 components.html 이 만드는 빈 칸이 화면에 여백을 남기지 않도록 숨깁니다.
    st.markdown(
        """
        <style>
          .stElementContainer:has(iframe[height="0"]) { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )
