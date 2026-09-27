/**
 * 배당 — "얼마를, 언제 기준으로 주는가".
 *
 * ★ 왜 배당수익률 하나로는 부족한가 ★
 *   지금까지 이 앱은 배당수익률(div_yield) 숫자 하나만 보여줬습니다.
 *   그런데 배당을 보고 사는 사람이 정말 알고 싶은 것은 둘입니다.
 *     · 한 주당 얼마씩 주는가, 그게 해마다 늘고 있는가
 *     · **언제까지 사야 받는가**
 *   둘 다 없었습니다.
 *
 * ★ 언제까지 사야 받나 ★
 *   배당기준일에 주주명부에 올라 있어야 받습니다. 그런데 주식은 사고
 *   나서 내 것이 되기까지 이틀(거래일 기준)이 걸립니다. 그래서
 *   **기준일의 전전 거래일**까지 사야 합니다.
 *
 *   쉬는 날을 넘겨짚지 않습니다. 실제로 장이 섰던 날만 봅니다.
 *   기준일이 앞으로의 날이라 그 사이 거래일을 알 수 없으면 날짜를
 *   지어내지 않고 '아직 모른다' 고 합니다 — 하루 늦게 사면 못 받습니다.
 */
import { sql } from "./db";

export type Payout = {
  rcept_no: string;
  /** 분기배당 · 결산배당 … */
  kind: string | null;
  /** 보통주 1주당 배당금 (원) */
  perShare: number | null;
  yieldPct: number | null;
  /** 배당기준일 (YYYY-MM-DD) */
  recordDate: string;
  payDate: string | null;
  /** 이 날까지 사야 받습니다. 알 수 없으면 null */
  buyBy: string | null;
  /** 기준일이 아직 오지 않았는가 */
  upcoming: boolean;
};

export async function getDividends(code: string, limit = 6): Promise<Payout[]> {
  try {
    const rows = await sql<
      {
        rcept_no: string; kind: string | null;
        per_share: number | null; yield_pct: string | null;
        record_date: Date | string; pay_date: Date | string | null;
        buy_by: Date | string | null; today: Date | string;
      }[]
    >`
      SELECT v.rcept_no, v.kind, v.per_share, v.yield_pct,
             v.record_date, v.pay_date,
             current_date AS today,
             -- 기준일의 전전 거래일 = 이 날까지 사야 받습니다.
             --
             -- ★ 확실할 때만 내놓습니다 ★
             --   기준일이 우리가 가진 마지막 시세 날짜보다 뒤면, 그
             --   사이에 며칠 장이 설지 알 수 없습니다. 그래도 억지로
             --   세면 '오늘로부터 두 거래일 전' 같은 엉뚱한 날이
             --   나옵니다. 그럴 바엔 안 알려주는 편이 낫습니다 —
             --   하루 늦게 사면 배당을 못 받습니다.
             CASE WHEN v.record_date <= (SELECT max(trade_date) FROM daily_price)
                  THEN (SELECT p.trade_date
                          FROM (SELECT DISTINCT trade_date FROM daily_price
                                 WHERE trade_date < v.record_date
                                 ORDER BY trade_date DESC LIMIT 2) p
                         ORDER BY p.trade_date ASC LIMIT 1)
             END                                          AS buy_by
        FROM dividend v
       WHERE v.code = ${code}
       ORDER BY v.record_date DESC
       LIMIT ${limit}
    `;

    const iso = (v: Date | string | null) =>
      v === null ? null
        : typeof v === "string" ? v.slice(0, 10)
          : v.toISOString().slice(0, 10);

    return rows.map((r) => {
      const record = iso(r.record_date)!;
      const today = iso(r.today)!;
      const 앞날 = record > today;
      return {
        rcept_no: r.rcept_no,
        kind: r.kind,
        perShare: r.per_share === null ? null : Number(r.per_share),
        yieldPct: r.yield_pct === null ? null : Number(r.yield_pct),
        recordDate: record,
        payDate: iso(r.pay_date),
        buyBy: iso(r.buy_by),
        upcoming: 앞날,
      };
    });
  } catch (e) {
    console.error("[배당] 읽지 못했습니다:", e);
    return [];
  }
}
