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
import SectorPicker from "./SectorPicker";
import { eok, limitHit, num, price, signed, tone } from "@/lib/format";
import { 기준 } from "@/lib/screen-rules";

type SortKey =
  | "장기 후보" | "단기 후보"
  | "시가총액" | "많이 오른" | "많이 내린" | "1년 수익률" | "PER 낮은" | "배당 높은";

/** ★ 후보 둘을 맨 앞에 둡니다 ★
    '무엇부터 볼까' 에 답하는 것이라, 줄 세우기보다 먼저 와야 합니다. */
const SORTS: SortKey[] = [
  "장기 후보", "단기 후보",
  "시가총액", "많이 오른", "많이 내린", "1년 수익률", "PER 낮은", "배당 높은",
];

/** 후보 거르기는 '줄 세우기' 가 아니라 '걸러내기' 입니다 */
const 후보정렬 = (s: SortKey) => s === "장기 후보" || s === "단기 후보";

/** 한 번에 그리는 개수. 너무 많이 그리면 휴대폰이 버벅입니다. */
const PAGE = 30;

export default function StockList({ stocks }: { stocks: ListStock[] }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortKey>("시가총액");
  const [sector, setSector] = useState("");   // "" = 업종 안 가림
  const [kind, setKind] = useState("");       // "" | "주식" | "ETF"
  const [country, setCountry] = useState(""); // "" | "한국" | "미국"
  const [shown, setShown] = useState(PAGE);

  /** 나라로 먼저 가른 목록. 업종 목록도 여기서 뽑습니다 — 한국 업종과
      미국 업종은 분류 자체가 달라서, 섞어 놓으면 고르는 칸이 두 배로
      길어지고 무엇을 고르는지도 흐려집니다. */
  const 나라것 = useMemo(
    () =>
      country === ""
        ? stocks
        : stocks.filter((s) =>
            country === "미국" ? s.currency === "USD" : s.currency !== "USD",
          ),
    [stocks, country],
  );

  /** 고를 수 있는 업종과 그 개수. 많은 업종부터 위로. */
  const sectors = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of 나라것) if (s.sector) n.set(s.sector, (n.get(s.sector) ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ko"));
  }, [나라것]);

  /** 나라를 바꾸면 업종은 풀어야 합니다. 한국 업종을 고른 채 미국으로
      넘어가면 맞는 종목이 하나도 없어 빈 화면이 됩니다. */
  const 나라바꾸기 = (v: string) => {
    setCountry(v);
    setSector("");
    setShown(PAGE);
  };

  /** 거르기를 하나라도 걸었는가 */
  const 거른중 = sector !== "" || kind !== "" || country !== "";
  const 초기화 = () => {
    setSector("");
    setKind("");
    setCountry("");
    setShown(PAGE);
  };

  // 초성은 한 번만 계산해 둡니다 (칠 때마다 다시 만들면 느려집니다)
  const chosung = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of stocks) m.set(s.code, chosungOf(s.name));
    return m;
  }, [stocks]);

  const view = useMemo(() => {
    const query = q.trim();

    // 나라·업종·종류로 먼저 좁히고, 그다음에 찾거나 줄 세웁니다.
    const 후보 = 나라것.filter(
      (s) =>
        (sector === "" || s.sector === sector) &&
        (kind === "" || (kind === "ETF" ? s.kind === "ETF" : s.kind !== "ETF")),
    );

    if (query) {
      return 후보
        .map((s) => ({ s, sc: scoreOf(query, s.name, s.code, chosung.get(s.code), s.sector) }))
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

    // 후보는 줄 세우기가 아니라 걸러내기입니다. 조건에 맞은 것만
    // 남기고, 그 안에서 '왜 걸렸는지' 가 센 것부터 보여줍니다.
    if (sort === "장기 후보") {
      return 후보
        .filter((s) => s.pick?.long)
        .sort((a, b) => (b.pick?.roe ?? -1) - (a.pick?.roe ?? -1));
    }
    if (sort === "단기 후보") {
      return 후보
        .filter((s) => s.pick?.short)
        .sort((a, b) => (b.pick?.spike ?? -1) - (a.pick?.spike ?? -1));
    }

    switch (sort) {
      case "많이 오른":   return by((s) => s.change_pct);
      case "많이 내린":   return by((s) => s.change_pct, true);
      case "1년 수익률":  return by((s) => s.ret1y);
      // PER 이 0 이하인 것은 '계산 불가' 라 순위에서 뺍니다.
      case "PER 낮은":    return by((s) => (s.per !== null && s.per > 0 ? s.per : null), true);
      case "배당 높은":   return by((s) => (s.div_yield ? s.div_yield : null));
      default:            return by((s) => s.market_cap);
    }
  }, [나라것, q, sort, sector, kind, chosung]);

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
            placeholder="찾기 — 이름 · 코드 · 초성 · 업종"
            inputMode="search"
            enterKeyHint="search"
            autoComplete="off"
            aria-label="종목 찾기. 이름, 여섯 자리 코드, 초성, 업종 이름으로 찾을 수 있습니다."
          />
          {searching && (
            <button className="search-x" onClick={() => { setQ(""); setShown(PAGE); }}
                    aria-label="검색어 지우기">✕</button>
          )}
        </div>

        {!searching && (
          <div className="picks">
            {/* 업종은 150가지가 넘습니다. 펼쳐놓고 고르게 하면 손가락으로
                한참 굴려야 해서, 찾는 칸이 붙은 창을 띄웁니다. */}
            <SectorPicker
              sectors={sectors}
              value={sector}
              onChange={(next) => { setSector(next); setShown(PAGE); }}
            />
            <select
              className="pick"
              value={country}
              onChange={(e) => 나라바꾸기(e.target.value)}
              aria-label="나라로 좁히기"
            >
              <option value="">한국·미국 전부</option>
              <option value="한국">한국만</option>
              <option value="미국">미국만</option>
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
          : 후보정렬(sort)
            ? `조건에 맞는 ${num(view.length)}개 · ${sort}`
            : `${num(view.length)}개 종목 · ${sort} 순`}
        {!searching && 거른중 && (
          <>
            {" · "}
            <b>
              {[
                country && `${country}만`,
                sector,
                kind && (kind === "ETF" ? "ETF만" : "주식만"),
              ]
                .filter(Boolean)
                .join(" · ")}
            </b>
            {" "}
            <button className="count-x" onClick={초기화}>
              지우기
            </button>
          </>
        )}
      </p>

      {/* ★ 무엇으로 걸렀는지를 반드시 밝힙니다 ★
          기준을 숨기고 이름만 늘어놓으면 '앱이 고른 종목' 이 됩니다.
          조건을 보여줘야 보는 사람이 동의하거나 반대할 수 있습니다. */}
      {!searching && 후보정렬(sort) && (
        <div className="screen-note">
          <b>{sort === "장기 후보" ? "장기" : "단기"}</b>
          {sort === "장기 후보" ? (
            <>
              {" "}— 매출이 작년 같은 분기보다 늘고, 영업이익이 흑자이고,
              ROE <span className="n">{기준.최소ROE}%</span> 위,
              부채비율 <span className="n">{기준.최대부채비율}%</span> 아래,
              PER <span className="n">{기준.최대PER}</span> 아래인 회사.
            </>
          ) : (
            <>
              {" "}— 최근 5일 거래대금이 그 앞 20일의{" "}
              <span className="n">{기준.거래급증배수}배</span> 넘고,
              20일 평균 위에 있고, 연 변동성이{" "}
              <span className="n">{기준.최대변동성}%</span> 아래인 회사.
            </>
          )}{" "}
          둘 다 시가총액 <span className="n">{num(기준.최소시총억)}억</span> 위,
          하루 거래대금{" "}
          <span className="n">
            {sort === "장기 후보" ? 기준.장기거래대금억 : 기준.단기거래대금억}억
          </span>{" "}
          위입니다 — 팔고 싶을 때 팔려야 후보입니다.
          <span className="screen-care">
            조건에 맞았다는 뜻이지 <b>오를 종목이라는 뜻이 아닙니다.</b>{" "}
            왜 그런지는 눌러서 직접 보세요.
          </span>
        </div>
      )}

      {view.length === 0 && !searching && 후보정렬(sort) && (
        <div className="empty">
          <b>조건에 맞는 종목이 없습니다</b>
          오늘은 이 기준을 넘는 종목이 없다는 뜻입니다. 기준을 낮춰
          억지로 만들지 않습니다.
        </div>
      )}

      {view.length === 0 && !searching && 거른중 && (
        <div className="empty">
          <b>고르신 조건에 맞는 종목이 없습니다</b>
          나라·업종·종류를 함께 좁히면 남는 게 없을 수 있습니다.
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
          <br />초성으로도 됩니다. (예: ㅅㅅㅈㅈ)
          <br />업종 이름으로도 됩니다. (예: 반도체)
        </div>
      )}

      {/* 줄들을 한 덩어리로 감쌉니다. 나머지 칸(공시·리포트)이 모두
          카드라 목록만 맨바닥에 있으면 따로 노는 것처럼 보입니다. */}
      <div className="rows">
      {list.map((s) => {
        const dir = tone(s.change_pct);
        const lim = limitHit(s.change_pct, s.currency);
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
                  {/* 왜 걸렸는지를 같이 보여줍니다. 이름만 늘어놓으면
                      '앱이 고른 종목' 이 되고, 그건 이 앱이 하려던 일과
                      정반대입니다. */}
                  {sort === "장기 후보" && s.pick?.roe !== null && (
                    <>
                      <span>ROE <b className="n">{num(s.pick!.roe!, 1)}%</b></span>
                      {s.pick?.debt !== null && (
                        <span>부채 <b className="n">{num(s.pick!.debt!, 0)}%</b></span>
                      )}
                    </>
                  )}
                  {sort === "단기 후보" && s.pick?.spike !== null && (
                    <>
                      <span>거래 <b className="n">{num(s.pick!.spike!, 1)}배</b></span>
                      {s.pick?.ma20Gap !== null && (
                        <span>20일선 <b className="n">{signed(s.pick!.ma20Gap!, 1)}%</b></span>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* 오른쪽 — 얼마인가 */}
              <div className="row-r">
                <div className="row-px n">
                  {s.currency === "USD"
                    ? (price(s.close_local, "USD") || "—")
                    : (s.close === null ? "—" : num(s.close))}
                </div>
                {/* 등락률은 알약으로. 목록을 훑을 때 오르내림이 한눈에
                    들어옵니다 — 진짜 증권 앱들이 쓰는 모양입니다. */}
                <div className="row-chg">
                  {lim && (
                    <span className={`limit ${lim}`}>
                      {lim === "up" ? "상한가" : "하한가"}
                    </span>
                  )}
                  <span className={`pill n ${dir}`}>
                    {s.change_pct === null ? "—" : `${signed(s.change_pct)}%`}
                  </span>
                </div>
              </div>
            </div>

            {/* 등락 막대는 여기도, 종목 상세에도 없습니다.
                알약이 방향과 크기를 이미 말해주고, +·− 부호가 색과
                따로 방향을 알려줍니다(색 구분이 어려운 분도 읽힙니다).
                막대까지 두면 0.05% 짜리가 점 하나로 찍혀서 화면이
                지저분해집니다. 크기를 제대로 보여주는 일은 눈금이 있는
                차트가 합니다. */}
          </Link>
        );
      })}
      </div>

      {shown < view.length && (
        <button className="more" onClick={() => setShown((n) => n + PAGE)}>
          {num(view.length - shown)}개 더 보기
        </button>
      )}
    </>
  );
}
