/**
 * 재무 추이 — 한 시점이 아니라 방향.
 *
 * ★ 왜 필요한가 ★
 *   지금까지는 가장 최근 분기 하나만 봤습니다. 그래서 "적자입니다" 까지는
 *   말해도 "3년째 이익이 줄고 있습니다" 는 못 했습니다.
 *   초보자에게는 한 시점보다 방향이 훨씬 중요합니다. 이번 분기 ROE 8% 가
 *   좋은 것인지 나쁜 것인지는, 작년이 15% 였는지 3% 였는지에 달렸습니다.
 *
 *   자료는 이미 있었습니다 — 12분기 30,919건을 받아두고 1개만 쓰고
 *   있었습니다.
 */
import { sql } from "./db";

export type Quarter = {
  year: number;
  quarter: number;
  /** '2025년 3분기' 처럼 읽을 수 있는 이름 */
  label: string;
  roe: number | null;
  debt: number | null;
  opMargin: number | null;
};

const REPORT: Record<number, string> = {
  // 0 은 미국 종목입니다. 야후는 분기별 보고서 대신 '최근 12개월' 값
  // 하나만 주기 때문에, 있지도 않은 분기를 붙이지 않고 따로 둡니다.
  0: "최근 1년",
  1: "1분기",
  2: "반기",
  3: "3분기",
  4: "사업(연간)",
};

export async function getTrend(code: string, limit = 12): Promise<Quarter[]> {
  try {
    const rows = await sql<
      {
        fiscal_year: number;
        fiscal_quarter: number;
        roe: string | number | null;
        debt_ratio: string | number | null;
        op_margin: string | number | null;
      }[]
    >`
      SELECT fiscal_year, fiscal_quarter, roe, debt_ratio, op_margin
        FROM financial
       WHERE code = ${code}
       ORDER BY fiscal_year DESC, fiscal_quarter DESC
       LIMIT ${limit}
    `;
    const n = (v: string | number | null) =>
      v === null ? null : typeof v === "number" ? v : Number(v);
    // 오래된 것부터 보여줘야 '흐름' 으로 읽힙니다.
    return rows
      .map((r) => ({
        year: Number(r.fiscal_year),
        quarter: Number(r.fiscal_quarter),
        label: `${r.fiscal_year}년 ${REPORT[Number(r.fiscal_quarter)] ?? ""}`,
        roe: n(r.roe),
        debt: n(r.debt_ratio),
        opMargin: n(r.op_margin),
      }))
      .reverse();
  } catch {
    return [];
  }
}

/**
 * 흐름을 한 마디로.
 *
 * ★ 같은 분기끼리만 견줍니다 ★
 *   많은 회사가 계절을 탑니다. 4분기와 1분기를 나란히 놓고 "줄었다" 고
 *   하면 틀린 말이 됩니다. 작년 같은 분기와 견줘야 뜻이 있습니다.
 *
 * 세 번 이상 이어져야 '계속' 이라고 말합니다. 두 번은 그냥 오르내림입니다.
 */
export function direction(
  qs: Quarter[],
  pick: (q: Quarter) => number | null,
): "늘고 있음" | "줄고 있음" | "들쭉날쭉" | null {
  // 같은 분기끼리 묶어 해마다 어떻게 변했는지 봅니다.
  const byQuarter = new Map<number, { year: number; v: number }[]>();
  for (const q of qs) {
    const v = pick(q);
    if (v === null) continue;
    if (!byQuarter.has(q.quarter)) byQuarter.set(q.quarter, []);
    byQuarter.get(q.quarter)!.push({ year: q.year, v });
  }

  let up = 0;
  let down = 0;
  let total = 0;
  for (const series of byQuarter.values()) {
    series.sort((a, b) => a.year - b.year);
    for (let i = 1; i < series.length; i++) {
      total++;
      if (series[i].v > series[i - 1].v) up++;
      else if (series[i].v < series[i - 1].v) down++;
    }
  }

  if (total < 2) return null;
  if (up >= 2 && down === 0) return "늘고 있음";
  if (down >= 2 && up === 0) return "줄고 있음";
  return "들쭉날쭉";
}
