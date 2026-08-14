"""
DART(금융감독원 전자공시) 오픈API 접속 담당 파일.

DART 는 상장회사가 의무적으로 제출하는 재무제표를 무료로 제공합니다.
여기서는 그 창구(API)를 두드리는 기본 기능만 담당하고,
지표 계산은 financial_collect.py 에서 합니다.

★ 시세 수집과 완전히 분리되어 있습니다 ★
  이 파일이 통째로 고장 나도 시세 수집과 화면은 정상 동작합니다.

★ 호출 한도 ★
  DART 는 인증키 하나당 하루 20,000건까지만 허용합니다.
  넘기면 그날은 더 못 쓰므로, 18,000건에서 스스로 멈추도록 세어 둡니다.
"""

from __future__ import annotations

import io
import time
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree

import requests

from .config import DART_DAILY_LIMIT, DART_REQUEST_DELAY_SEC, MAX_RETRY, get_dart_api_key

BASE_URL = "https://opendart.fss.or.kr/api"

# 분기 번호 → DART 보고서 코드
#   1 = 1분기보고서, 2 = 반기보고서, 3 = 3분기보고서, 4 = 사업보고서(연간)
REPORT_CODE = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}
REPORT_NAME = {1: "1분기", 2: "반기", 3: "3분기", 4: "사업(연간)"}

# DART 응답 상태 코드
#   000 정상 / 013 조회된 데이터 없음 / 020 요청 한도 초과
#   010 등록되지 않은 키 / 011 사용할 수 없는 키 / 100 필드 부적절
STATUS_OK = "000"
STATUS_NO_DATA = "013"
STATUS_LIMIT = "020"

_FATAL_STATUS = {
    "010": "등록되지 않은 인증키입니다. .env 의 DART_API_KEY 를 확인하세요.",
    "011": "사용할 수 없는 인증키입니다(사용중지 등). DART 사이트에서 확인하세요.",
    "012": "접근할 수 없는 IP 입니다.",
    "020": "오늘의 요청 한도(20,000건)를 초과했습니다. 내일 다시 시도하세요.",
    "021": "조회 가능한 회사 개수가 초과했습니다.",
}


class DartLimitReached(RuntimeError):
    """하루 호출 한도에 도달했을 때 발생시키는 오류."""


@dataclass
class DartClient:
    """
    DART API 를 부르는 도구.

    사용 예:
        dart = DartClient()
        data = dart.get("fnlttMultiAcnt", corp_code="00126380",
                        bsns_year="2025", reprt_code="11011")
    """

    api_key: str = field(default_factory=get_dart_api_key)
    calls: int = 0          # 지금까지 부른 횟수
    limit: int = DART_DAILY_LIMIT

    # ── 내부 도구 ────────────────────────────────────────────
    def _check_limit(self) -> None:
        if self.calls >= self.limit:
            raise DartLimitReached(
                f"안전 한도({self.limit:,}건)에 도달해 중단합니다.\n"
                "DART 하루 한도는 20,000건입니다. 내일 다시 실행하면 "
                "받다 만 지점부터 이어서 받습니다."
            )

    def _sleep(self) -> None:
        time.sleep(DART_REQUEST_DELAY_SEC)

    # ── JSON 요청 ────────────────────────────────────────────
    def get(self, endpoint: str, **params) -> dict:
        """
        DART 에 자료를 요청하고 결과를 돌려줍니다.

        돌려주는 값에는 status 가 들어 있습니다.
          "000" = 정상,  "013" = 해당 자료 없음(정상적인 상황)
        인증키 문제나 한도 초과처럼 계속해도 소용없는 경우에는 오류를 냅니다.
        """
        self._check_limit()

        url = f"{BASE_URL}/{endpoint}.json"
        payload = {"crtfc_key": self.api_key, **params}

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRY + 1):
            try:
                self.calls += 1
                resp = requests.get(url, params=payload, timeout=30)
                self._sleep()

                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")

                data = resp.json()
                status = str(data.get("status", ""))

                if status in _FATAL_STATUS:
                    if status == STATUS_LIMIT:
                        raise DartLimitReached(_FATAL_STATUS[status])
                    raise RuntimeError(f"DART 오류 {status}: {_FATAL_STATUS[status]}")

                return data

            except DartLimitReached:
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == MAX_RETRY:
                    break
                wait = 1.0 * (2 ** (attempt - 1))
                print(f"      ! DART 요청 실패({attempt}/{MAX_RETRY}): {exc}"
                      f" → {wait:.0f}초 후 재시도")
                time.sleep(wait)

        raise RuntimeError(f"DART 요청을 {MAX_RETRY}번 시도했지만 실패했습니다") from last_error

    # ── 회사코드 대응표 내려받기 ──────────────────────────────
    def download_corp_codes(self) -> dict[str, dict]:
        """
        DART 의 전체 회사코드 목록을 한 번에 내려받습니다.

        DART 는 종목코드(005930)가 아니라 자기들만의 8자리 회사코드
        (00126380)로 조회합니다. 그 대응표를 받아오는 기능입니다.

        이 요청은 ZIP 파일 하나로 전체 회사(9만여 곳)를 주기 때문에
        호출 1건으로 끝납니다. 매우 효율적입니다.

        돌려주는 값: { 종목코드6자리: {corp_code, corp_name}, ... }
                     (상장되어 종목코드가 있는 회사만)
        """
        self._check_limit()
        self.calls += 1

        url = f"{BASE_URL}/corpCode.xml"
        resp = requests.get(url, params={"crtfc_key": self.api_key}, timeout=120)
        resp.raise_for_status()

        # 응답이 ZIP 이 아니면 보통 인증키 오류 메시지(XML)입니다.
        if not resp.content[:2] == b"PK":
            text = resp.content[:400].decode("utf-8", errors="replace")
            raise RuntimeError(
                "회사코드 목록을 받지 못했습니다. 인증키를 확인하세요.\n"
                f"    응답 내용: {text}"
            )

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = zf.namelist()[0]
            xml_bytes = zf.read(name)

        root = ElementTree.fromstring(xml_bytes)
        mapping: dict[str, dict] = {}
        for item in root.iter("list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            if not stock_code or len(stock_code) != 6:
                continue  # 비상장 회사는 종목코드가 비어 있습니다
            mapping[stock_code] = {
                "corp_code": (item.findtext("corp_code") or "").strip(),
                "corp_name": (item.findtext("corp_name") or "").strip(),
            }
        return mapping


# ── 숫자 변환 도구 ────────────────────────────────────────────
def to_amount(text) -> int | None:
    """
    DART 가 주는 금액 글자를 숫자로 바꿉니다.

    DART 금액은 "1,234,567" 처럼 쉼표가 들어 있고,
    음수는 "-1,234" 또는 "△1,234" 또는 "(1,234)" 로 올 수 있습니다.
    빈 값이거나 '-' 하나만 있으면 자료 없음으로 봅니다.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s or s in {"-", "－", "N/A"}:
        return None

    negative = False
    if s.startswith("△") or s.startswith("▲"):
        negative, s = True, s[1:]
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s.startswith("-"):
        negative, s = True, s[1:]

    s = s.replace(",", "").replace(" ", "")
    if not s.replace(".", "").isdigit():
        return None

    try:
        value = int(round(float(s)))
    except (TypeError, ValueError):
        return None
    return -value if negative else value
