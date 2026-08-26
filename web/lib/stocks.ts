/**
 * 화면이 쓰는 데이터를 가져오는 곳.
 *
 * 파이썬 화면(src/market_data.py)과 **같은 계산**을 합니다.
 * 두 화면이 다른 숫자를 보여주면 어느 쪽을 믿어야 할지 알 수 없으므로,
 * SQL 을 그대로 옮겼습니다.
 */
import { sql } from "./db";
import { NEAR_DAYS, PERIODS } from "./periods";

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
export async function getStocks(): Promise<Stock[]> {
  // 'N개월 전 종가' 를 종목마다 하나씩 붙입니다.
  //   · 그날이 휴장일이면 그 이전 거래일을 씁니다.
  //   · 다만 NEAR_DAYS 보다 더 거슬러 올라가지는 않습니다. (→ periods.ts)
  const joins = PERIODS.map(
    (p, i) => `
      LEFT JOIN LATERAL (
        SELECT dp.close
          FROM daily_price dp
         WHERE dp.code = c.code
           AND dp.trade_date <= c.trade_date - INTERVAL '${p.interval}'
           AND dp.trade_date >= c.trade_date - INTERVAL '${p.interval}'
                                             - INTERVAL '${NEAR_DAYS} days'
         ORDER BY dp.trade_date DESC
         LIMIT 1
      ) AS r${i} ON TRUE`,
  ).join("\n");

  const picks = PERIODS.map((_, i) => `r${i}.close AS past${i}`).join(", ");

  const rows = await sql.unsafe(`
    WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price),
    recent AS (
      SELECT p.* FROM daily_price p, bound b
       WHERE p.trade_date >= b.last_d - INTERVAL '30 days'
    ),
    cur AS (
      SELECT DISTINCT ON (code)
             code, trade_date, close, change_pct, volume, market_cap,
             per, pbr, div_yield
        FROM recent ORDER BY code, trade_date DESC
    )
    SELECT t.code, t.name, t.market, t.kind,
           c.trade_date, c.close, c.change_pct, c.volume, c.market_cap,
           c.per, c.pbr, c.div_yield,
           f.roe, f.debt_ratio, f.op_margin,
           ${picks}
      FROM cur c
      JOIN ticker t ON t.code = c.code
      -- 재무는 '있으면 붙이고 없으면 빈칸'. ETF 가 목록에서 사라지지 않게.
      LEFT JOIN LATERAL (
        SELECT fi.roe, fi.debt_ratio, fi.op_margin
          FROM financial fi
         WHERE fi.code = c.code
         ORDER BY fi.fiscal_year DESC, fi.fiscal_quarter DESC
         LIMIT 1
      ) AS f ON TRUE
      ${joins}
     WHERE t.is_active
  `);

  return rows.map((r: Record<string, unknown>) => {
    const close = toNum(r.close);
    const returns = PERIODS.map((_, i) => {
      const past = toNum(r[`past${i}`]);
      if (close === null || past === null || past === 0) return null;
      return Math.round((close / past - 1) * 10000) / 100;
    });
    return {
      code: String(r.code),
      name: String(r.name),
      market: String(r.market),
      kind: String(r.kind),
      trade_date: new Date(r.trade_date as string).toISOString().slice(0, 10),
      close,
      change_pct: toNum(r.change_pct),
      volume: toNum(r.volume),
      // 원 단위로 들어 있어 억원으로 바꿉니다.
      market_cap: toNum(r.market_cap) === null ? null : toNum(r.market_cap)! / 1e8,
      per: toNum(r.per),
      pbr: toNum(r.pbr),
      div_yield: toNum(r.div_yield),
      roe: toNum(r.roe),
      debt_ratio: toNum(r.debt_ratio),
      op_margin: toNum(r.op_margin),
      returns,
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

/** 종목 하나의 기본 정보. */
export async function getStock(code: string): Promise<Stock | null> {
  const all = await getStocks();
  return all.find((s) => s.code === code) ?? null;
}

/** 자료가 언제까지 들어와 있는지. */
export async function getLastDate(): Promise<string | null> {
  const rows = await sql`SELECT max(trade_date) AS d FROM daily_price`;
  const d = rows[0]?.d;
  return d ? new Date(d as string).toISOString().slice(0, 10) : null;
}
