/**
 * 후보 거르기 — 장기와 단기.
 *
 * ★ AI 가 아니라 규칙입니다 ★
 *   '시가총액 1,000억 넘고 하루 거래대금 10억 넘고 ROE 8% 위' 같은
 *   거르기는 창고가 가장 빠르고 정확합니다.
 *
 * ★ 왜 둘로 나누나 ★
 *   같은 종목이 장기로는 좋고 단기로는 들어갈 자리가 아닐 수 있고,
 *   그 반대도 됩니다. 애초에 찾는 것이 다릅니다.
 *
 *     장기 — 실적이 꾸준히 늘고, 빚이 적고, 값이 과하지 않은 회사
 *     단기 — 최근 흐름과 거래가 살아난 회사
 *
 * ★ 둘 다에 거래대금 최소선을 겁니다 ★
 *   아무리 좋아 보여도 **팔고 싶을 때 못 파는** 종목은 후보가
 *   아닙니다. 사는 것은 언제나 쉽습니다.
 *
 * ★ 이것은 '오를 종목' 이 아닙니다 ★
 *   조건에 맞았다는 사실만 말합니다. 왜 그런지, 계속될 것인지는
 *   종목 화면에서 직접 봐야 합니다.
 *
 * ★ 목록 조회(getStocks)와 따로 돕니다 ★
 *   getStocks 는 4천 종목을 145ms 에 집어오도록 맞춰둔 쿼리입니다.
 *   거기에 재무·시세 집계를 얹으면 그 성질이 깨집니다. 후보는 수십
 *   종목뿐이라 따로 뽑아 와서 붙이는 편이 훨씬 가볍습니다.
 */
import { sql } from "./db";
import { 기준 } from "./screen-rules";

export type Pick = {
  /** 어느 거르기에 걸렸나 */
  long: boolean;
  short: boolean;
  /** 장기 — 왜 걸렸는지 보여줄 값 */
  roe: number | null;
  debt: number | null;
  /** 단기 — 거래대금이 몇 배로 늘었나 */
  spike: number | null;
  /** 단기 — 20일 평균보다 몇 % 위인가 */
  ma20Gap: number | null;
};

export async function getPicks(): Promise<Map<string, Pick>> {
  const out = new Map<string, Pick>();
  try {
    const [장기, 단기] = await Promise.all([
      sql<{ code: string; roe: string | null; debt: string | null }[]>`
        WITH last AS (
          SELECT DISTINCT ON (dp.code)
                 dp.code, dp.close, dp.volume, dp.market_cap, dp.per,
                 (dp.volume::numeric * dp.close) / 100000000 AS value_eok
            FROM daily_price dp
           WHERE dp.trade_date >= (SELECT max(trade_date) FROM daily_price) - 7
           ORDER BY dp.code, dp.trade_date DESC
        ), latest AS (
          SELECT DISTINCT ON (code) code, fiscal_year, fiscal_quarter,
                 revenue, operating_profit, roe, debt_ratio
            FROM financial
           ORDER BY code, fiscal_year DESC, fiscal_quarter DESC
        )
        SELECT t.code, f.roe, f.debt_ratio AS debt
          FROM ticker t
          JOIN last l   ON l.code = t.code
          JOIN latest f ON f.code = t.code
          -- 작년 같은 분기. 계절을 타는 회사가 많아 앞 분기와 견주면
          -- 틀린 말이 됩니다.
          JOIN financial p ON p.code = t.code
                          AND p.fiscal_year = f.fiscal_year - 1
                          AND p.fiscal_quarter = f.fiscal_quarter
         WHERE t.is_active AND t.kind <> 'ETF' AND t.currency = 'KRW'
           AND l.market_cap >= ${기준.최소시총억}
           AND l.value_eok  >= ${기준.장기거래대금억}
           AND f.operating_profit > 0
           AND f.revenue > p.revenue
           AND f.roe        >= ${기준.최소ROE}
           AND f.debt_ratio <= ${기준.최대부채비율}
           AND (l.per IS NULL OR (l.per > 0 AND l.per <= ${기준.최대PER}))
      `,
      sql<{ code: string; spike: string | null; gap: string | null }[]>`
        WITH last AS (
          SELECT DISTINCT ON (dp.code)
                 dp.code, dp.close, dp.volume, dp.market_cap,
                 (dp.volume::numeric * dp.close) / 100000000 AS value_eok
            FROM daily_price dp
           WHERE dp.trade_date >= (SELECT max(trade_date) FROM daily_price) - 7
           ORDER BY dp.code, dp.trade_date DESC
        ), flow AS (
          SELECT code,
                 avg(close) FILTER (WHERE rn <= 20) AS ma20,
                 avg(volume::numeric * close) FILTER (WHERE rn <= 5) AS v5,
                 avg(volume::numeric * close) FILTER (WHERE rn BETWEEN 6 AND 25) AS v20,
                 stddev_pop(ret) FILTER (WHERE rn <= 60) * sqrt(252) * 100 AS vol
            FROM (
              SELECT code, close, volume,
                     row_number() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn,
                     close / NULLIF(lag(close) OVER (PARTITION BY code
                                     ORDER BY trade_date), 0) - 1 AS ret
                FROM daily_price
               WHERE trade_date >= (SELECT max(trade_date) FROM daily_price) - 130
                 AND close IS NOT NULL
            ) x
           GROUP BY code
        )
        SELECT t.code,
               round((h.v5 / NULLIF(h.v20, 0))::numeric, 2)        AS spike,
               round((l.close / h.ma20 - 1)::numeric * 100, 1)      AS gap
          FROM ticker t
          JOIN last l ON l.code = t.code
          JOIN flow h ON h.code = t.code
         WHERE t.is_active AND t.kind <> 'ETF' AND t.currency = 'KRW'
           AND l.market_cap >= ${기준.최소시총억}
           AND l.value_eok  >= ${기준.단기거래대금억}
           AND h.ma20 IS NOT NULL
           AND l.close > h.ma20                       -- 20일 평균 위
           AND h.v20 > 0
           AND h.v5 >= h.v20 * ${기준.거래급증배수}    -- 거래가 늘었다
           -- 많이 흔들리는 종목이 '기회' 처럼 보이지만, 올라갈 폭이 큰
           -- 만큼 내려갈 폭도 큽니다. 초보자가 가장 크게 다치는 자리라
           -- 아예 후보에서 뺍니다.
           AND h.vol <= ${기준.최대변동성}
      `,
    ]);

    const 넣기 = (code: string) =>
      out.get(code) ??
      (out.set(code, {
        long: false, short: false, roe: null, debt: null,
        spike: null, ma20Gap: null,
      }),
      out.get(code)!);

    for (const r of 장기) {
      const p = 넣기(r.code);
      p.long = true;
      p.roe = r.roe === null ? null : Number(r.roe);
      p.debt = r.debt === null ? null : Number(r.debt);
    }
    for (const r of 단기) {
      const p = 넣기(r.code);
      p.short = true;
      p.spike = r.spike === null ? null : Number(r.spike);
      p.ma20Gap = r.gap === null ? null : Number(r.gap);
    }
    return out;
  } catch (e) {
    // 후보를 못 뽑아도 목록 자체는 열려야 합니다.
    console.error("[후보] 거르지 못했습니다:", e);
    return out;
  }
}
