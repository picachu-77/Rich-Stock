"""
한경컨센서스 화면에서 리포트 목록을 뽑아냅니다.

★ 이 파일은 '읽어내기' 만 합니다 ★
  받아오기(consensus_collect.py)와 나눠 둡니다. 화면 구조는 언젠가
  바뀌는데, 그때 고칠 곳이 여기 하나여야 합니다. 그리고 이렇게 나눠
  두면 화면 없이도 시험할 수 있습니다 — 실제로 개발하는 쪽에서는
  바깥 접속이 막혀 있어 그 방법밖에 없습니다.

★ 화면 생김새 (2026-09 정찰) ★
  http://consensus.hankyung.com/analysis/list?skinType=business
      작성일 | 제목 | 적정가격 | 투자의견 | 작성자 | 제공출처 |
      기업정보 | 차트 | 첨부파일

  검색칸(GET)
      sdate · edate · now_page · pagenum · report_type · search_text

  report_type : CO=기업 / IN=산업 / MA=시장 / DE=파생 / EC=경제

★ 조심한 것 ★
  · 제목 칸에 같은 글이 두세 번 들어 있습니다(줄임말 + 원문).
  · 투자의견이 'Buy' 와 '매수' 로 섞여 옵니다.
  · 적정가격이 비거나 '-' 인 리포트가 있습니다 (목표주가 없는 보고서).
"""

from __future__ import annotations

import re

BASE = "http://consensus.hankyung.com"
LIST_PATH = "/analysis/list"

# 화면의 분류 → 우리가 쓸 이름
REPORT_TYPE = {
    "기업": "CO",
    "산업": "IN",
    "시장": "MA",
    "파생": "DE",
    "경제": "EC",
}
KIND_OF = {v: k for k, v in REPORT_TYPE.items()}


def list_url(
    report_type: str = "CO",
    sdate: str = "",
    edate: str = "",
    page: int = 1,
    pagenum: int = 20,
) -> str:
    """검색칸이 쓰는 그대로 주소를 만듭니다."""
    skin = {"CO": "business", "IN": "industry", "MA": "market",
            "DE": "derivative", "EC": "economy"}.get(report_type, "business")
    return (
        f"{BASE}{LIST_PATH}?skinType={skin}"
        f"&sdate={sdate}&edate={edate}"
        f"&now_page={page}&pagenum={pagenum}&report_type={report_type}"
    )


def _text(html: str) -> str:
    """태그를 떼고 공백을 정리합니다."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def clean_title(cell_html: str) -> str:
    """
    제목 칸에서 진짜 제목만 꺼냅니다.

    같은 글이 두세 번 들어 있습니다. title="..." 속성이 있으면 그게
    원문이라 먼저 씁니다. 없으면 앞 열두 글자가 다시 나오는 자리에서
    자릅니다.
    """
    attr = re.search(r'title="([^"]+)"', cell_html)
    if attr:
        return re.sub(r"\s+", " ", attr.group(1)).strip()

    t = _text(cell_html)

    # 딱 두 번 이어 붙은 경우 (가운데 띄어쓰기가 있을 수도 없을 수도)
    for gap in (1, 0):
        half, rest = divmod(len(t) - gap, 2)
        if rest == 0 and half >= 3 and t[:half] == t[half + gap:]:
            return t[:half].strip()

    # 앞머리가 다시 나오는 자리에서 자릅니다. 제목이 짧으면 앞머리도
    # 짧게 잡아야 합니다 — 열두 글자로 고정하면 짧은 제목이 안 잘립니다.
    head = t[: min(12, len(t) // 2)]
    if len(head) >= 3:
        again = t.find(head, 1)
        if again > 0:
            return t[:again].strip()
    return t


def stock_code(title: str) -> str | None:
    """제목 안의 종목코드. '삼성전자(005930) …' → '005930'"""
    m = re.search(r"\((\d{6})\)", title)
    return m.group(1) if m else None


def opinion(raw: str) -> str | None:
    """
    투자의견을 한 가지 말로 맞춥니다.

    증권사마다 'Buy' 'BUY' '매수' 'Strong Buy' 로 제각각입니다. 그대로
    두면 화면에서 세기도 어렵고 초보자에게는 더 헷갈립니다.
    """
    s = (raw or "").strip()
    if not s or s in ("-", "--"):
        return None
    low = s.lower().replace(" ", "")
    if any(k in low for k in ("buy", "매수", "outperform", "overweight", "strongbuy")):
        return "매수"
    if any(k in low for k in ("hold", "중립", "neutral", "marketperform", "equalweight")):
        return "중립"
    if any(k in low for k in ("sell", "매도", "underperform", "underweight", "reduce")):
        return "매도"
    return s          # 못 알아본 것은 그대로 둡니다. 버리면 모르게 됩니다.


def _won(raw: str) -> int | None:
    s = re.sub(r"[^\d]", "", raw or "")
    return int(s) if s else None


ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
IDX_RE = re.compile(r"report_idx=(\d+)")


def parse_list(html: str, report_type: str = "CO") -> list[dict]:
    """
    목록 화면에서 리포트들을 뽑습니다.

    기업 화면은 칸이 9개(적정가격·투자의견 있음), 나머지는 6개입니다.
    칸 수로 어느 쪽인지 가릅니다 — 머리글 글자를 믿으면 화면이 조금만
    바뀌어도 통째로 깨집니다.
    """
    out: list[dict] = []
    for row_html in ROW_RE.findall(html):
        cells = CELL_RE.findall(row_html)
        if len(cells) < 6:
            continue

        idx = IDX_RE.search(row_html)
        if not idx:
            continue                      # 보고서 번호가 없으면 줄이 아닙니다

        written = _text(cells[0])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", written):
            continue

        if len(cells) >= 9:               # 기업 화면
            title = clean_title(cells[1])
            target = _won(_text(cells[2]))
            op = opinion(_text(cells[3]))
            analyst = _text(cells[4])
            house = _text(cells[5])
            kind = "기업"
        else:                             # 그 밖의 화면
            kind = _text(cells[1]) or KIND_OF.get(report_type, "")
            title = clean_title(cells[2])
            target = None
            op = None
            analyst = _text(cells[3])
            house = _text(cells[4])

        out.append({
            "report_idx": int(idx.group(1)),
            "code": stock_code(title),
            "written_at": written,
            "kind": kind,
            "title": title,
            "target_price": target,
            "opinion": op,
            "analyst": analyst or None,
            "house": house or None,
        })
    return out


def last_page(html: str) -> int:
    """쪽 번호 중 가장 큰 것."""
    pages = [int(p) for p in re.findall(r"now_page=(\d+)", html)]
    return max(pages) if pages else 1
