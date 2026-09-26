"""
한경컨센서스 정찰 — 화면이 어떻게 생겼는지 먼저 봅니다.

★ 왜 정찰부터 하나 ★
  한경컨센서스는 공식 창구(API)가 없습니다. 화면을 읽어서 뽑아내야
  하는데, 화면을 한 번도 못 본 채로 뽑아내는 코드를 쓸 수는 없습니다.
  DART·야후는 '무엇이 온다' 가 정해져 있었지만 여기는 아닙니다.

  그래서 이 파일은 아무것도 저장하지 않습니다. 받아온 화면이
  어떻게 생겼는지 찍어보기만 합니다. 그걸 보고 진짜 수집기를 씁니다.

★ 예의를 지킵니다 ★
  한 번에 한 쪽씩, 사이를 두고 부릅니다. 남의 서버입니다.

실행
    python -m src.consensus_probe
    python -m src.consensus_probe --kind industry
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.request
from datetime import date, timedelta

BASE = "http://consensus.hankyung.com"

# 어느 칸을 볼지. 오른쪽은 한경컨센서스 화면의 이름입니다.
KINDS = {
    "company": ("기업", "/apps.analysis/analysis.list"),
    "industry": ("산업", "/apps.analysis/analysis.list"),
    "market": ("시장", "/apps.analysis/analysis.list"),
    "economy": ("경제", "/apps.analysis/analysis.list"),
}

# 화면이 report_type 으로 칸을 가릅니다. 정확한 값은 정찰로 확인합니다.
REPORT_TYPE = {
    "company": "CO", "industry": "INDUSTRY", "market": "MARKET", "economy": "ECONOMY",
}

UA = ("Mozilla/5.0 (compatible; RichStock/1.0; 개인 학습용 수집기)")


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = r.headers.get_content_charset() or "utf-8"
        try:
            return r.status, raw.decode(enc, errors="replace")
        except LookupError:
            return r.status, raw.decode("utf-8", errors="replace")


def list_url(kind: str, page: int = 1, days: int = 7) -> str:
    end = date.today()
    start = end - timedelta(days=days)
    path = KINDS[kind][1]
    return (
        f"{BASE}{path}"
        f"?sdate={start:%Y-%m-%d}&edate={end:%Y-%m-%d}"
        f"&report_type={REPORT_TYPE[kind]}&pagenum=20&now_page={page}"
    )


def describe(html: str) -> None:
    """무엇이 들어 있는지 사람이 읽을 수 있게 요약합니다."""
    print(f"  길이 : {len(html):,}자")

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    print(f"  제목 : {title.group(1).strip() if title else '(없음)'}")

    tables = re.findall(r"<table[^>]*>", html, re.I)
    print(f"  표 개수 : {len(tables)}")
    for t in tables[:4]:
        print(f"    {t[:120]}")

    ths = re.findall(r"<th[^>]*>(.*?)</th>", html, re.S | re.I)
    clean = [re.sub(r"<[^>]+>", "", x).strip() for x in ths]
    clean = [x for x in clean if x]
    if clean:
        print(f"  표 머리글 ({len(clean)}개) : {' | '.join(clean[:15])}")
    else:
        print("  표 머리글 : (없음 — <th> 를 안 쓰는 화면일 수 있습니다)")

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    print(f"  줄(tr) 개수 : {len(rows)}")
    shown = 0
    for r in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S | re.I)
        if not cells:
            continue
        vals = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in cells]
        print(f"    {shown + 1}번째 줄 (칸 {len(vals)}개)")
        for i, v in enumerate(vals):
            print(f"        [{i}] {v[:70]}")
        shown += 1
        if shown >= 2:
            break

    # 보고서 하나를 가리키는 링크가 어떻게 생겼는지
    links = re.findall(r'href="([^"]*(?:report_idx|downpdf|analysis)[^"]*)"', html, re.I)
    if links:
        print(f"  보고서 링크 꼴 ({len(links)}개 중 3개)")
        for l in links[:3]:
            print(f"    {l[:110]}")

    # 쪽 넘김
    pages = re.findall(r'now_page=(\d+)', html)
    if pages:
        print(f"  쪽 번호 : {sorted(set(int(p) for p in pages))[:12]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="한경컨센서스 정찰")
    ap.add_argument("--kind", default="company", choices=list(KINDS))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--all", action="store_true", help="네 칸을 모두 봅니다")
    args = ap.parse_args()

    kinds = list(KINDS) if args.all else [args.kind]
    for n, kind in enumerate(kinds):
        label = KINDS[kind][0]
        url = list_url(kind, days=args.days)
        print("=" * 66)
        print(f" {label} 리포트")
        print("=" * 66)
        print(f"  주소 : {url}")
        try:
            status, html = fetch(url)
            print(f"  응답 : {status}")
            describe(html)
        except Exception as e:
            print(f"  ! 받지 못했습니다: {type(e).__name__} {e}")
        print()
        if n < len(kinds) - 1:
            time.sleep(2)     # 남의 서버입니다. 사이를 둡니다.


if __name__ == "__main__":
    main()
