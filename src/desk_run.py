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
                   screen_long, screen_short, split_verdicts, tech_facts)
from .store import save_desk_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="여섯 부서로 종목을 봅니다")
    p.add_argument("--code", help="종목 하나만 (없으면 스크리닝 결과)")
    p.add_argument("--top", type=int, default=3,
                   help="거르기마다 상위 몇 종목 (기본 3)")
    p.add_argument("--horizon", choices=["long", "short", "both"], default="both",
                   help="어느 거르기를 돌릴지 (기본 both)")
    p.add_argument("--min-cap", type=int, default=1000, help="최소 시가총액(억)")
    p.add_argument("--min-value", type=float, default=10.0,
                   help="최소 하루 거래대금(억). 팔 수 있어야 후보입니다")
    p.add_argument("--dry-run", action="store_true",
                   help="Claude 를 부르지 않고 무엇을 보낼지만 봅니다")
    return p.parse_args()


def 종목이름(conn, code: str) -> str:
    rows = fetch_all(conn, "SELECT name FROM ticker WHERE code = %s", (code,))
    return rows[0][0] if rows else code


def 한종목(conn, code: str, name: str, 시장: dict,
           dry: bool) -> tuple[dict, str | None, str | None]:
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

    장기, 단기 = split_verdicts(결론.text)
    return {r.desk: r.text for r in 보고}, 장기, 단기


def main() -> None:
    args = parse_args()

    print("=" * 58)
    print(" 여섯 부서")
    print(f" 빠른 모델 {FAST} · 판단 모델 {DEEP}")
    if args.dry_run:
        print(" (시험 — Claude 를 부르지 않습니다)")
    print("=" * 58)

    with get_conn() as conn:
        대상: list[tuple[str, str, str]] = []   # (코드, 이름, 어느 거르기)

        if args.code:
            대상 = [(args.code, 종목이름(conn, args.code), "직접")]
        else:
            print("\n▸ 01 스크리닝부 (규칙으로 거릅니다 — AI 안 씁니다)")
            찾음: dict[str, tuple[str, str]] = {}

            if args.horizon in ("long", "both"):
                rows = screen_long(conn, args.top, args.min_cap, args.min_value)
                print(f"\n  [장기] 실적이 늘고, 빚이 적고, 값이 과하지 않은 회사 — {len(rows)}종목")
                for r in rows:
                    print(f"    {r[1]} ({r[0]}) · {r[2] or '업종없음'} · "
                          f"시총 {int(r[4]):,}억 · ROE {float(r[6]):.1f}% · "
                          f"부채 {float(r[7]):.0f}%")
                    찾음[r[0]] = (r[1], "long")

            if args.horizon in ("short", "both"):
                # 단기는 거래대금 최소선을 높게 잡습니다 (자주 사고팝니다)
                rows = screen_short(conn, args.top, args.min_cap,
                                    max(args.min_value, 30.0))
                print(f"\n  [단기] 최근 흐름과 거래가 살아난 회사 — {len(rows)}종목")
                for r in rows:
                    print(f"    {r[1]} ({r[0]}) · {r[2] or '업종없음'} · "
                          f"거래대금 {float(r[7]):,.0f}억 → {float(r[6]):,.0f}억 · "
                          f"20일평균 대비 {float(r[9]):+.1f}% · 변동성 {float(r[8]):.0f}%")
                    앞 = 찾음.get(r[0])
                    찾음[r[0]] = (r[1], "both" if 앞 else "short")

            대상 = [(c, n, h) for c, (n, h) in 찾음.items()]
            if not 대상:
                print("\n   조건에 맞는 종목이 없습니다.")
                return

        print(f"\n부를 횟수: {len(대상)}종목 × 5번 = {len(대상) * 5}번")

        시장 = market_facts(conn)
        저장 = 0
        for code, name, found_by in 대상:
            try:
                reports, 장기, 단기 = 한종목(conn, code, name, 시장, args.dry_run)
            except DeskError as exc:
                print(f"\n! {exc}")
                sys.exit(1)
            if not args.dry_run:
                save_desk_report(conn, code, reports, 장기, 단기, found_by,
                                 f"{FAST}+{DEEP}")
                conn.commit()
                저장 += 1
                print(f"\n  → 저장 (장기 {장기 or '못 읽음'} · 단기 {단기 or '못 읽음'})")

        print(f"\n{'=' * 58}")
        print(f" 끝. {저장}건 저장" if 저장 else " 끝. (시험이라 저장하지 않았습니다)")
        print("=" * 58)


if __name__ == "__main__":
    main()
