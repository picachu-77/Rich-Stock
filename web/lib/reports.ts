/**
 * 증권사 리포트 — 밖에서 보는 사람들은 어떻게 보는가.
 *
 * 공시가 '회사가 스스로 신고한 것' 이라면 리포트는 그 반대편입니다.
 * 화면에 없던 유일한 것이 목표주가였습니다.
 *
 * ★ 숫자 하나만 크게 띄우지 않습니다 ★
 *   증권사 의견은 거의 다 '매수' 입니다. 실제로 세어보니 2주 동안
 *   매수 62건, 중립 2건, 매도 0건이었습니다. 목표주가만 크게 보여주면
 *   초보자는 '여기까지 오른다' 로 읽습니다. 그래서 늘 함께 보여줍니다 —
 *   몇 곳이 봤는지, 가장 낮게 본 곳은 얼마인지, 의견이 어떻게 갈렸는지.
 */
import { sql } from "./db";

export type Report = {
  id: number;
  code: string | null;
  name: string | null;
  writtenAt: string;
  kind: string;
  title: string;
  targetPrice: number | null;
  opinion: string | null;
  analyst: string | null;
  house: string | null;
  /** 원문을 읽으러 가는 곳. 우리가 퍼 나르지 않습니다. */
  url: string;
};

const LINK = (id: number) =>
  `http://consensus.hankyung.com/analysis/downpdf?report_idx=${id}`;

type Row = {
  report_idx: string | number;
  code: string | null;
  name: string | null;
  written_at: string | Date;
  kind: string;
  title: string;
  target_price: string | number | null;
  opinion: string | null;
  analyst: string | null;
  house: string | null;
};

const toReport = (r: Row): Report => ({
  id: Number(r.report_idx),
  code: r.code,
  name: r.name,
  writtenAt: new Date(r.written_at as string).toISOString().slice(0, 10),
  kind: r.kind,
  title: r.title,
  targetPrice: r.target_price === null ? null : Number(r.target_price),
  opinion: r.opinion,
  analyst: r.analyst,
  house: r.house,
  url: LINK(Number(r.report_idx)),
});

/** 최근 리포트 (첫 화면·리포트 탭). */
export async function getRecentReports(limit = 20, kind?: string): Promise<Report[]> {
  try {
    const rows = kind
      ? await sql<Row[]>`
          SELECT r.report_idx, r.code, t.name, r.written_at, r.kind, r.title,
                 r.target_price, r.opinion, r.analyst, r.house
            FROM report r
            LEFT JOIN ticker t ON t.code = r.code
           WHERE r.kind = ${kind}
           ORDER BY r.written_at DESC, r.report_idx DESC
           LIMIT ${limit}`
      : await sql<Row[]>`
          SELECT r.report_idx, r.code, t.name, r.written_at, r.kind, r.title,
                 r.target_price, r.opinion, r.analyst, r.house
            FROM report r
            LEFT JOIN ticker t ON t.code = r.code
           ORDER BY r.written_at DESC, r.report_idx DESC
           LIMIT ${limit}`;
    return rows.map(toReport);
  } catch (e) {
    // 리포트 표가 아직 없을 수 있습니다. 이것 때문에 화면이 안 열리면
    // 손해가 더 큽니다. 다만 조용히 넘기지는 않습니다 — 실제로
    // 조회 한 줄이 틀려서 칸 하나가 통째로 안 나온 적이 있는데,
    // 기록이 없으면 '자료가 없나 보다' 로 넘어가게 됩니다.
    console.error("[리포트] 최근 목록을 읽지 못했습니다:", e);
    return [];
  }
}

/** 종목 하나에 달린 리포트. */
export async function getStockReports(code: string, limit = 8): Promise<Report[]> {
  try {
    const rows = await sql<Row[]>`
      SELECT r.report_idx, r.code, t.name, r.written_at, r.kind, r.title,
             r.target_price, r.opinion, r.analyst, r.house
        FROM report r
        LEFT JOIN ticker t ON t.code = r.code
       WHERE r.code = ${code}
       ORDER BY r.written_at DESC, r.report_idx DESC
       LIMIT ${limit}`;
    return rows.map(toReport);
  } catch (e) {
    console.error("[리포트] 종목 리포트를 읽지 못했습니다:", e);
    return [];
  }
}

export type Target = {
  /** 목표주가를 낸 증권사 수 */
  count: number;
  avg: number;
  low: number;
  high: number;
  /** 의견을 낸 리포트 수 (목표주가 없는 것도 포함) */
  opinions: number;
  buy: number;
  hold: number;
  sell: number;
  /** 가장 최근 리포트 날짜 */
  last: string;
};

/**
 * 종목 하나의 목표주가를 모읍니다. 최근 6개월치만 봅니다 —
 * 1년 전 목표주가는 지금 이야기가 아닙니다.
 */
export async function getTarget(code: string): Promise<Target | null> {
  try {
    const rows = await sql<
      {
        n: string; avg: string | null; low: string | null; high: string | null;
        opinions: string; buy: string; hold: string; sell: string; last: string | Date;
      }[]
    >`
      SELECT count(*) FILTER (WHERE target_price IS NOT NULL)        AS n,
             avg(target_price)                                        AS avg,
             min(target_price)                                        AS low,
             max(target_price)                                        AS high,
             count(*) FILTER (WHERE opinion IN ('매수','중립','매도')) AS opinions,
             count(*) FILTER (WHERE opinion = '매수')                  AS buy,
             count(*) FILTER (WHERE opinion = '중립')                  AS hold,
             count(*) FILTER (WHERE opinion = '매도')                  AS sell,
             max(written_at)                                          AS last
        FROM report
       WHERE code = ${code}
         AND written_at >= current_date - 180`;
    const r = rows[0];
    if (!r || Number(r.n) === 0) return null;
    return {
      count: Number(r.n),
      avg: Math.round(Number(r.avg)),
      low: Number(r.low),
      high: Number(r.high),
      opinions: Number(r.opinions),
      buy: Number(r.buy),
      hold: Number(r.hold),
      sell: Number(r.sell),
      last: new Date(r.last as string).toISOString().slice(0, 10),
    };
  } catch (e) {
    console.error("[리포트] 목표주가를 모으지 못했습니다:", e);
    return null;
  }
}

/**
 * 시장 전체의 의견 쏠림. '매도가 몇 건인지' 를 보여주려고 셉니다.
 * 이 한 줄이 목표주가를 읽는 눈을 바꿉니다.
 */
export async function getOpinionMix(days = 90): Promise<
  { buy: number; hold: number; sell: number; total: number } | null
> {
  try {
    const rows = await sql<
      { buy: string; hold: string; sell: string; total: string }[]
    >`
      SELECT count(*) FILTER (WHERE opinion = '매수') AS buy,
             count(*) FILTER (WHERE opinion = '중립') AS hold,
             count(*) FILTER (WHERE opinion = '매도') AS sell,
             count(*)                                 AS total
        FROM report
       WHERE kind = '기업' AND written_at >= current_date - ${days}::int`;
    const r = rows[0];
    if (!r || Number(r.total) === 0) return null;
    return {
      buy: Number(r.buy), hold: Number(r.hold),
      sell: Number(r.sell), total: Number(r.total),
    };
  } catch (e) {
    console.error("[리포트] 의견 쏠림을 세지 못했습니다:", e);
    return null;
  }
}
