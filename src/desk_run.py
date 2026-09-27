# -*- coding: utf-8 -*-
"""
여섯 부서를 돌립니다.

    python -m src.desk_run --dry-run          # 부르지 않고 준비만 확인
    python -m src.desk_run --code 005930      # 한 종목만
    python -m src.desk_run --top 5            # 스크리닝 상위 5종목

★ 한 종목에 Claude 를 다섯 번 부릅니다 ★
  02·03·04 를 먼저(빠른 모델), 그 보고서를 05 리스크관리부에 넘겨
  반대하게 하고, 마지막에 06 운용부가 모읍니다.
  01 스크리닝부는 SQL 이라 부르지 않습니다.

★ 돈이 듭니다 ★
  종목 수 × 5번입니다. --top 을 크게 잡기 전에 --dry-run 으로 먼저
  얼마나 부르게 되는지 보세요.
"""

from __future__ import annotations

import argparse
import re
import sys

from .db import fetch_all, get_conn
from .desk import (DEEP, FAST, DeskError, Report, company_news,
                   fundamental_facts, market_facts, risk_facts, run_desk,
                   screen, tech_facts)
from .store import save_desk_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="여섯 부서로 종목을 봅니다")
    p.add_argument("--code", help="종목 하나만 (없으면 스크리닝 결과)")
    p.add_argument("--top", type=int, default=3, help="스크리닝 상위 몇 종목 (기본 3)")
    p.add_argument("--min-cap", type=int, default=1000, help="최소 시가총액(억)")
    p.add_argument("--min-value", type=float, default=10.0,
                   help="최소 하루 거래대금(억). 팔 수 있어야 후보입니다")
    p.add_argument("--dry-run", action="store_true",
                   help="Claude 를 부르지 않고 무엇을 보낼지만 봅니다")
    return p.parse_args()


def 종목이름(conn, code: str) -> str:
    rows = fetch_all(conn, "SELECT name FROM ticker WHERE code = %s", (code,))
    return rows[0][0] if rows else code


def 의견뽑기(글: str) -> str | None:
    """운용부 보고서에서 관심/보류/제외를 찾습니다."""
    m = re.search(r"(관심|보류|제외)", 글)
    return m.group(1) if m else None


def 한종목(conn, code: str, name: str, 시장: dict, dry: bool) -> tuple[dict, str | None]:
    print(f"\n{'═' * 58}")
    print(f" {name} ({code})")
    print("═" * 58)

    보고: list[Report] = []

    for 부서, 자료 in (
        ("기술적분석부", tech_facts(conn, code)),
        ("펀더멘탈부", fundamental_facts(conn, code)),
        ("마켓부", {**시장, **company_news(conn, code)}),
    ):
        print(f"\n▸ {부서}")
        r = run_desk(부서, 자료, dry=dry)
        보고.append(r)
        print(r.text)

    print("\n▸ 리스크관리부 (앞 세 부서에 반대합니다)")
    위험 = run_desk("리스크관리부", risk_facts(conn, code), 앞선보고=보고, dry=dry)
    보고.append(위험)
    print(위험.text)

    print("\n▸ 운용부")
    결론 = run_desk("운용부", {"종목": name, "코드": code}, 앞선보고=보고, dry=dry)
    보고.append(결론)
    print(결론.text)

    return {r.desk: r.text for r in 보고}, 의견뽑기(결론.text)


def main() -> None:
    args = parse_args()

    print("=" * 58)
    print(" 여섯 부서")
    print(f" 빠른 모델 {FAST} · 판단 모델 {DEEP}")
    if args.dry_run:
        print(" (시험 — Claude 를 부르지 않습니다)")
    print("=" * 58)

    with get_conn() as conn:
        if args.code:
            대상 = [(args.code, 종목이름(conn, args.code))]
        else:
            print("\n▸ 01 스크리닝부 (규칙으로 거릅니다 — AI 안 씁니다)")
            rows = screen(conn, args.top, args.min_cap, args.min_value)
            대상 = [(r[0], r[1]) for r in rows]
            for r in rows:
                print(f"   {r[1]} ({r[0]}) · {r[2] or '업종없음'} · "
                      f"시총 {int(r[4]):,}억 · 하루 거래대금 {float(r[5]):,.0f}억")
            if not 대상:
                print("   조건에 맞는 종목이 없습니다.")
                return

        print(f"\n부를 횟수: {len(대상)}종목 × 5번 = {len(대상) * 5}번")

        시장 = market_facts(conn)
        저장 = 0
        for code, name in 대상:
            try:
                reports, verdict = 한종목(conn, code, name, 시장, args.dry_run)
            except DeskError as exc:
                print(f"\n! {exc}")
                sys.exit(1)
            if not args.dry_run:
                save_desk_report(conn, code, reports, verdict, f"{FAST}+{DEEP}")
                conn.commit()
                저장 += 1
                print(f"\n  → 저장했습니다 (의견: {verdict or '못 읽음'})")

        print(f"\n{'=' * 58}")
        print(f" 끝. {저장}건 저장" if 저장 else " 끝. (시험이라 저장하지 않았습니다)")
        print("=" * 58)


if __name__ == "__main__":
    main()
