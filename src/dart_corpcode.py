"""
종목코드(6자리) → DART 회사코드(8자리) 대응표를 만들어 저장하는 스크립트.

실행 방법:
    .venv\\Scripts\\python.exe -m src.dart_corpcode

왜 필요한가요?
    우리가 아는 삼성전자 종목코드는 005930 이지만,
    DART 는 자기들만의 회사코드 00126380 으로 조회합니다.
    이 둘을 이어주는 표가 있어야 재무지표를 받아올 수 있습니다.

효율
    DART 가 전체 회사 목록을 ZIP 파일 하나로 주기 때문에
    API 호출 단 1건으로 9만여 회사의 대응표를 받습니다.

    한 번 만들어 ticker 표의 dart_corp_code 칸에 저장해두면
    이후 재무지표 수집 때 다시 받을 필요가 없습니다.
    (신규 상장이 생기면 다시 실행하면 됩니다)
"""

from __future__ import annotations

from .dart import DartClient
from .db import bulk_upsert, fetch_all, get_conn


def main() -> None:
    print("=" * 62)
    print(" 종목코드 → DART 회사코드 대응표 만들기")
    print("=" * 62)

    dart = DartClient()

    print("\n[1/3] DART 에서 전체 회사코드 목록을 내려받는 중...")
    print("      (파일이 커서 20~60초 정도 걸립니다)")
    mapping = dart.download_corp_codes()
    print(f"      상장회사 {len(mapping):,}곳의 대응 정보를 받았습니다.")

    print("\n[2/3] 우리 종목 목록과 맞춰보는 중...")
    with get_conn() as conn:
        rows = fetch_all(
            conn,
            "SELECT code, name, kind FROM ticker WHERE is_active = TRUE ORDER BY code;",
        )

        matched: list[tuple] = []
        preferred: list[tuple] = []
        unmatched_stock: list[str] = []
        etf_count = 0

        for code, name, kind in rows:
            if kind == "ETF":
                # ETF 는 펀드라서 DART 재무제표 대상이 아닙니다 (정상)
                etf_count += 1
                continue

            info = mapping.get(code)
            if info and info["corp_code"]:
                matched.append((code, info["corp_code"]))
                continue

            # ── 우선주 처리 ──
            # 우선주(삼성전자우 005935)는 DART 에 별도 코드가 없습니다.
            # 같은 회사이므로 보통주(삼성전자 005930)의 회사코드를 씁니다.
            # 국내 종목코드 규칙: 우선주는 보통주의 마지막 한 자리만 다릅니다.
            common_code = code[:5] + "0"
            parent = mapping.get(common_code)
            if parent and parent["corp_code"] and common_code != code:
                preferred.append((code, parent["corp_code"]))
            else:
                unmatched_stock.append(f"{name}({code})")

        total_stock = len(matched) + len(preferred) + len(unmatched_stock)
        print(f"      일반주식 {total_stock:,}곳 중 {len(matched):,}곳 직접 연결")
        print(f"      우선주 {len(preferred):,}곳은 보통주(모회사) 재무제표에 연결")
        print(f"      ETF {etf_count:,}곳은 대상 아님 (펀드는 재무제표를 내지 않습니다)")
        if unmatched_stock:
            print(f"      연결 실패 {len(unmatched_stock)}곳: "
                  f"{', '.join(unmatched_stock[:8])}"
                  f"{' ...' if len(unmatched_stock) > 8 else ''}")

        matched.extend(preferred)

        print("\n[3/3] 종목 표에 저장하는 중...")
        # 이미 있는 종목의 dart_corp_code 칸만 채웁니다.
        # (새 줄을 만들지 않으므로 이름이 빈 껍데기 행이 생길 일이 없습니다)
        saved = bulk_upsert(
            conn,
            """
            UPDATE ticker AS t
               SET dart_corp_code = v.corp_code,
                   updated_at = now()
              FROM (VALUES %s) AS v(code, corp_code)
             WHERE t.code = v.code;
            """,
            matched,
        )

        total_with_code = fetch_all(
            conn, "SELECT count(*) FROM ticker WHERE dart_corp_code IS NOT NULL;"
        )[0][0]

    print(f"      {saved:,}건 저장 완료")
    print()
    print("=" * 62)
    print(f" 완료!  회사코드가 연결된 종목: {total_with_code:,}개")
    print(f" DART API 호출: {dart.calls}건 (하루 한도 20,000건)")
    print("=" * 62)


if __name__ == "__main__":
    main()
