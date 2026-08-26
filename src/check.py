"""
설정 점검 도구.  ★ 문제가 생기면 가장 먼저 이걸 실행해 보세요 ★

실행 방법:
    .venv\\Scripts\\python.exe -m src.check

확인하는 것 5가지
  1) .env 파일이 있고 값이 채워져 있는가
  2) 데이터베이스에 접속이 되는가
  3) 표(테이블)가 만들어져 있는가
  4) 한국거래소 로그인이 되는가       ← 시세용
  5) DART 인증키가 동작하는가          ← 재무지표용 (선택)

4) 와 5) 는 서로 독립적입니다.
DART 가 없어도 시세 수집과 화면은 정상 동작합니다.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK = "  [ 정상 ]"
NG = "  [ 문제 ]"


def _mask(value: str) -> str:
    """비밀번호가 화면에 그대로 찍히지 않도록 전부 가립니다."""
    if not value:
        return "(비어 있음)"
    return f"{'*' * len(value)} ({len(value)}자)"


def check_env_file() -> bool:
    print("\n[1/5] .env 파일 확인")
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"{NG} .env 파일이 없습니다: {env_path}")
        print("       해결: 명령창에 아래를 입력하세요")
        print("             copy .env.example .env")
        print("       그 다음 메모장으로 .env 를 열어 값을 채우세요.")
        return False
    print(f"{OK} .env 파일이 있습니다.")
    return True


def check_database() -> bool:
    print("\n[2/5] 데이터베이스 접속 확인")
    try:
        from .config import get_database_url

        url = get_database_url()
        # 비밀번호 부분을 가려서 보여줍니다
        shown = url
        if "@" in url and "://" in url:
            head, tail = url.split("://", 1)
            creds, host = tail.split("@", 1)
            user = creds.split(":", 1)[0]
            shown = f"{head}://{user}:****@{host}"
        print(f"       연결 대상: {shown[:100]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} {exc}")
        return False

    try:
        from .db import test_connection

        version = test_connection()
        print(f"{OK} 접속 성공. {version.split(',')[0]}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} 접속 실패: {exc}")
        print("       확인할 점:")
        print("         - 데이터베이스 대시보드에서 연결 문자열을 다시 복사했는지")
        print("         - 문자열이 한 줄로 붙어 있는지 (줄바꿈이 들어가면 안 됩니다)")
        print("         - 프로젝트가 잠자기 상태면 잠시 후 다시 시도 (무료 플랜)")
        return False


def check_tables() -> bool:
    print("\n[3/5] 표(테이블) 확인")
    try:
        from .db import fetch_all, get_conn

        expected = {"ticker", "daily_price", "ingest_log", "financial", "dart_log"}
        with get_conn() as conn:
            rows = fetch_all(
                conn,
                """
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name IN
                       ('ticker','daily_price','ingest_log','financial','dart_log')
                 ORDER BY table_name;
                """,
            )
            names = [r[0] for r in rows]

            if len(names) < len(expected):
                missing = expected - set(names)
                print(f"{NG} 표가 없습니다: {', '.join(sorted(missing))}")
                print("       해결: .venv\\Scripts\\python.exe -m src.create_tables")
                return False

            print(f"{OK} 표 {len(expected):,}개 모두 있습니다: {', '.join(names)}")

            from .store import summary

            info = summary(conn)
            print(f"       등록 종목 : {info['ticker_total']:,}개")
            print(f"       시세 데이터: {info['price_rows']:,}건")
            if info["first_date"]:
                print(f"       보유 기간 : {info['first_date']} ~ {info['last_date']}")
            else:
                print("       보유 기간 : (아직 없음 — backfill 을 실행하세요)")
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} 확인 실패: {exc}")
        return False


def check_krx() -> bool:
    print("\n[4/5] 한국거래소 로그인 확인")
    try:
        from .config import get_krx_credentials

        krx_id, krx_pw = get_krx_credentials()
        print(f"       아이디: {krx_id} / 비밀번호: {_mask(krx_pw)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} {exc}")
        return False

    try:
        from .krx import ensure_login

        ensure_login()

        # 실제로 데이터가 나오는지 한 건만 받아봅니다
        from datetime import timedelta

        from .krx import fetch_stock_prices, kst_today

        probe = kst_today()
        for _ in range(8):
            if probe.weekday() < 5:
                rows = fetch_stock_prices(probe)
                if rows:
                    print(f"{OK} {probe} 시세 {len(rows):,}종목 수신 성공.")
                    sample = rows[0]
                    print(f"       예시 → 종목 {sample[0]} / 종가 {sample[2]:,}원")
                    return True
            probe -= timedelta(days=1)

        print(f"{NG} 로그인은 됐지만 최근 8일간 데이터를 받지 못했습니다.")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} {exc}")
        return False


def check_dart() -> bool | None:
    """
    DART 연결을 확인합니다.

    돌려주는 값
      True  : 정상
      False : 키는 있는데 연결이 안 됨
      None  : 키가 아예 없음 (재무지표를 안 쓰신다면 문제 없음)
    """
    print("\n[5/5] DART 재무지표 확인  (선택 기능)")
    try:
        from .config import get_dart_api_key

        key = get_dart_api_key()
        print(f"       인증키: {key[:4]}{'*' * 32}{key[-4:]} ({len(key)}자)")
    except Exception as exc:  # noqa: BLE001
        print("  [ 건너뜀 ] DART 인증키가 없습니다.")
        print("       재무지표(ROE·부채비율 등)를 쓰지 않으신다면 문제 없습니다.")
        print("       시세 수집과 화면은 이것 없이도 정상 동작합니다.")
        print(f"       {str(exc).strip().splitlines()[0]}")
        return None

    try:
        from .dart import REPORT_CODE, DartClient

        dart = DartClient()
        data = dart.get(
            "fnlttMultiAcnt",
            corp_code="00126380",  # 삼성전자
            bsns_year="2025",
            reprt_code=REPORT_CODE[4],
        )
        if str(data.get("status")) != "000":
            print(f"{NG} DART 응답 이상: {data.get('status')} {data.get('message')}")
            return False
        print(f"{OK} 삼성전자 재무제표 {len(data.get('list', [])):,}개 계정 수신 성공.")
    except Exception as exc:  # noqa: BLE001
        print(f"{NG} {exc}")
        return False

    # 회사코드 대응표가 준비되어 있는지도 봅니다
    try:
        from .db import fetch_all, get_conn

        with get_conn() as conn:
            mapped = fetch_all(
                conn, "SELECT count(*) FROM ticker WHERE dart_corp_code IS NOT NULL;"
            )[0][0]
            fin_rows = fetch_all(conn, "SELECT count(*) FROM financial;")[0][0]
        print(f"       회사코드 연결된 종목: {mapped:,}개")
        print(f"       저장된 재무지표    : {fin_rows:,}건")
        if mapped == 0:
            print("       → 아직 대응표가 없습니다. 아래를 실행하세요:")
            print("          .venv\\Scripts\\python.exe -m src.dart_corpcode")
    except Exception as exc:  # noqa: BLE001
        print(f"       (대응표 확인 실패: {exc})")

    return True


def main() -> None:
    print("=" * 62)
    print(" 설정 점검")
    print("=" * 62)

    results: dict[str, bool | None] = {
        ".env 파일": check_env_file(),
        "데이터베이스": check_database(),
        "표(테이블)": check_tables(),
        "거래소 로그인": check_krx(),
        "DART (선택)": check_dart(),
    }

    print("\n" + "=" * 62)
    print(" 점검 결과 요약")
    print("=" * 62)
    for name, ok in results.items():
        mark = "건너뜀" if ok is None else ("정상" if ok else "문제")
        print(f"  {mark:<4}  {name}")

    required = [v for k, v in results.items() if k != "DART (선택)"]
    if all(required):
        print("\n  시세 기능은 모두 정상입니다.")
        if results["DART (선택)"] is None:
            print("  (재무지표를 쓰시려면 .env 에 DART_API_KEY 를 추가하세요)")
        elif results["DART (선택)"] is False:
            print("  (재무지표 쪽에 문제가 있지만, 시세 기능에는 영향이 없습니다)")
        else:
            print("  재무지표 기능도 정상입니다!")
    else:
        print("\n  위에 '[ 문제 ]' 로 표시된 항목의 해결 안내를 따라 주세요.")


if __name__ == "__main__":
    main()
