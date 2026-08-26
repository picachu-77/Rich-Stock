/**
 * 화면이 쓰는 데이터를 가져오는 곳.
 *
 * 파이썬 화면(src/market_data.py)과 **같은 계산**을 합니다.
 * 두 화면이 다른 숫자를 보여주면 어느 쪽을 믿어야 할지 알 수 없으므로,
 * SQL 을 그대로 옮겼습니다.
 */
import { sql } from "./db";
import { NEAR_DAYS, PERIODS } from "./periods";

/**
 * 목록 화면에 필요한 것만 담은 가벼운 모양.
 *
 * 왜 나눴나요?
 *   목록은 종목 4천 개를 한꺼번에 브라우저로 보냅니다. 그래야 글자를 칠
 *   때마다 서버에 다녀오지 않고 즉시 걸러집니다. 그런데 안 쓰는 값까지
 *   같이 보내면 그 4천 배만큼 무거워집니다.
 *   실제로 처음엔 화면 하나가 1.66MB 였습니다.
 *
 *   그래서 목록이 실제로 그리거나 정렬에 쓰는 값만 남겼습니다.
 *   PBR·ROE·부채비율·영업이익률·거래량·기준일과 3·6개월·3년 수익률은
 *   목록에서 쓰지 않으므로 뺐습니다. (상세 화면에서만 씁니다)
 */
export type ListStock = {
  code: string;
  name: string;
  market: string;
  kind: string;
  close: number | null;
  change_pct: number | null;
  market_cap: number | null;
  per: number | null;
  div_yield: number | null;
  /** 1개월 수익률(%) — 정렬에만 씁니다 */
  ret1m: number | null;
  /** 1년 수익률(%) — 카드에 보여주고 정렬에도 씁니다 */
  ret1y: number | null;
};

/** 종목 하나를 자세히 볼 때 쓰는 모양. */
export type Stock = {
  code: string;
  name: string;
  market: string;
  kind: string;
  trade_date: string;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  per: number | null;
  pbr: number | null;
  div_yield: number | null;
  roe: number | null;
  debt_ratio: number | null;
  op_margin: number | null;
  /** 기간별 수익률(%). 자료가 없으면 null 입니다. */
  returns: (number | null)[];
};

/** 억원 단위로 바꿔 담아두면 화면에서 다루기 편합니다. */
const toNum = (v: unknown): number | null =>
  v === null || v === undefined ? null : Number(v);

/**
 * 전 종목의 최신 시세 + 기간별 수익률.
 *
 * 하루에 한 번만 바뀌는 자료라, 화면 쪽에서 캐시해 두고 씁니다.
 */
export async function getStocks(): Promise<ListStock[]> {
  // 목록에 필요한 기간은 1개월과 1년 두 개뿐입니다.
  const want = [
    { key: "ret1m", interval: "1 month" },
    { key: "ret1y", interval: "1 year" },
  ];
  const joins = want
    .map(
      (p, i) => `
      LEFT JOIN LATERAL (
        SELECT dp.close FROM daily_price dp
         WHERE dp.code = t.code
           AND dp.trade_date <= c.trade_date - INTERVAL '${p.interval}'
           AND dp.trade_date >= c.trade_date - INTERVAL '${p.interval}'
                                             - INTERVAL '${NEAR_DAYS} days'
         ORDER BY dp.trade_date DESC LIMIT 1
      ) AS r${i} ON TRUE`,
    )
    .join("\n");

  // ★ 종목마다 '가장 최근 시세 한 줄' 을 색인으로 바로 집어옵니다 ★
  //   최근 30일치를 통째로 꺼내 종목별 첫 줄만 남기는 방식은, 시세 표
  //   200만 줄을 전부 훑고 그중 200만 줄을 버립니다. 실측 19.4초였습니다.
  //   지금 방식은 145ms 입니다. (파이썬 쪽 src/market_data.py 와 같은 조회)
  const rows = await sql.unsafe(`
    WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price)
    SELECT t.code, t.name, t.market, t.kind,
           c.trade_date, c.close, c.change_pct, c.market_cap,
           c.per, c.div_yield,
           r0.close AS past0, r1.close AS past1
      FROM ticker t
      CROSS JOIN bound b
      JOIN LATERAL (
        SELECT p.trade_date, p.close, p.change_pct, p.market_cap, p.per, p.div_yield
          FROM daily_price p
         WHERE p.code = t.code
           AND p.trade_date >= b.last_d - INTERVAL '30 days'
         ORDER BY p.trade_date DESC
         LIMIT 1
      ) AS c ON TRUE
      ${joins}
     WHERE t.is_active
  `);

  const pct = (cur: number | null, past: number | null) =>
    cur === null || past === null || past === 0
      ? null
      : Math.round((cur / past - 1) * 10000) / 100;

  return rows.map((r: Record<string, unknown>) => {
    const close = toNum(r.close);
    const cap = toNum(r.market_cap);
    return {
      code: String(r.code),
      name: String(r.name),
      market: String(r.market),
      kind: String(r.kind),
      close,
      change_pct: toNum(r.change_pct),
      // 원 단위로 들어 있어 억원으로 바꿉니다.
      market_cap: cap === null ? null : Math.round(cap / 1e8),
      per: toNum(r.per),
      div_yield: toNum(r.div_yield),
      ret1m: pct(close, toNum(r.past0)),
      ret1y: pct(close, toNum(r.past1)),
    };
  });
}

export type PricePoint = { d: string; c: number };

/** 종목 하나의 과거 종가 (차트용). */
export async function getHistory(code: string): Promise<PricePoint[]> {
  const rows = await sql`
    SELECT trade_date, close
      FROM daily_price
     WHERE code = ${code} AND close IS NOT NULL
     ORDER BY trade_date
  `;
  return rows.map((r) => ({
    d: new Date(r.trade_date as string).toISOString().slice(0, 10),
    c: Number(r.close),
  }));
}

/**
 * 종목 하나의 자세한 정보.
 *
 * 전에는 전 종목을 불러온 뒤 그중 하나를 골랐습니다. 한 종목을 보려고
 * 4천 개를 조회하는 셈이라 낭비였습니다. 지금은 그 종목만 봅니다.
 */
export async function getStock(code: string): Promise<Stock | null> {
  const joins = PERIODS.map(
    (p, i) => `
      LEFT JOIN LATERAL (
        SELECT dp.close FROM daily_price dp
         WHERE dp.code = $1
           AND dp.trade_date <= c.trade_date - INTERVAL '${p.interval}'
           AND dp.trade_date >= c.trade_date - INTERVAL '${p.interval}'
                                             - INTERVAL '${NEAR_DAYS} days'
         ORDER BY dp.trade_date DESC LIMIT 1
      ) AS r${i} ON TRUE`,
  ).join("\n");
  const picks = PERIODS.map((_, i) => `r${i}.close AS past${i}`).join(", ");

  const rows = await sql.unsafe(
    `
    WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price)
    SELECT t.code, t.name, t.market, t.kind,
           c.trade_date, c.close, c.change_pct, c.volume, c.market_cap,
           c.per, c.pbr, c.div_yield,
           f.roe, f.debt_ratio, f.op_margin,
           ${picks}
      FROM ticker t
      CROSS JOIN bound b
      JOIN LATERAL (
        SELECT p.trade_date, p.close, p.change_pct, p.volume, p.market_cap,
               p.per, p.pbr, p.div_yield
          FROM daily_price p
         WHERE p.code = $1
           AND p.trade_date >= b.last_d - INTERVAL '30 days'
         ORDER BY p.trade_date DESC LIMIT 1
      ) AS c ON TRUE
      LEFT JOIN LATERAL (
        SELECT fi.roe, fi.debt_ratio, fi.op_margin
          FROM financial fi
         WHERE fi.code = $1
         ORDER BY fi.fiscal_year DESC, fi.fiscal_quarter DESC LIMIT 1
      ) AS f ON TRUE
      ${joins}
     WHERE t.code = $1
  `,
    [code],
  );
  if (rows.length === 0) return null;

  const r = rows[0] as Record<string, unknown>;
  const close = toNum(r.close);
  const cap = toNum(r.market_cap);
  return {
    code: String(r.code),
    name: String(r.name),
    market: String(r.market),
    kind: String(r.kind),
    trade_date: new Date(r.trade_date as string).toISOString().slice(0, 10),
    close,
    change_pct: toNum(r.change_pct),
    volume: toNum(r.volume),
    market_cap: cap === null ? null : cap / 1e8,
    per: toNum(r.per),
    pbr: toNum(r.pbr),
    div_yield: toNum(r.div_yield),
    roe: toNum(r.roe),
    debt_ratio: toNum(r.debt_ratio),
    op_margin: toNum(r.op_margin),
    returns: PERIODS.map((_, i) => {
      const past = toNum(r[`past${i}`]);
      if (close === null || past === null || past === 0) return null;
      return Math.round((close / past - 1) * 10000) / 100;
    }),
  };
}

/** 자료가 언제까지 들어와 있는지. */
export async function getLastDate(): Promise<string | null> {
  const rows = await sql`SELECT max(trade_date) AS d FROM daily_price`;
  const d = rows[0]?.d;
  return d ? new Date(d as string).toISOString().slice(0, 10) : null;
}
