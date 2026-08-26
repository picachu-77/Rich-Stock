"use client";

/**
 * 종목 목록 — 찾고, 줄 세우고, 눌러서 들어가는 화면.
 *
 * 왜 브라우저 쪽에서 거르나요?
 *   전 종목이라야 4,000개 남짓입니다. 한 번 받아두고 브라우저에서 거르면
 *   글자를 칠 때마다 결과가 **기다림 없이** 바뀝니다. Streamlit 은 글자
 *   하나 칠 때마다 서버에 다녀와야 해서 느렸습니다.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Stock } from "@/lib/stocks";
import { chosungOf, scoreOf } from "@/lib/search";
import { eok, num, signed, tone, won } from "@/lib/format";

type SortKey =
  | "시가총액"
  | "등락률"
  | "수익률 1개월"
  | "수익률 1년"
  | "PER 낮은 순"
  | "배당 높은 순";

const SORTS: SortKey[] = [
  "시가총액",
  "등락률",
  "수익률 1개월",
  "수익률 1년",
  "PER 낮은 순",
  "배당 높은 순",
];

/** 한 번에 그리는 개수. 너무 많이 그리면 휴대폰이 버벅입니다. */
const PAGE = 40;

export default function StockList({ stocks }: { stocks: Stock[] }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("시가총액");
  const [shown, setShown] = useState(PAGE);

  // 초성은 한 번만 계산해 두고 씁니다 (칠 때마다 다시 만들면 느려집니다)
  const chosung = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of stocks) m.set(s.code, chosungOf(s.name));
    return m;
  }, [stocks]);

  const view = useMemo(() => {
    const query = q.trim();
    let list = stocks;

    if (query) {
      list = stocks
        .map((s) => ({ s, sc: scoreOf(query, s.name, s.code, chosung.get(s.code)) }))
        .filter((x) => x.sc > 0)
        .sort(
          (a, b) =>
            b.sc - a.sc || (b.s.market_cap ?? -1) - (a.s.market_cap ?? -1),
        )
        .map((x) => x.s);
      return list;
    }

    // 값이 없는 종목은 늘 뒤로 보냅니다. 빈칸이 1등에 오면 이상합니다.
    const by = (get: (s: Stock) => number | null, asc = false) =>
      [...list].sort((a, b) => {
        const x = get(a);
        const y = get(b);
        if (x === null && y === null) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        return asc ? x - y : y - x;
      });

    switch (sort) {
      case "등락률":
        return by((s) => s.change_pct);
      case "수익률 1개월":
        return by((s) => s.returns[0]);
      case "수익률 1년":
        return by((s) => s.returns[3]);
      case "PER 낮은 순":
        // PER 이 0 이하인 것은 '계산 불가' 라 순위에서 뺍니다.
        return by((s) => (s.per !== null && s.per > 0 ? s.per : null), true);
      case "배당 높은 순":
        return by((s) => (s.div_yield ? s.div_yield : null));
      default:
        return by((s) => s.market_cap);
    }
  }, [stocks, q, sort, chosung]);

  const list = view.slice(0, shown);

  return (
    <>
      <input
        className="search"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setShown(PAGE);
        }}
        placeholder="종목 찾기 — 삼성전자 · 005930 · ㅅㅅㅈㅈ"
        inputMode="search"
        enterKeyHint="search"
        autoComplete="off"
      />

      {!q.trim() && (
        <div className="pills" role="group" aria-label="정렬 기준">
          {SORTS.map((s) => (
            <button
              key={s}
              className="pill"
              aria-pressed={sort === s}
              onClick={() => {
                setSort(s);
                setShown(PAGE);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div style={{ margin: "10px 0 8px", fontSize: ".84rem", color: "#667085" }}>
        {q.trim()
          ? `'${q.trim()}' 로 ${num(view.length)}개를 찾았습니다`
          : `${num(view.length)}개 종목 · ${sort} 순`}
      </div>

      {view.length === 0 && (
        <div className="empty">
          찾은 종목이 없습니다.
          <br />
          이름 일부나 6자리 코드, 초성으로도 찾을 수 있습니다.
        </div>
      )}

      {list.map((s) => (
        <Link key={s.code} href={`/stock/${s.code}`} className="card">
          <div className="card-top">
            <span className="card-name">{s.name}</span>
            <span className="card-code tnum">{s.code}</span>
            <span className="card-tag">{s.kind === "ETF" ? "ETF" : s.market}</span>
          </div>

          <div className="card-mid">
            <span className="card-price tnum">{won(s.close)}</span>
            <span className={`card-chg tnum ${tone(s.change_pct)}`}>
              {signed(s.change_pct)}
              {s.change_pct !== null ? "%" : ""}
            </span>
          </div>

          <div className="card-sub tnum">
            {s.market_cap !== null && <span>시총 <b>{eok(s.market_cap)}</b></span>}
            {s.returns[3] !== null && (
              <span>
                1년 <b className={tone(s.returns[3])}>{signed(s.returns[3])}%</b>
              </span>
            )}
            {s.per !== null && s.per > 0 && <span>PER <b>{num(s.per, 2)}</b></span>}
            {s.div_yield ? <span>배당 <b>{num(s.div_yield, 2)}%</b></span> : null}
          </div>
        </Link>
      ))}

      {shown < view.length && (
        <button
          className="pill"
          style={{ width: "100%", justifyContent: "center", minHeight: 48, marginTop: 4 }}
          onClick={() => setShown((n) => n + PAGE)}
        >
          {num(view.length - shown)}개 더 보기
        </button>
      )}
    </>
  );
}
