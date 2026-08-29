/**
 * 지수와 환율 — '오늘 시장 전체는 어땠나'.
 *
 * ★ 왜 필요한가 ★
 *   종목 하나가 3% 빠진 날, 초보자는 그것을 회사의 문제로 읽습니다.
 *   그런데 그날 시장 전체가 3% 빠졌다면 이 회사는 아무 일도 없었던
 *   것입니다. 반대로 시장이 2% 오른 날 혼자 3% 빠졌다면 그것은
 *   진짜 신호입니다. 기준선이 없으면 이 구별을 할 수 없습니다.
 *
 *   환율도 같이 둡니다. 미국 종목 값을 원으로 바꿀 때 쓰는 값이라,
 *   보는 사람도 알아야 합니다.
 */
import { sql } from "./db";

export type MarketPoint = {
  symbol: string;
  /** 사람이 읽는 이름 (코스피, 나스닥, 원달러 …) */
  name: string;
  close: number | null;
  change_pct: number | null;
  /** 환율인가 — 환율은 오르는 것이 좋은 일도 나쁜 일도 아니라 색을 안 씁니다 */
  isFx: boolean;
};

/** 화면에 보여줄 순서. 한국 것을 먼저 봅니다. */
const SHOW: [string, string][] = [
  ["^KS11", "코스피"],
  ["^KQ11", "코스닥"],
  ["^IXIC", "나스닥"],
  ["^GSPC", "S&P 500"],
  ["KRW=X", "원달러"],
];

export async function getIndexes(): Promise<MarketPoint[]> {
  try {
    const rows = await sql<
      { symbol: string; close: string | null; change_pct: string | null }[]
    >`
      SELECT DISTINCT ON (symbol) symbol, close, change_pct
        FROM market_index
       WHERE trade_date >= (SELECT max(trade_date) FROM market_index) - INTERVAL '7 days'
       ORDER BY symbol, trade_date DESC
    `;
    const got = new Map(rows.map((r) => [r.symbol, r]));
    return SHOW.map(([symbol, name]) => {
      const r = got.get(symbol);
      return {
        symbol,
        name,
        close: r?.close == null ? null : Number(r.close),
        change_pct: r?.change_pct == null ? null : Number(r.change_pct),
        isFx: symbol.endsWith("=X"),
      };
    }).filter((p) => p.close !== null);
  } catch {
    // 지수 표가 아직 없거나 창고가 잠깐 안 될 때. 이것 때문에 첫 화면이
    // 통째로 안 열리면 손해가 더 큽니다.
    return [];
  }
}
