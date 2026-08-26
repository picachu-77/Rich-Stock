"""
설정 담당 파일.

하는 일: 데이터베이스 연결 문자열(비밀 정보)을 안전한 곳에서 읽어옵니다.
        Neon · Supabase 등 어떤 Postgres 든 연결 문자열만 바꾸면 됩니다.
읽는 순서는 아래와 같고, 먼저 찾은 값을 씁니다.

  1) 컴퓨터의 환경변수  (GitHub Actions 가 자동 실행할 때 이 방법을 씁니다)
  2) 프로젝트 폴더의 .env 파일  (내 컴퓨터에서 직접 실행할 때)
  3) Streamlit 의 secrets  (Streamlit Community Cloud 에 올렸을 때)

*** 연결 문자열을 코드 안에 직접 적는 일은 절대 없습니다. ***
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 이 프로젝트의 최상위 폴더 경로 (src 의 한 단계 위)
ROOT_DIR = Path(__file__).resolve().parent.parent

# .env 파일이 있으면 그 안의 값을 읽어 환경변수처럼 사용할 수 있게 합니다.
# override=False → 이미 환경변수가 있으면 그쪽을 우선합니다(GitHub Actions 용).
load_dotenv(ROOT_DIR / ".env", override=False)


_HELP = """
[!] 데이터베이스 연결 문자열(DATABASE_URL)을 찾지 못했습니다.

  내 컴퓨터에서 실행 중이라면:
    1) 프로젝트 폴더에 .env 파일이 있는지 확인하세요.
       없다면 명령창에 아래를 입력해 견본을 복사하세요.
           copy .env.example .env
    2) .env 파일을 메모장으로 열어서
           DATABASE_URL=postgresql://...
       형태로 연결 문자열을 붙여넣고 저장하세요.
       (따옴표 없이, 한 줄로, = 앞뒤 공백 없이)

  GitHub Actions 에서 실행 중이라면:
    저장소 Settings > Secrets and variables > Actions 에
    DATABASE_URL 이라는 이름의 secret 이 등록되어 있는지 확인하세요.
"""


def get_database_url() -> str:
    """데이터베이스 연결 문자열을 돌려줍니다. 없으면 친절한 안내와 함께 멈춥니다."""
    url = (os.getenv("DATABASE_URL") or "").strip()

    # Streamlit Cloud 에서 실행되는 경우 secrets 에서도 찾아봅니다.
    if not url:
        try:
            import streamlit as st  # streamlit 이 없거나 실행중이 아니면 그냥 넘어감

            url = str(st.secrets.get("DATABASE_URL", "")).strip()
        except Exception:
            url = ""

    if not url:
        raise RuntimeError(_HELP)

    # 흔한 실수 자동 교정: 값 양끝에 따옴표를 붙인 경우
    if (url.startswith('"') and url.endswith('"')) or (
        url.startswith("'") and url.endswith("'")
    ):
        url = url[1:-1].strip()

    # 견본(.env.example)의 가짜 값이 그대로 남아 있는 경우
    if "myuser:mypassword" in url or "ep-cool-name-123456" in url:
        raise RuntimeError(
            "[!] .env 의 DATABASE_URL 이 아직 견본(예시) 값 그대로입니다.\n"
            "    데이터베이스 대시보드에서 연결 문자열(Connection string)을 찾아\n"
            "    실제 연결 문자열을 복사해 붙여넣어 주세요."
        )

    if not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError(
            "[!] DATABASE_URL 값이 postgresql:// 로 시작하지 않습니다.\n"
            "    대시보드에서 복사한 문자열 전체를 그대로 붙여넣었는지 확인하세요.\n"
            f"    현재 값의 앞부분: {url[:30]}..."
        )

    return url


# ── 한국거래소(KRX) 로그인 정보 ─────────────────────────────────
# 2025년부터 한국거래소가 시세 조회에 회원 로그인을 요구하도록 정책을
# 변경했습니다. 회원가입은 무료입니다: https://data.krx.co.kr

_KRX_HELP = """
[!] 한국거래소(KRX) 로그인 정보를 찾지 못했습니다.

  한국거래소가 정책을 바꿔서, 이제 시세를 받으려면 무료 회원 로그인이
  필요합니다. 아래 순서로 준비해 주세요.

    1) https://data.krx.co.kr 접속
    2) 우측 상단 [로그인] > [회원가입] 으로 무료 가입 (이메일 인증까지 완료)
    3) 프로젝트 폴더의 .env 파일에 아래 두 줄을 추가
           KRX_ID=가입한아이디
           KRX_PW=가입한비밀번호

  GitHub Actions 에서 실행 중이라면 저장소의
  Settings > Secrets and variables > Actions 에
  KRX_ID, KRX_PW 두 개의 secret 이 등록되어 있어야 합니다.
"""


def get_krx_credentials() -> tuple[str, str]:
    """KRX 아이디/비밀번호를 돌려줍니다. 없으면 친절한 안내와 함께 멈춥니다."""
    krx_id = (os.getenv("KRX_ID") or "").strip().strip("\"'")
    krx_pw = (os.getenv("KRX_PW") or "").strip().strip("\"'")

    if not krx_id or not krx_pw:
        try:
            import streamlit as st

            krx_id = krx_id or str(st.secrets.get("KRX_ID", "")).strip()
            krx_pw = krx_pw or str(st.secrets.get("KRX_PW", "")).strip()
        except Exception:
            pass

    if not krx_id or not krx_pw:
        raise RuntimeError(_KRX_HELP)

    # 견본(.env.example)의 가짜 값이 그대로 남아 있는 경우
    if krx_id == "your_krx_id" or krx_pw == "your_krx_password":
        raise RuntimeError(
            "[!] .env 의 KRX_ID / KRX_PW 가 아직 견본(예시) 값 그대로입니다.\n"
            "    data.krx.co.kr 에 가입한 실제 아이디와 비밀번호로 바꿔주세요."
        )

    # pykrx 는 환경변수를 직접 읽으므로 여기서 확실히 넣어줍니다.
    os.environ["KRX_ID"] = krx_id
    os.environ["KRX_PW"] = krx_pw
    return krx_id, krx_pw


# ── DART(금융감독원 전자공시) 인증키 ────────────────────────────
# 재무지표 수집에만 씁니다. 이 값이 없어도 시세 수집과 화면은 정상 동작합니다.

_DART_HELP = """
[!] DART 오픈API 인증키(DART_API_KEY)를 찾지 못했습니다.

  이 키는 '재무지표'(ROE, 부채비율, 영업이익률 등)를 가져올 때만 필요합니다.
  시세 수집과 화면 보기에는 필요 없습니다.

    1) https://opendart.fss.or.kr 접속
    2) [인증키 신청/관리] > [오픈API 이용동의] 로 무료 신청
    3) 메일로 받은 40자리 키를 .env 파일에 아래처럼 추가
           DART_API_KEY=받은40자리키

  GitHub Actions 에서 실행 중이라면 저장소의
  Settings > Secrets and variables > Actions 에
  DART_API_KEY 라는 이름의 secret 이 등록되어 있어야 합니다.
"""


def get_dart_api_key() -> str:
    """DART 인증키를 돌려줍니다. 없으면 친절한 안내와 함께 멈춥니다."""
    key = (os.getenv("DART_API_KEY") or "").strip().strip("\"'")

    if not key:
        try:
            import streamlit as st

            key = str(st.secrets.get("DART_API_KEY", "")).strip()
        except Exception:
            key = ""

    if not key or key.startswith("여기에"):
        raise RuntimeError(_DART_HELP)

    if len(key) != 40:
        raise RuntimeError(
            f"[!] DART_API_KEY 길이가 40자가 아닙니다 (현재 {len(key)}자).\n"
            "    메일로 받은 인증키 전체를 공백 없이 붙여넣었는지 확인하세요."
        )

    return key


def has_dart_api_key() -> bool:
    """DART 키가 준비되어 있는지만 조용히 확인합니다 (오류를 내지 않음)."""
    try:
        get_dart_api_key()
        return True
    except Exception:
        return False


# ── 수집기 동작 설정 ────────────────────────────────────────────
# 거래소 서버에 부담을 주지 않도록 요청 사이에 쉬는 시간(초)
REQUEST_DELAY_SEC = float(os.getenv("REQUEST_DELAY_SEC", "0.6"))

# 요청이 실패했을 때 다시 시도하는 최대 횟수
MAX_RETRY = int(os.getenv("MAX_RETRY", "4"))

# 데이터베이스에 한 번에 밀어넣는 줄 수 (너무 크면 메모리 부담)
DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "1000"))

# ── DART 호출 제한 ─────────────────────────────────────────────
# DART 는 인증키 하나당 하루 2만 건까지만 호출할 수 있습니다.
# 한도를 넘으면 그날은 더 못 쓰므로, 안전하게 18,000 건에서 스스로 멈춥니다.
DART_DAILY_LIMIT = int(os.getenv("DART_DAILY_LIMIT", "18000"))

# DART 요청 사이에 쉬는 시간(초)
DART_REQUEST_DELAY_SEC = float(os.getenv("DART_REQUEST_DELAY_SEC", "0.25"))
