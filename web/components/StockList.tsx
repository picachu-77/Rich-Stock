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
  const [sector, setSector] = useState("");   // "" = 업종 안 가림
  const [kind, setKind] = useState("");       // "" | "주식" | "ETF"
  const [shown, setShown] = useState(PAGE);

  /** 고를 수 있는 업종과 그 개수. 많은 업종부터 위로. */
  const sectors = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of stocks) if (s.sector) n.set(s.sector, (n.get(s.sector) ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
  }, [stocks]);

  /** 거르기를 하나라도 걸었는가 */
  const 거른중 = sector !== "" || kind !== "";
  const 초기화 = () => { setSector(""); setKind(""); setShown(PAGE); };

  // 초성은 한 번만 계산해 둡니다 (칠 때마다 다시 만들면 느려집니다)
  const chosung = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of stocks) m.set(s.code, chosungOf(s.name));
    return m;
  }, [stocks]);

  const view = useMemo(() => {
    const query = q.trim();

    // 업종·종류로 먼저 좁히고, 그다음에 찾거나 줄 세웁니다.
    const 후보 = stocks.filter(
      (s) =>
        (sector === "" || s.sector === sector) &&
        (kind === "" || (kind === "ETF" ? s.kind === "ETF" : s.kind !== "ETF")),
    );

    if (query) {
      return 후보
        .map((s) => ({ s, sc: scoreOf(query, s.name, s.code, chosung.get(s.code)) }))
        .filter((x) => x.sc > 0)
        .sort((a, b) => b.sc - a.sc || (b.s.market_cap ?? -1) - (a.s.market_cap ?? -1))
        .map((x) => x.s);
    }

    // 값이 없는 종목은 늘 뒤로. 빈칸이 1등에 오면 이상합니다.
    const by = (get: (s: ListStock) => number | null, asc = false) =>
      [...후보].sort((a, b) => {
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
  }, [stocks, q, sort, sector, kind, chosung]);

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
          <div className="picks">
            <select
              className="pick"
              value={sector}
              onChange={(e) => { setSector(e.target.value); setShown(PAGE); }}
              aria-label="업종으로 좁히기"
            >
              <option value="">업종 전체</option>
              {sectors.map(([name, n]) => (
                <option key={name} value={name}>
                  {name} ({n.toLocaleString("ko-KR")})
                </option>
              ))}
            </select>
            <select
              className="pick"
              value={kind}
              onChange={(e) => { setKind(e.target.value); setShown(PAGE); }}
              aria-label="종류로 좁히기"
            >
              <option value="">주식·ETF 전부</option>
              <option value="주식">주식만</option>
              <option value="ETF">ETF만</option>
            </select>
          </div>
        )}

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
        {!searching && 거른중 && (
          <>
            {" · "}
            <b>{[sector, kind && (kind === "ETF" ? "ETF만" : "주식만")].filter(Boolean).join(" · ")}</b>
            {" "}
            <button className="count-x" onClick={초기화}>
              지우기
            </button>
          </>
        )}
      </p>

      {view.length === 0 && !searching && 거른중 && (
        <div className="empty">
          <b>고르신 조건에 맞는 종목이 없습니다</b>
          업종과 종류를 함께 좁히면 남는 게 없을 수 있습니다.
          <br />
          <button className="more" style={{ marginTop: 12 }} onClick={초기화}>
            조건 지우기
          </button>
        </div>
      )}

      {view.length === 0 && searching && (
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
                  {!sector && s.sector && <span>{s.sector}</span>}
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
