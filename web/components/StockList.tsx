"use client";

/**
 * 종목 목록 — 찾고, 줄 세우고, 눌러서 들어가는 화면.
 *
 * 브라우저에서 거르는 이유
 *   전 종목이라야 4천 개 남짓입니다. 한 번 받아두고 브라우저에서 거르면
 *   글자를 칠 때마다 결과가 **기다림 없이** 바뀝니다.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import type { ListStock } from "@/lib/stocks";
import { chosungOf, scoreOf } from "@/lib/search";
import { eok, limitHit, num, railWidth, signed, tone } from "@/lib/format";

type SortKey = "시가총액" | "많이 오른" | "많이 내린" | "1년 수익률" | "PER 낮은" | "배당 높은";

const SORTS: SortKey[] = ["시가총액", "많이 오른", "많이 내린", "1년 수익률", "PER 낮은", "배당 높은"];

/** 한 번에 그리는 개수. 너무 많이 그리면 휴대폰이 버벅입니다. */
const PAGE = 30;

export default function StockList({ stocks }: { stocks: ListStock[] }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("시가총액");
  const [shown, setShown] = useState(PAGE);

  // 초성은 한 번만 계산해 둡니다 (칠 때마다 다시 만들면 느려집니다)
  const chosung = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of stocks) m.set(s.code, chosungOf(s.name));
    return m;
  }, [stocks]);

  const view = useMemo(() => {
    const query = q.trim();

    if (query) {
      return stocks
        .map((s) => ({ s, sc: scoreOf(query, s.name, s.code, chosung.get(s.code)) }))
        .filter((x) => x.sc > 0)
        .sort((a, b) => b.sc - a.sc || (b.s.market_cap ?? -1) - (a.s.market_cap ?? -1))
        .map((x) => x.s);
    }

    // 값이 없는 종목은 늘 뒤로. 빈칸이 1등에 오면 이상합니다.
    const by = (get: (s: ListStock) => number | null, asc = false) =>
      [...stocks].sort((a, b) => {
        const x = get(a);
        const y = get(b);
        if (x === null && y === null) return 0;
        if (x === null) return 1;
        if (y === null) return -1;
        return asc ? x - y : y - x;
      });

    switch (sort) {
      case "많이 오른":   return by((s) => s.change_pct);
      case "많이 내린":   return by((s) => s.change_pct, true);
      case "1년 수익률":  return by((s) => s.ret1y);
      // PER 이 0 이하인 것은 '계산 불가' 라 순위에서 뺍니다.
      case "PER 낮은":    return by((s) => (s.per !== null && s.per > 0 ? s.per : null), true);
      case "배당 높은":   return by((s) => (s.div_yield ? s.div_yield : null));
      default:            return by((s) => s.market_cap);
    }
  }, [stocks, q, sort, chosung]);

  const list = view.slice(0, shown);
  const searching = q.trim().length > 0;

  return (
    <>
      <div className="sticky">
        <div className="search-box">
          <input
            className="search"
            value={q}
            onChange={(e) => { setQ(e.target.value); setShown(PAGE); }}
            placeholder="종목 찾기 — 이름 · 코드 · 초성"
            inputMode="search"
            enterKeyHint="search"
            autoComplete="off"
            aria-label="종목 찾기. 이름, 여섯 자리 코드, 초성으로 찾을 수 있습니다."
          />
          {searching && (
            <button className="search-x" onClick={() => { setQ(""); setShown(PAGE); }}
                    aria-label="검색어 지우기">✕</button>
          )}
        </div>

        {!searching && (
          <div className="chips" role="group" aria-label="정렬 기준">
            {SORTS.map((s) => (
              <button key={s} className="chip" aria-pressed={sort === s}
                      onClick={() => { setSort(s); setShown(PAGE); }}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="count" role="status" aria-live="polite">
        {searching
          ? `'${q.trim()}' 로 ${num(view.length)}개를 찾았습니다`
          : `${num(view.length)}개 종목 · ${sort} 순`}
      </p>

      {view.length === 0 && (
        <div className="empty">
          <b>찾은 종목이 없습니다</b>
          이름 일부나 여섯 자리 코드로 찾아보세요.
          <br />초성으로도 찾을 수 있습니다. (예: ㅅㅅㅈㅈ)
        </div>
      )}

      {list.map((s) => {
        const dir = tone(s.change_pct);
        const lim = limitHit(s.change_pct);
        return (
          <Link key={s.code} href={`/stock/${s.code}`} className="row">
            <div className="row-grid">
              {/* 왼쪽 — 무슨 종목인가 */}
              <div className="row-l">
                <div className="row-line">
                  <span className="row-name">{s.name}</span>
                  <span className="row-code n">{s.code}</span>
                  {s.kind === "ETF" && <span className="tag">ETF</span>}
                </div>
                <div className="row-sub">
                  {s.market_cap !== null && <span>시총 <b className="n">{eok(s.market_cap)}</b></span>}
                  {s.ret1y !== null && (
                    <span>1년 <b className={`n ${tone(s.ret1y)}`}>{signed(s.ret1y, 1)}%</b></span>
                  )}
                  {/* 지금 무엇으로 줄 세웠는지에 맞는 값만 함께 보여줍니다.
                      네 가지를 늘 다 보여주면 좁은 화면에서 두 줄로 감깁니다. */}
                  {sort === "PER 낮은" && s.per !== null && s.per > 0 && (
                    <span>PER <b className="n">{num(s.per, 2)}</b></span>
                  )}
                  {sort === "배당 높은" && !!s.div_yield && (
                    <span>배당 <b className="n">{num(s.div_yield, 2)}%</b></span>
                  )}
                </div>
              </div>

              {/* 오른쪽 — 얼마인가 */}
              <div className="row-r">
                <div className="row-px n">{s.close === null ? "—" : num(s.close)}</div>
                <div className={`row-chg n ${dir}`}>
                  {signed(s.change_pct)}{s.change_pct !== null && "%"}
                </div>
              </div>
            </div>

            {/* 가운데가 0. 오르면 오른쪽, 내리면 왼쪽으로 자랍니다.
                방향을 색과 위치 두 가지로 보여주므로, 색 구분이 어려운
                분도 어느 쪽인지 알 수 있습니다. */}
            <div className="rail" aria-hidden="true">
              {s.change_pct !== null && Math.abs(s.change_pct) >= 0.005 && (
                <i className={dir} style={{ width: `${railWidth(s.change_pct)}%` }} />
              )}
              {lim && <span className={`limit ${lim}`}>{lim === "up" ? "상한가" : "하한가"}</span>}
            </div>
          </Link>
        );
      })}

      {shown < view.length && (
        <button className="more" onClick={() => setShown((n) => n + PAGE)}>
          {num(view.length - shown)}개 더 보기
        </button>
      )}
    </>
  );
}
