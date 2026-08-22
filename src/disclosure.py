# -*- coding: utf-8 -*-
"""
공시로 '회사가 지금 어디로 가고 있는지' 를 읽는 파일.

왜 필요한가요?
  재무제표는 **이미 지나간 일**입니다. 작년에 얼마 벌었는지는 알려주지만,
  이 회사가 앞으로 뭘 하려는지는 말해주지 않습니다.

  회사가 무엇을 하려는지는 **공시**에 먼저 나옵니다.
    "신규 시설투자 결정"  → 공장을 짓는다, 늘리려 한다
    "타법인 주식 취득"    → 다른 회사를 산다
    "단일판매·공급계약"   → 큰 일감을 따냈다
    "유상증자 결정"       → 돈이 필요하다 (내 지분은 묽어진다)
    "자기주식 취득"       → 주가가 싸다고 회사 스스로 판단했다

  이 파일은 공시 제목을 다섯 갈래로 나눠서, 최근 이 회사가 어느 쪽 일을
  많이 했는지 보여줍니다.

한계 (화면에도 적습니다)
  제목만 보고 나누기 때문에 속뜻까지는 알 수 없습니다.
  '유상증자' 도 공장을 짓기 위한 것이면 좋은 신호일 수 있고, 빚을 갚기
  위한 것이면 나쁜 신호입니다. 어느 쪽인지는 공시 원문을 읽어야 합니다.
  그래서 화면에서 DART 원문으로 바로 갈 수 있게 해뒀습니다.
"""

from __future__ import annotations

import warnings

import pandas as pd
import streamlit as st

from src.db import get_conn

warnings.filterwarnings(
    "ignore",
    message="pandas only supports SQLAlchemy connectable",
    category=UserWarning,
)


# ── 공시를 나누는 기준 ────────────────────────────────────────
# 위에 있는 것부터 먼저 맞춰봅니다. (먼저 맞는 것으로 정해집니다)
# 그래서 '조심할 일' 을 맨 위에 두었습니다 — 놓치면 안 되는 것이라서입니다.
CATEGORIES: list[dict] = [
    {
        "key": "위험",
        "이름": "조심할 일",
        "아이콘": "⚠️",
        "색": "danger",
        "뜻": "회사에 문제가 생겼거나 생길 수 있다는 신호입니다. 원문을 꼭 읽어보세요.",
        "말": [
            "횡령", "배임", "소송", "가압류", "부도", "채무불이행",
            "회생절차", "파산", "관리종목", "상장폐지", "거래정지",
            "감사의견", "의견거절", "한정", "자본잠식", "유상감자",
            "불성실공시", "조회공시", "벌금", "과징금", "제재",
        ],
    },
    {
        "key": "투자",
        "이름": "돈을 씁니다",
        "아이콘": "🏭",
        "색": "invest",
        "뜻": "설비를 늘리거나 다른 회사를 사들이는 중입니다. 사업을 키우려는 움직임입니다.",
        "말": [
            "신규시설투자", "시설투자", "타법인주식", "출자증권취득",
            "유형자산", "영업양수", "자산양수", "합병", "분할",
            "지분취득", "출자", "인수",
        ],
    },
    {
        "key": "수주",
        "이름": "일감을 땄습니다",
        "아이콘": "📄",
        "색": "order",
        "뜻": "판매·공급 계약을 맺었습니다. 앞으로 매출로 잡힐 일감입니다.",
        "말": ["단일판매", "공급계약", "수주", "계약체결", "납품"],
    },
    {
        "key": "조달",
        "이름": "돈을 구합니다",
        "아이콘": "💰",
        "색": "raise",
        "뜻": (
            "회사 밖에서 돈을 끌어옵니다. 왜 필요한지가 중요합니다 — "
            "공장을 지으려는 것이면 좋은 신호, 빚을 막으려는 것이면 나쁜 신호입니다. "
            "유상증자·전환사채는 **내 지분이 묽어집니다.**"
        ),
        "말": [
            "유상증자", "전환사채", "신주인수권부사채", "교환사채",
            "사채권발행", "자금조달", "제3자배정", "주주배정", "차입",
        ],
    },
    {
        "key": "주주환원",
        "이름": "주주에게 돌려줍니다",
        "아이콘": "🎁",
        "색": "back",
        "뜻": "배당을 주거나 자기 주식을 사들입니다. 주주 몫을 늘리는 쪽 움직임입니다.",
        "말": [
            "현금·현물배당", "현금배당", "배당결정", "자기주식취득",
            "자기주식소각", "무상증자", "주식분할", "액면분할",
        ],
    },
    {
        "key": "지배구조",
        "이름": "주인이 바뀝니다",
        "아이콘": "👤",
        "색": "owner",
        "뜻": "최대주주나 큰 주주의 지분이 바뀌었습니다. 회사의 방향이 달라질 수 있습니다.",
        "말": ["최대주주", "대량보유", "경영권", "임원ㆍ주요주주", "특정증권등소유"],
    },
    {
        "key": "정기보고",
        "이름": "정기 보고서",
        "아이콘": "📑",
        "색": "plain",
        "뜻": "분기·반기·사업보고서입니다. 정해진 때에 내는 것이라 특별한 신호는 아닙니다.",
        "말": ["사업보고서", "반기보고서", "분기보고서", "감사보고서"],
    },
]

# 어디에도 안 맞는 공시
OTHER = {
    "key": "기타", "이름": "그 밖의 공시", "아이콘": "📌", "색": "plain",
    "뜻": "위 갈래에 들지 않는 공시입니다.",
}

BY_KEY: dict[str, dict] = {c["key"]: c for c in CATEGORIES}
BY_KEY[OTHER["key"]] = OTHER

# DART 원문 주소 (접수번호로 바로 열립니다)
DART_VIEW = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def classify(report_nm: str) -> str:
    """
    공시 제목을 보고 갈래를 정합니다.

        classify("신규시설투자등") → "투자"
        classify("유상증자결정")   → "조달"

    제목에서 띄어쓰기와 괄호를 지운 뒤 맞춰봅니다.
    DART 제목은 "주요사항보고서(유상증자결정)" 처럼 괄호가 붙는 일이 많습니다.
    """
    if not report_nm or pd.isna(report_nm):
        return OTHER["key"]

    text = str(report_nm)
    for ch in " ()[]【】·・":
        text = text.replace(ch, "")

    for cat in CATEGORIES:
        for word in cat["말"]:
            if word.replace("·", "").replace(" ", "") in text:
                return cat["key"]
    return OTHER["key"]


# ── 데이터 읽기 ───────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_disclosures(code: str, months: int = 12) -> pd.DataFrame:
    """한 종목의 최근 공시를 최신순으로 가져옵니다."""
    sql = f"""
        SELECT rcept_no, rcept_dt, report_nm, category
          FROM disclosure
         WHERE code = %(code)s
           AND rcept_dt >= (CURRENT_DATE - INTERVAL '{int(months)} months')
         ORDER BY rcept_dt DESC, rcept_no DESC;
    """
    cols = ["rcept_no", "rcept_dt", "report_nm", "category"]
    try:
        with get_conn() as conn:
            df = pd.read_sql(sql, conn, params={"code": code})
    except Exception:  # noqa: BLE001
        # 공시 표가 아직 없어도 다른 화면은 정상 동작해야 합니다.
        return pd.DataFrame(columns=cols)

    if df.empty:
        return pd.DataFrame(columns=cols)

    df["rcept_dt"] = pd.to_datetime(df["rcept_dt"])
    # 저장할 때 분류해 두지만, 예전 자료를 위해 비어 있으면 지금 계산합니다.
    df["category"] = [
        c if isinstance(c, str) and c else classify(n)
        for c, n in zip(df["category"], df["report_nm"])
    ]
    return df


def has_table() -> bool:
    """공시 표가 만들어져 있는지 확인합니다."""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.disclosure');")
                return cur.fetchone()[0] is not None
    except Exception:  # noqa: BLE001
        return False


# ── 방향 읽기 ─────────────────────────────────────────────────
def counts_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """갈래별로 몇 건인지 셉니다. (많은 순)"""
    if df.empty:
        return pd.DataFrame(columns=["갈래", "건수"])
    c = df["category"].value_counts().reset_index()
    c.columns = ["갈래", "건수"]
    return c


def direction_lines(df: pd.DataFrame, months: int = 12) -> list[str]:
    """
    최근 공시를 보고 '이 회사가 지금 무엇을 하고 있는지' 문장으로 정리합니다.

    정기 보고서는 정해진 때에 내는 것이라 방향과 무관해서 뺍니다.
    """
    if df.empty:
        return []

    meaningful = df[~df["category"].isin(["정기보고", "기타"])]
    if meaningful.empty:
        return []

    lines = []
    for key, n in meaningful["category"].value_counts().items():
        cat = BY_KEY.get(key, OTHER)
        last = meaningful[meaningful["category"] == key].iloc[0]
        lines.append(
            f"{cat['아이콘']} **{cat['이름']}** {int(n):,}건 "
            f"(가장 최근 {last['rcept_dt']:%Y-%m-%d} · {last['report_nm']})"
        )
    return lines


def headline(df: pd.DataFrame, months: int = 12) -> str:
    """
    한 줄 요약. 가장 많았던 갈래를 기준으로 말합니다.

    두 갈래가 겹칠 때가 진짜 중요합니다.
      돈을 구하면서(조달) 동시에 돈을 쓰면(투자) → 키우려고 돈을 당겨오는 중
      돈을 구하기만 하고 쓰지 않으면 → 왜 필요한지 확인이 필요
    """
    if df.empty:
        return ""

    keys = set(df[~df["category"].isin(["정기보고", "기타"])]["category"])
    if not keys:
        return f"최근 {months:,}개월 동안 정기 보고서 말고는 눈에 띄는 공시가 없습니다."

    if "위험" in keys:
        return ("⚠️ **조심할 공시가 있습니다.** 아래 목록에서 먼저 확인하세요. "
                "제목만으로는 알 수 없으니 DART 원문을 꼭 읽어보시길 권합니다.")
    if "투자" in keys and "조달" in keys:
        return ("🏭💰 **돈을 끌어와서 사업을 키우는 중**으로 보입니다. "
                "다만 끌어온 돈이 정말 그 투자에 쓰이는지는 원문에서 확인해야 합니다.")
    if "투자" in keys:
        return "🏭 **사업을 키우는 쪽**으로 움직이고 있습니다."
    if "수주" in keys:
        return "📄 **일감을 따내는 중**입니다. 앞으로 매출로 잡힐 계약이 있습니다."
    if "조달" in keys:
        return ("💰 **돈을 구하는 중**입니다. 무엇에 쓰려는 것인지 원문을 확인하세요. "
                "유상증자·전환사채는 내 지분이 묽어집니다.")
    if "주주환원" in keys:
        return "🎁 **주주 몫을 챙기는 쪽**으로 움직이고 있습니다."
    if "지배구조" in keys:
        return "👤 **주인이 바뀌는 중**입니다. 회사 방향이 달라질 수 있습니다."
    return ""
