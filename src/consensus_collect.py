"""
증권사 리포트 수집 (한경컨센서스).

실행
    python -m src.consensus_collect              # 최근 7일
    python -m src.consensus_collect --days 365   # 1년치 (처음 한 번)
    python -m src.consensus_collect --kinds CO   # 기업 리포트만

★ 남의 서버입니다 ★
  공식 창구(API)가 없어 화면을 읽습니다. 그래서 한 쪽씩, 사이를 두고,
  빈 쪽이 나오면 그만둡니다. 실패해도 다음 날 다시 받으면 되므로
  한 번에 다 받아야 하는 구조로 만들지 않았습니다.

★ 원문(PDF)은 받지 않습니다 ★
  제목·목표가·의견·작성자·출처만 저장하고, 읽으러는 한경컨센서스로
  보냅니다. 공시를 다루는 방식과 같습니다.
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from .consensus import REPORT_TYPE, list_url, parse_list
from .db import get_conn
from .store import save_reports

PAGE_SIZE = 50        # 한 쪽에 몇 건. 20이 기본값이지만 50도 받습니다
PAUSE = 1.5           # 쪽 사이에 쉬는 시간(초)
RETRY = 3
MAX_PAGES = 400       # 안전장치. 끝없이 도는 일이 없도록

UA = "Mozilla/5.0 (compatible; RichStock/1.0; personal study crawler)"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="증권사 리포트 수집")
    p.add_argument("--days", type=int, default=7, help="며칠치를 받을지 (기본 7)")
    p.add_argument("--kinds", default="CO,IN,MA,EC",
                   help="받을 갈래 (CO=기업 IN=산업 MA=시장 DE=파생 EC=경제)")
    p.add_argument("--dry-run", action="store_true",
                   help="저장하지 않고 읽어낸 것만 보여줍니다")
    return p.parse_args()


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    last: Exception | None = None
    for attempt in range(RETRY):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                enc = r.headers.get_content_charset() or "utf-8"
                return r.read().decode(enc, errors="replace")
        except Exception as e:
            last = e
            wait = PAUSE * (2 ** attempt)
            print(f"      · 다시 시도합니다 ({attempt + 1}/{RETRY}, {wait:.0f}초 뒤) — {e}")
            time.sleep(wait)
    raise RuntimeError(f"받지 못했습니다: {last}")


def collect_kind(kind: str, sdate: str, edate: str) -> list[dict]:
    """한 갈래를 처음 쪽부터 빈 쪽이 나올 때까지 받습니다."""
    got: dict[int, dict] = {}
    for page in range(1, MAX_PAGES + 1):
        url = list_url(kind, sdate, edate, page, PAGE_SIZE)
        try:
            html = fetch(url)
        except Exception as e:
            print(f"    ! {page}쪽에서 멈췄습니다: {e}")
            break

        rows = parse_list(html, kind)
        새것 = [r for r in rows if r["report_idx"] not in got]
        for r in 새것:
            got[r["report_idx"]] = r

        print(f"    · {page}쪽 — 읽은 것 {len(rows):,}건 (새것 {len(새것):,}건, 누적 {len(got):,}건)")

        # 빈 쪽이거나 새것이 하나도 없으면 끝입니다.
        # (쪽 번호를 믿지 않습니다. 화면이 바뀌면 그 숫자부터 틀립니다)
        if not rows or not 새것:
            break
        time.sleep(PAUSE)
    return list(got.values())


def main() -> None:
    args = parse_args()
    end = date.today()
    start = end - timedelta(days=args.days)
    kinds = [k.strip().upper() for k in args.kinds.split(",") if k.strip()]

    print("=" * 62)
    print(" 증권사 리포트 수집 (한경컨센서스)")
    print("=" * 62)
    print(f"  기간 : {start} ~ {end}")
    print(f"  갈래 : {', '.join(kinds)}")
    if args.dry_run:
        print("  [살펴보기만 — 저장하지 않습니다]")
    print()

    every: list[dict] = []
    for kind in kinds:
        name = {v: k for k, v in REPORT_TYPE.items()}.get(kind, kind)
        print(f"  {name} ({kind})")
        rows = collect_kind(kind, start.isoformat(), end.isoformat())
        print(f"    → {len(rows):,}건")
        every.extend(rows)
        time.sleep(PAUSE)

    print()
    있는코드 = sum(1 for r in every if r["code"])
    목표가 = [r["target_price"] for r in every if r["target_price"]]
    print(f"  모두 {len(every):,}건")
    print(f"    종목코드가 붙은 것 {있는코드:,}건")
    print(f"    목표주가가 있는 것 {len(목표가):,}건")
    if 목표가:
        print(f"      가장 낮은 것 {min(목표가):,}원 / 가장 높은 것 {max(목표가):,}원")

    의견 = {}
    for r in every:
        if r["opinion"]:
            의견[r["opinion"]] = 의견.get(r["opinion"], 0) + 1
    if 의견:
        print("    투자의견 : " + " · ".join(
            f"{k} {v:,}건" for k, v in sorted(의견.items(), key=lambda x: -x[1])))

    print()
    print("  앞 3건")
    for r in every[:3]:
        print(f"    {r['written_at']} [{r['kind']}] {r['title'][:52]}")
        print(f"      종목 {r['code'] or '-'} · 목표 {r['target_price'] or '-'} · "
              f"{r['opinion'] or '-'} · {r['house'] or '-'}")

    if args.dry_run:
        print()
        print("  저장하지 않았습니다.")
        print("=" * 62)
        return

    with get_conn() as conn:
        saved = save_reports(conn, every)
        conn.commit()
    print()
    print(f"  {saved:,}건을 저장했습니다.")
    print("=" * 62)


if __name__ == "__main__":
    main()
