"""
담을 미국 종목 목록.

★ 왜 손으로 고른 목록인가 ★
  미국 상장 종목은 6천 개가 넘습니다. 전부 담으면 창고(500MB 중 이미
  444MB 사용)가 바로 넘칩니다. 그리고 초보자에게 6천 개는 0개와
  같습니다 — 이름을 아는 회사가 없으면 고를 수가 없습니다.

  그래서 '한국 사람이 이름을 들어봤을 만한 회사' 100개만 담습니다.
  1년치 시세로 약 4MB 입니다.

★ 이름을 한글로 적는 이유 ★
  이 사이트의 검색은 초성(ㅅㅅㅈㅈ → 삼성전자)으로도 찾습니다.
  'AAPL' 만 있으면 '애플' 로 못 찾습니다. 둘 다 넣어두면
  '애플' 로도 'AAPL' 로도 찾힙니다. (종목코드가 곧 티커입니다)

★ 목록을 고치려면 ★
  이 파일만 고치면 됩니다. 다음 수집 때 새 종목이 들어오고,
  뺀 종목은 그대로 남습니다(지우지 않습니다. 과거 시세는 보존).
"""

from __future__ import annotations

# (티커, 한글이름, 거래소, 종류)
#   거래소 : NASDAQ / NYSE   — 수집할 때 야후가 알려주는 값으로 바로잡습니다
#   종류   : STOCK / ETF     — 한국 종목과 같은 구분을 씁니다
US_TICKERS: list[tuple[str, str, str, str]] = [
    # ── 아주 큰 기술 회사 ──
    ("AAPL",  "애플",              "NASDAQ", "STOCK"),
    ("MSFT",  "마이크로소프트",     "NASDAQ", "STOCK"),
    ("NVDA",  "엔비디아",          "NASDAQ", "STOCK"),
    ("AMZN",  "아마존",            "NASDAQ", "STOCK"),
    ("GOOGL", "알파벳(구글)",       "NASDAQ", "STOCK"),
    ("META",  "메타(페이스북)",     "NASDAQ", "STOCK"),
    ("TSLA",  "테슬라",            "NASDAQ", "STOCK"),
    ("AVGO",  "브로드컴",          "NASDAQ", "STOCK"),
    ("ORCL",  "오라클",            "NYSE",   "STOCK"),
    ("NFLX",  "넷플릭스",          "NASDAQ", "STOCK"),
    ("CRM",   "세일즈포스",         "NYSE",   "STOCK"),
    ("ADBE",  "어도비",            "NASDAQ", "STOCK"),
    ("CSCO",  "시스코",            "NASDAQ", "STOCK"),
    ("IBM",   "IBM",              "NYSE",   "STOCK"),
    ("NOW",   "서비스나우",         "NYSE",   "STOCK"),
    ("INTU",  "인튜이트",          "NASDAQ", "STOCK"),
    ("UBER",  "우버",              "NYSE",   "STOCK"),
    ("ABNB",  "에어비앤비",         "NASDAQ", "STOCK"),
    ("SHOP",  "쇼피파이",          "NASDAQ", "STOCK"),
    ("PLTR",  "팔란티어",          "NASDAQ", "STOCK"),
    ("SNOW",  "스노우플레이크",     "NYSE",   "STOCK"),
    ("PANW",  "팔로알토네트웍스",   "NASDAQ", "STOCK"),
    ("CRWD",  "크라우드스트라이크", "NASDAQ", "STOCK"),

    # ── 반도체 ──
    ("AMD",   "AMD",              "NASDAQ", "STOCK"),
    ("TSM",   "TSMC",             "NYSE",   "STOCK"),
    ("ASML",  "ASML",             "NASDAQ", "STOCK"),
    ("QCOM",  "퀄컴",              "NASDAQ", "STOCK"),
    ("TXN",   "텍사스인스트루먼트", "NASDAQ", "STOCK"),
    ("MU",    "마이크론",          "NASDAQ", "STOCK"),
    ("AMAT",  "어플라이드머티어리얼즈", "NASDAQ", "STOCK"),
    ("LRCX",  "램리서치",          "NASDAQ", "STOCK"),
    ("KLAC",  "KLA",              "NASDAQ", "STOCK"),
    ("ADI",   "아나로그디바이스",   "NASDAQ", "STOCK"),
    ("MRVL",  "마벨",              "NASDAQ", "STOCK"),
    ("ARM",   "Arm홀딩스",         "NASDAQ", "STOCK"),
    ("INTC",  "인텔",              "NASDAQ", "STOCK"),

    # ── 금융 ──
    ("BRK-B", "버크셔해서웨이",     "NYSE",   "STOCK"),
    ("JPM",   "JP모건체이스",       "NYSE",   "STOCK"),
    ("V",     "비자",              "NYSE",   "STOCK"),
    ("MA",    "마스터카드",         "NYSE",   "STOCK"),
    ("BAC",   "뱅크오브아메리카",   "NYSE",   "STOCK"),
    ("GS",    "골드만삭스",         "NYSE",   "STOCK"),
    ("MS",    "모건스탠리",         "NYSE",   "STOCK"),
    ("BLK",   "블랙록",            "NYSE",   "STOCK"),
    ("SPGI",  "S&P글로벌",         "NYSE",   "STOCK"),
    ("AXP",   "아메리칸익스프레스", "NYSE",   "STOCK"),
    ("PYPL",  "페이팔",            "NASDAQ", "STOCK"),
    ("COIN",  "코인베이스",         "NASDAQ", "STOCK"),

    # ── 건강·제약 ──
    ("LLY",   "일라이릴리",         "NYSE",   "STOCK"),
    ("UNH",   "유나이티드헬스",     "NYSE",   "STOCK"),
    ("JNJ",   "존슨앤드존슨",       "NYSE",   "STOCK"),
    ("ABBV",  "애브비",            "NYSE",   "STOCK"),
    ("MRK",   "머크",              "NYSE",   "STOCK"),
    ("PFE",   "화이자",            "NYSE",   "STOCK"),
    ("TMO",   "서모피셔",          "NYSE",   "STOCK"),
    ("ABT",   "애보트",            "NYSE",   "STOCK"),
    ("AMGN",  "암젠",              "NASDAQ", "STOCK"),
    ("DHR",   "다나허",            "NYSE",   "STOCK"),
    ("MDT",   "메드트로닉",         "NYSE",   "STOCK"),
    ("NVO",   "노보노디스크",       "NYSE",   "STOCK"),
    ("ISRG",  "인튜이티브서지컬",   "NASDAQ", "STOCK"),

    # ── 소비재 ──
    ("WMT",   "월마트",            "NYSE",   "STOCK"),
    ("COST",  "코스트코",          "NASDAQ", "STOCK"),
    ("HD",    "홈디포",            "NYSE",   "STOCK"),
    ("LOW",   "로우스",            "NYSE",   "STOCK"),
    ("PG",    "프록터앤드갬블",     "NYSE",   "STOCK"),
    ("KO",    "코카콜라",          "NYSE",   "STOCK"),
    ("PEP",   "펩시코",            "NASDAQ", "STOCK"),
    ("MCD",   "맥도날드",          "NYSE",   "STOCK"),
    ("SBUX",  "스타벅스",          "NASDAQ", "STOCK"),
    ("NKE",   "나이키",            "NYSE",   "STOCK"),
    ("TJX",   "TJX",              "NYSE",   "STOCK"),
    ("DIS",   "월트디즈니",         "NYSE",   "STOCK"),
    ("BABA",  "알리바바",          "NYSE",   "STOCK"),
    ("SONY",  "소니",              "NYSE",   "STOCK"),

    # ── 산업·에너지·통신 ──
    ("XOM",   "엑슨모빌",          "NYSE",   "STOCK"),
    ("CVX",   "셰브론",            "NYSE",   "STOCK"),
    ("CAT",   "캐터필러",          "NYSE",   "STOCK"),
    ("DE",    "디어",              "NYSE",   "STOCK"),
    ("BA",    "보잉",              "NYSE",   "STOCK"),
    ("GE",    "GE에어로스페이스",   "NYSE",   "STOCK"),
    ("RTX",   "RTX",              "NYSE",   "STOCK"),
    ("LMT",   "록히드마틴",         "NYSE",   "STOCK"),
    ("HON",   "허니웰",            "NASDAQ", "STOCK"),
    ("UNP",   "유니온퍼시픽",       "NYSE",   "STOCK"),
    ("UPS",   "UPS",              "NYSE",   "STOCK"),
    ("LIN",   "린데",              "NASDAQ", "STOCK"),
    ("ACN",   "액센츄어",          "NYSE",   "STOCK"),
    ("T",     "AT&T",             "NYSE",   "STOCK"),
    ("VZ",    "버라이즌",          "NYSE",   "STOCK"),
    ("CMCSA", "컴캐스트",          "NASDAQ", "STOCK"),
    ("F",     "포드",              "NYSE",   "STOCK"),
    ("GM",    "제너럴모터스",       "NYSE",   "STOCK"),
    ("RIVN",  "리비안",            "NASDAQ", "STOCK"),

    # ── ETF (여러 종목을 담아둔 바구니) ──
    ("SPY",   "SPDR S&P500 ETF",   "NYSE",   "ETF"),
    ("VOO",   "뱅가드 S&P500 ETF", "NYSE",   "ETF"),
    ("QQQ",   "인베스코 나스닥100 ETF", "NASDAQ", "ETF"),
    ("VTI",   "뱅가드 미국전체 ETF", "NYSE",  "ETF"),
    ("SCHD",  "슈왑 배당주 ETF",    "NYSE",   "ETF"),
    ("DIA",   "SPDR 다우존스 ETF",  "NYSE",   "ETF"),
    ("SOXX",  "아이셰어즈 반도체 ETF", "NASDAQ", "ETF"),
    ("TLT",   "아이셰어즈 미국 20년 국채 ETF", "NASDAQ", "ETF"),
]

# 야후가 알려주는 거래소 약호 → 우리가 쓰는 이름
EXCHANGE = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NAS": "NASDAQ",
    "NYQ": "NYSE", "PCX": "NYSE", "ASE": "NYSE", "BTS": "NYSE",
}

# 야후의 업종 이름 → 한글. 한국 종목은 한국표준산업분류(src/ksic.py)를
# 쓰지만 미국 종목에는 그 코드가 없어서, 야후가 주는 11개 분류를 씁니다.
SECTOR_KO = {
    "Technology": "기술",
    "Financial Services": "금융",
    "Healthcare": "건강·제약",
    "Consumer Cyclical": "경기 소비재",
    "Consumer Defensive": "생활 필수품",
    "Communication Services": "통신·미디어",
    "Industrials": "산업재",
    "Energy": "에너지",
    "Utilities": "공공(전기·가스)",
    "Real Estate": "부동산",
    "Basic Materials": "소재",
}


def codes() -> list[str]:
    return [t[0] for t in US_TICKERS]
