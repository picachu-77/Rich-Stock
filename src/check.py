"""
설정 점검 도구.  ★ 문제가 생기면 가장 먼저 이걸 실행해 보세요 ★

실행 방법:
    .venv\\Scripts\\python.exe -m src.check

확인하는 것 4가지
  1) .env 파일이 있고 값이 채워져 있는가
  2) Neon 데이터베이스에 접속이 되는가
  3) 표(테이블)가 만들어져 있는가
  4) 한국거래소 로그인이 되는가
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
    print("\n[1/4] .env 파일 확인")
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
    print("\n[2/4] Neon 데이터베이스 접속 확인")
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
        print("         - Neon 대시보드에서 연결 문자열을 다시 복사했는지")
        print("         - 문자열이 한 줄로 붙어 있는지 (줄바꿈이 들어가면 안 됩니다)")
        print("         - Neon 프로젝트가 잠자기 상태면 잠시 후 다시 시도")
        return False


def check_tables() -> bool:
    print("\n[3/4] 표(테이블) 확인")
    try:
        from .db import fetch_all, get_conn

        with get_conn() as conn:
            rows = fetch_all(
                conn,
                """
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name IN ('ticker','daily_price','ingest_log')
                 ORDER BY table_name;
                """,
            )
            names = [r[0] for r in rows]

            if len(names) < 3:
                missing = {"ticker", "daily_price", "ingest_log"} - set(names)
                print(f"{NG} 표가 없습니다: {', '.join(sorted(missing))}")
                print("       해결: .venv\\Scripts\\python.exe -m src.create_tables")
                return False

            print(f"{OK} 표 3개 모두 있습니다: {', '.join(names)}")

            from .store import summary

            info = summary(conn)
            print(f"       등록 종목 : {info['ticker_total']}개")
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
    print("\n[4/4] 한국거래소 로그인 확인")
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


def main() -> None:
    print("=" * 62)
    print(" 설정 점검")
    print("=" * 62)

    results = {
        ".env 파일": check_env_file(),
        "데이터베이스": check_database(),
        "표(테이블)": check_tables(),
        "거래소 로그인": check_krx(),
    }

    print("\n" + "=" * 62)
    print(" 점검 결과 요약")
    print("=" * 62)
    for name, ok in results.items():
        print(f"  {'정상' if ok else '문제'}  {name}")

    if all(results.values()):
        print("\n  모두 정상입니다! 다음 단계로 진행하세요.")
    else:
        print("\n  위에 '[ 문제 ]' 로 표시된 항목의 해결 안내를 따라 주세요.")


if __name__ == "__main__":
    main()
