# -*- coding: utf-8 -*-
"""
배당 기준일을 어디서 받을 수 있는지 **확인만** 하는 파일.

왜 이런 걸 따로 만드나요?
  배당락일은 우리 창고에 없는 자료입니다. 어디서 받아야 하는지도
  모릅니다. 이럴 때 "아마 이 주소일 것이다" 하고 코드를 쓰면,
  404 를 받고 나서야 틀린 줄 압니다. 실제로 이 프로젝트에서 한 번
  그랬습니다(한경컨센서스 때 없는 주소를 찍었습니다).

  그래서 먼저 두드려보기만 하는 파일을 만듭니다.
  **아무것도 저장하지 않습니다.** 무엇이 오는지 눈으로 보기만 합니다.

무엇을 확인하나요?
  1) alotMatter (배당에 관한 사항)
     정기보고서에 실린 배당 정보입니다. 주당배당금·배당수익률은
     여기 있을 것으로 보이는데, **배당기준일(날짜)이 들어 있는지**를
     확인해야 합니다. 없으면 이 창구만으로는 "언제까지 사야 하나" 에
     답할 수 없습니다.

  2) list (공시검색)
     '현금ㆍ현물배당결정' 공시가 실제로 어떤 제목으로 오는지,
     접수번호(rcept_no)를 얻을 수 있는지 봅니다.

  3) document (공시서류 원본)
     2)에서 얻은 접수번호로 공시 원문을 받아, 그 안에 배당기준일이
     적혀 있는지 봅니다. 원문은 ZIP 안의 XML 이라 JSON 창구를 쓰는
     기존 도구로는 못 받습니다. 여기서만 직접 받아 봅니다.

쓰는 법
    python -m src.dividend_probe                 # 삼성전자로 확인
    python -m src.dividend_probe --code 005930 --year 2025
"""

from __future__ import annotations

import argparse
import io
import re
import zipfile

import requests

from .config import get_dart_api_key
from .dart import BASE_URL, REPORT_CODE, DartClient
from .db import fetch_all, get_conn


def corp_code_of(conn, stock_code: str) -> tuple[str, str] | None:
    """종목코드 → DART 회사코드. 창고에 이미 받아둔 대응표를 씁니다."""
    rows = fetch_all(
        conn,
        "SELECT dart_corp_code, name FROM ticker WHERE code = %s",
        (stock_code,),
    )
    if not rows or not rows[0][0]:
        return None
    return rows[0][0], rows[0][1]


def show(title: str) -> None:
    print()
    print("─" * 62)
    print(f" {title}")
    print("─" * 62)


def probe_alot(dart: DartClient, corp: str, year: int) -> None:
    """1) 배당에 관한 사항 — 날짜가 들어 있는가?"""
    show(f"1) alotMatter — 배당에 관한 사항 ({year}년 사업보고서)")
    try:
        data = dart.get(
            "alotMatter",
            corp_code=corp,
            bsns_year=str(year),
            reprt_code=REPORT_CODE[4],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 부르지 못했습니다: {exc}")
        return

    print(f"  status = {data.get('status')}  ({data.get('message')})")
    items = data.get("list") or []
    if not items:
        print("  자료 없음")
        return

    print(f"  {len(items)}줄")
    print(f"  필드 이름: {sorted(items[0].keys())}")
    print()
    print("  ── 받은 줄 그대로 ──")
    for row in items[:14]:
        parts = [f"{k}={v!r}" for k, v in row.items()
                 if k not in ("rcept_no", "corp_code", "corp_cls", "corp_name")]
        print(f"    {' · '.join(parts)}")

    # 날짜처럼 생긴 값이 하나라도 있나
    날짜 = []
    for row in items:
        for k, v in row.items():
            if isinstance(v, str) and re.search(r"\d{4}[-.년/]\s?\d{1,2}", v):
                날짜.append((k, v))
    print()
    print(f"  ★ 날짜처럼 생긴 값: {날짜[:8] if 날짜 else '없음'}")
    if not 날짜:
        print("    → 이 창구에는 배당기준일이 없습니다. 3)을 봐야 합니다.")


def probe_list(dart: DartClient, corp: str, year: int) -> list[dict]:
    """2) 배당 결정 공시가 어떤 모습으로 오는가?"""
    show("2) list — '현금ㆍ현물배당결정' 공시 찾기")
    found: list[dict] = []
    try:
        data = dart.get(
            "list",
            corp_code=corp,
            bgn_de=f"{year}0101",
            end_de=f"{year + 1}1231",
            page_count="100",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 부르지 못했습니다: {exc}")
        return found

    print(f"  status = {data.get('status')}  ({data.get('message')})")
    items = data.get("list") or []
    print(f"  공시 {len(items)}건 중 배당이 들어간 제목만:")
    for row in items:
        nm = row.get("report_nm", "")
        if "배당" in nm:
            found.append(row)
            print(f"    {row.get('rcept_dt')}  {nm}  (접수 {row.get('rcept_no')})")
    if not found:
        print("    (없음)")
    return found


def probe_document(rcept_no: str) -> None:
    """3) 공시 원문에 배당기준일이 있는가?"""
    show(f"3) document — 공시 원문 (접수 {rcept_no})")
    url = f"{BASE_URL}/document.xml"
    try:
        resp = requests.get(
            url, params={"crtfc_key": get_dart_api_key(), "rcept_no": rcept_no},
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 받지 못했습니다: {exc}")
        return

    print(f"  HTTP {resp.status_code} · {len(resp.content):,} 바이트")
    print(f"  Content-Type: {resp.headers.get('Content-Type')}")

    # 오류면 XML 로 짧게 옵니다
    head = resp.content[:400]
    if b"<result>" in head or b"status" in head[:120]:
        print(f"  응답 앞부분: {head[:300]!r}")
        return

    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! ZIP 이 아닙니다: {exc}")
        print(f"  앞부분: {head[:200]!r}")
        return

    print(f"  ZIP 안: {zf.namelist()}")
    raw = zf.read(zf.namelist()[0])
    print(f"  푼 크기 {len(raw):,} 바이트")
    print(f"  앞 120바이트 그대로: {raw[:120]!r}")

    # ★ 어느 글자표로 풀어야 하는지 모릅니다 ★
    #   지난번에 utf-8 로 풀고 '배당' 이 안 나오길래 '내용이 없나' 했는데,
    #   원문을 찍어보지 않아서 확인할 수가 없었습니다. 이번에는 둘 다
    #   풀어보고 '배당' 이 나오는 쪽을 씁니다. 글자가 깨졌는지 아닌지는
    #   추측하지 말고 내용으로 판단합니다.
    후보 = {}
    for enc in ("euc-kr", "cp949", "utf-8"):
        try:
            후보[enc] = raw.decode(enc)
        except Exception as exc:  # noqa: BLE001
            print(f"  {enc}: 못 품 ({exc})")
    print()
    print("  ── 글자표별로 '배당' 이 몇 번 나오나 ──")
    for enc, s in 후보.items():
        print(f"    {enc:8} 배당 {s.count('배당'):3}회 · 기준일 {s.count('기준일'):3}회 "
              f"· 못 읽은 글자 {s.count(chr(0xFFFD)):3}개")

    best = max(후보.items(), key=lambda kv: kv[1].count("배당"), default=(None, ""))
    if not best[0] or best[1].count("배당") == 0:
        print()
        print("  ! 어느 글자표로 풀어도 '배당' 이 없습니다.")
        print("    이 파일은 겉표지일 뿐이고 알맹이가 따로 있을 수 있습니다.")
        print()
        print("  ── 푼 내용 앞 1,200자 (euc-kr 기준) ──")
        s = 후보.get("euc-kr") or 후보.get("utf-8") or ""
        print("    " + s[:1200].replace("\n", "\n    "))
        return

    enc, text = best
    print(f"\n  → {enc} 로 읽습니다")
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)
    print(f"  글자 수 {len(plain):,}")

    print()
    print("  ── '기준일' 이 나오는 자리 ──")
    hits = 0
    for m in re.finditer(r"기준일", plain):
        s = max(0, m.start() - 80)
        print(f"    …{plain[s:m.end() + 80]}…")
        hits += 1
        if hits >= 8:
            break
    if not hits:
        print("    (없음)")

    print()
    print("  ── 내용 앞 1,500자 ──")
    print("    " + plain[:1500])


def probe_accounts(dart: DartClient, corp: str, year: int) -> None:
    """
    4) fnlttMultiAcnt — 재무 호출이 **어떤 계정까지 주는지**.

    지금 우리는 매출·영업이익·순이익·자산·부채·자본 여섯 개만 뽑아
    쓰고 있습니다. 그런데 같은 호출에 다른 계정도 함께 올 수 있습니다.
    이미 받고 있는데 안 쓰는 것이 있다면 공짜로 늘릴 수 있습니다.

    특히 보고 싶은 것: 유동자산·유동부채 (→ 유동비율)
    """
    show(f"4) fnlttMultiAcnt — 재무 호출이 주는 계정 전부 ({year}년)")
    try:
        data = dart.get(
            "fnlttMultiAcnt",
            corp_code=corp,
            bsns_year=str(year),
            reprt_code=REPORT_CODE[4],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 부르지 못했습니다: {exc}")
        return

    print(f"  status = {data.get('status')}  ({data.get('message')})")
    items = data.get("list") or []
    if not items:
        print("  자료 없음")
        return

    보임 = {}
    for it in items:
        nm = (it.get("account_nm") or "").strip()
        if nm and nm not in 보임:
            보임[nm] = (it.get("fs_div"), it.get("thstrm_amount"))

    print(f"  {len(items)}줄 · 계정 이름 {len(보임)}가지")
    print()
    for nm, (fs, amt) in sorted(보임.items()):
        print(f"    {nm:28} fs={fs}  {amt}")

    print()
    찾는것 = ["유동자산", "유동부채", "비유동자산", "비유동부채",
             "이익잉여금", "자본금", "매출총이익", "영업활동현금흐름"]
    print("  ★ 넣고 싶은 것이 오는가")
    for 이름 in 찾는것:
        있음 = any(이름 in nm for nm in 보임)
        print(f"    {이름:16} {'온다  ✓' if 있음 else '안 온다'}")


def main() -> None:
    p = argparse.ArgumentParser(description="배당 기준일을 어디서 받을지 확인만 합니다")
    p.add_argument("--code", default="005930", help="종목코드 (기본 005930 삼성전자)")
    p.add_argument("--year", type=int, default=2025, help="확인할 사업연도")
    args = p.parse_args()

    print("=" * 62)
    print(" 배당 기준일 — 어디서 받을 수 있는지 확인")
    print(" (아무것도 저장하지 않습니다)")
    print("=" * 62)

    with get_conn() as conn:
        got = corp_code_of(conn, args.code)
    if not got:
        print(f"! {args.code} 의 DART 회사코드가 창고에 없습니다.")
        return
    corp, name = got
    print(f" 대상: {name} ({args.code}) · DART 회사코드 {corp}")

    dart = DartClient(api_key=get_dart_api_key())

    probe_alot(dart, corp, args.year)
    found = probe_list(dart, corp, args.year)
    if found:
        probe_document(found[0]["rcept_no"])
    else:
        print("\n  배당 공시를 못 찾아 3)은 건너뜁니다.")

    probe_accounts(dart, corp, args.year)

    print()
    print("=" * 62)
    print(" 확인 끝. 이 결과를 보고 어느 창구를 쓸지 정합니다.")
    print("=" * 62)


if __name__ == "__main__":
    main()
