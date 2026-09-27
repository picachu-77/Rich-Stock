# -*- coding: utf-8 -*-
"""
'현금ㆍ현물배당결정' 공시에서 배당 내용을 읽어내는 파일.

왜 공시를 읽나요?
  배당 정보는 두 군데에 있는데, 필요한 것이 서로 다릅니다.

    alotMatter (정기보고서)  주당배당금·배당수익률·배당성향을 3년치.
                             **배당기준일이 없습니다.**
    현금ㆍ현물배당결정 공시   1주당 얼마를, **언제 기준으로**, 언제 주는지.

  "배당 받으려면 언제까지 사야 하나" 에 답하려면 두 번째가 필요합니다.

★ 언제까지 사야 받나 ★
  공시 원문이 규칙을 직접 적어둡니다 —
    "시가배당율은 배당기준일 전전거래일(배당부 종가일)부터 …"
  즉 **배당기준일의 전전 거래일**까지 사야 주주명부에 오릅니다.
  주식은 사고 나서 내 것이 되기까지 이틀이 걸리기 때문입니다.

★ 조심할 것: 글자표가 거짓말을 합니다 ★
  원문 파일은 이름이 .xml 인데 내용은 HTML 이고,
  머리에 charset=euc-kr 이라고 적혀 있는데 **실제로는 UTF-8** 입니다.
  선언을 믿고 euc-kr 로 풀면 오류가 납니다. 실제로 그랬습니다.
  그래서 선언을 무시하고 내용으로 판단합니다.

★ 2024년부터 달라진 것 ★
  예전에는 '12월 마지막 거래일 이틀 전까지 사면 된다' 가 통했습니다.
  지금은 배당액을 먼저 정하고 기준일을 뒤로 미루는 회사가 늘어서
  회사마다 다릅니다. 규칙이 아니라 회사별 실제 날짜를 봐야 합니다.
  (삼성전자 2026년 분기배당은 기준일 6/30, 결의일 7/30 이었습니다 —
   기준일이 결의보다 먼저입니다)
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date


@dataclass
class Dividend:
    """공시 한 건에서 읽어낸 배당 내용."""
    rcept_no: str
    kind: str | None            # 분기배당 · 결산배당 · 중간배당 …
    per_share: int | None       # 보통주 1주당 배당금 (원)
    per_share_pref: int | None  # 우선주(종류주식) 1주당 배당금 (원)
    yield_pct: float | None     # 시가배당률 (%)
    record_date: date | None    # 배당기준일 — 이 날 주주명부에 있어야 받습니다
    pay_date: date | None       # 지급 예정일
    decided_at: date | None     # 이사회결의일


def to_text(payload: bytes) -> str:
    """
    공시 원문(ZIP)을 글자로 풉니다.

    파일 이름은 .xml 이지만 내용은 HTML 이고, 머리에 적힌 charset 은
    믿을 수 없습니다. 그래서 몇 가지로 풀어보고 '배당' 이 가장 많이
    나오는 쪽을 고릅니다 — 글자가 깨졌는지는 내용으로 압니다.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        return ""
    names = zf.namelist()
    if not names:
        return ""
    raw = zf.read(names[0])

    best = ""
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            s = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if s.count("배당") > best.count("배당"):
            best = s
    return best


def flatten(html: str) -> str:
    """태그를 걷어내고 공백을 하나로 모읍니다."""
    s = re.sub(r"<[^>]+>", " ", html)
    s = s.replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _date(text: str, label: str) -> date | None:
    """'배당기준일 2026-06-30' 에서 날짜를 꺼냅니다.

    ★ 날짜가 붙어 있을 때만 찾습니다 ★
      원문 아래쪽에 "…시가배당율은 배당기준일 전전거래일…" 같은 설명이
      또 나옵니다. 날짜를 요구하면 그런 문장에는 안 걸립니다.
    """
    m = re.search(rf"{label}\s*(\d{{4}})[-.\s]*(\d{{1,2}})[-.\s]*(\d{{1,2}})", text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _won(text: str, label: str) -> int | None:
    m = re.search(rf"{label}\s*([\d,]+)", text)
    if not m:
        return None
    try:
        v = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    # 0 은 '아직 안 정해졌다' 는 뜻으로 쓰입니다. '0원 배당' 이 아닙니다.
    return v or None


def parse(rcept_no: str, payload: bytes) -> Dividend | None:
    """공시 원문 한 건을 읽습니다. 배당기준일이 없으면 버립니다."""
    text = flatten(to_text(payload))
    if not text or "배당" not in text:
        return None

    record = _date(text, "배당기준일")
    if record is None:
        # 기준일이 없는 배당 공시는 우리가 쓸 데가 없습니다.
        # ('언제까지 사야 하나' 에 답을 못 합니다)
        return None

    kind = None
    m = re.search(r"배당구분\s*(\S+?)배당", text)
    if m:
        kind = f"{m.group(1)}배당"

    # "1주당 배당금(원) 보통주식 374 종류주식 374"
    보통 = _won(text, r"1주당\s*배당금\(원\)\s*보통주식")
    종류 = None
    m = re.search(r"1주당\s*배당금\(원\).{0,40}?종류주식\s*([\d,]+)", text)
    if m:
        try:
            종류 = int(m.group(1).replace(",", "")) or None
        except ValueError:
            종류 = None

    율 = None
    m = re.search(r"시가배당률?\(%\)\s*보통주식\s*([\d.]+)", text)
    if m:
        try:
            율 = float(m.group(1)) or None
        except ValueError:
            율 = None

    return Dividend(
        rcept_no=rcept_no,
        kind=kind,
        per_share=보통,
        per_share_pref=종류,
        yield_pct=율,
        record_date=record,
        pay_date=_date(text, r"배당금지급\s*예정일자"),
        decided_at=_date(text, r"이사회결의일\(결정일\)"),
    )


def buy_by(record: date, trading_days: list[date]) -> date | None:
    """
    이 날까지 사야 배당을 받습니다 — 배당기준일의 전전 거래일.

    쉬는 날을 넘겨짚지 않습니다. 실제로 장이 섰던 날(창고에 있는 시세
    날짜)만 봅니다. 그래서 기준일이 아직 오지 않았고 그 사이에 장이
    섰는지 알 수 없으면 **None 을 돌려줍니다.** 틀린 날짜를 알려주느니
    모른다고 하는 편이 낫습니다 — 하루 늦게 사면 못 받습니다.
    """
    before = [d for d in trading_days if d < record]
    if len(before) < 2:
        return None
    # 기준일 당일이 거래일 목록에 있어야 '그 앞'을 셀 수 있습니다.
    if record not in trading_days and record > max(trading_days):
        return None
    return before[-2]
