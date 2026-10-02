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
  /** 장기 의견 — 관심 / 보류 / 제외 */
  verdictLong: string | null;
  /** 단기 의견 — 관심 / 보류 / 제외 */
  verdictShort: string | null;
  reports: Partial<Record<DeskName, string>>;
  models: string | null;
};

/** 리포트 목록에 올릴 한 줄 */
export type Pick = {
  code: string;
  name: string;
  sector: string | null;
  close: number | null;
  changePct: number | null;
  createdAt: string;
  daysAgo: number;
  verdictLong: string | null;
  verdictShort: string | null;
  /** 운용부 보고서에서 뽑은 '한 줄 이유' */
  reasonLong: string | null;
  reasonShort: string | null;
};

export async function getDeskReport(code: string): Promise<DeskReport | null> {
  try {
    const rows = await sql<
      {
        created_at: Date | string;
        days_ago: number | string;
        verdict_long: string | null;
        verdict_short: string | null;
        reports: Record<string, string>;
        models: string | null;
      }[]
    >`
      SELECT created_at,
             (current_date - created_at::date) AS days_ago,
             verdict_long, verdict_short, reports, models
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
      verdictLong: r.verdict_long,
      verdictShort: r.verdict_short,
      reports: (r.reports ?? {}) as Partial<Record<DeskName, string>>,
      models: r.models,
    };
  } catch (e) {
    console.error("[부서] 보고서를 읽지 못했습니다:", e);
    return null;
  }
}


/**
 * 운용부 글에서 '## 장기' / '## 단기' 문단의 한 줄 이유만 꺼냅니다.
 *
 * 목록에서는 보고서를 통째로 보여줄 수 없습니다. 그렇다고 의견만
 * (관심/보류) 보여주면 왜 그렇게 봤는지를 모른 채 고르게 됩니다.
 */
function 한줄이유(글: string | undefined, 머리: "장기" | "단기"): string | null {
  if (!글) return null;
  const 조각 = new RegExp(`##\\s*${머리}\\s*([\\s\\S]*?)(?=\\n##|$)`).exec(글);
  if (!조각) return null;
  const m = /한 줄 이유(.+)/.exec(조각[1]);
  if (!m) return null;
  // '**한 줄 이유** — 적자에서…' 처럼 굵게 표시와 줄표가 섞여 옵니다.
  // 한 번에 떼려다 순서가 어긋나 '— 적자에서…' 가 그대로 남았습니다.
  // 꾸밈을 먼저 지우고, 그다음 앞머리 기호를 떱니다.
  return m[1]
    .replace(/\*/g, "")
    .replace(/^[\s—\-–:·]+/, "")
    .trim() || null;
}

/**
 * 가장 최근 보고서들을 모읍니다 — 종목마다 한 건씩.
 *
 * ★ 최근 것만 봅니다 ★
 *   한 달 전 보고서를 오늘 고른 종목인 것처럼 늘어놓으면 안 됩니다.
 */
export async function getPicks(days = 30, limit = 40): Promise<Pick[]> {
  try {
    const rows = await sql<
      {
        code: string; name: string; sector_name: string | null;
        close: string | null; change_pct: string | null;
        created_at: Date | string; days_ago: number | string;
        verdict_long: string | null; verdict_short: string | null;
        reports: Record<string, string>;
      }[]
    >`
      SELECT DISTINCT ON (d.code)
             d.code, t.name, t.sector_name,
             p.close, p.change_pct,
             d.created_at,
             (current_date - d.created_at::date) AS days_ago,
             d.verdict_long, d.verdict_short, d.reports
        FROM desk_report d
        JOIN ticker t ON t.code = d.code
        LEFT JOIN LATERAL (
          SELECT close, change_pct FROM daily_price
           WHERE code = d.code ORDER BY trade_date DESC LIMIT 1
        ) p ON TRUE
       WHERE d.created_at >= current_date - ${days}::int
       ORDER BY d.code, d.created_at DESC
       LIMIT ${limit}
    `;
    return rows.map((r) => {
      const iso =
        typeof r.created_at === "string"
          ? r.created_at.slice(0, 10)
          : r.created_at.toISOString().slice(0, 10);
      const reports = r.reports ?? {};
      return {
        code: r.code,
        name: r.name,
        sector: r.sector_name,
        close: r.close === null ? null : Number(r.close),
        changePct: r.change_pct === null ? null : Number(r.change_pct),
        createdAt: iso,
        daysAgo: Number(r.days_ago),
        verdictLong: r.verdict_long,
        verdictShort: r.verdict_short,
        reasonLong: 한줄이유(reports["운용부"], "장기"),
        reasonShort: 한줄이유(reports["운용부"], "단기"),
      };
    });
  } catch (e) {
    console.error("[부서] 추린 종목을 읽지 못했습니다:", e);
    return [];
  }
}
