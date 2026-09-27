/**
 * 부서 보고서 읽기.
 *
 * ★ 언제 쓴 것인지를 꼭 같이 보여줍니다 ★
 *   시세도 실적도 계속 바뀝니다. 한 달 전에 쓴 보고서를 오늘 것처럼
 *   보여주면, 그 사이에 실적이 나왔는데도 옛날 이야기를 읽게 됩니다.
 */
import { sql } from "./db";

export const DESKS = [
  "기술적분석부",
  "펀더멘탈부",
  "마켓부",
  "리스크관리부",
  "운용부",
] as const;

export type DeskName = (typeof DESKS)[number];

export type DeskReport = {
  createdAt: string;
  /** 며칠 전에 쓴 것인가 */
  daysAgo: number;
  /** 관심 / 보류 / 제외 */
  verdict: string | null;
  reports: Partial<Record<DeskName, string>>;
  models: string | null;
};

export async function getDeskReport(code: string): Promise<DeskReport | null> {
  try {
    const rows = await sql<
      {
        created_at: Date | string;
        days_ago: number | string;
        verdict: string | null;
        reports: Record<string, string>;
        models: string | null;
      }[]
    >`
      SELECT created_at,
             (current_date - created_at::date) AS days_ago,
             verdict, reports, models
        FROM desk_report
       WHERE code = ${code}
       ORDER BY created_at DESC
       LIMIT 1
    `;
    const r = rows[0];
    if (!r) return null;
    const iso =
      typeof r.created_at === "string"
        ? r.created_at.slice(0, 10)
        : r.created_at.toISOString().slice(0, 10);
    return {
      createdAt: iso,
      daysAgo: Number(r.days_ago),
      verdict: r.verdict,
      reports: (r.reports ?? {}) as Partial<Record<DeskName, string>>,
      models: r.models,
    };
  } catch (e) {
    console.error("[부서] 보고서를 읽지 못했습니다:", e);
    return null;
  }
}
