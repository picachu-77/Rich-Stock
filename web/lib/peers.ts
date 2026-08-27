/**
 * 같은 업종과 견주기.
 *
 * ★ 왜 필요한가 ★
 *   숫자 설명에서 "같은 업종끼리 견줘야 뜻이 있습니다" 라고 써놓고
 *   정작 견줄 방법을 안 드렸습니다. 그러면 초보자는 더 막막해집니다.
 *   "PER 8.4 — 낮은 축입니다" 는 두루뭉술한 말이지만
 *   "같은 업종 32곳 중 5번째로 낮습니다" 는 근거가 있는 말입니다.
 *
 * ★ 자세한 업종에 회사가 적으면 큰 묶음으로 물러섭니다 ★
 *   '반도체(개별소자)' 에 3곳뿐이면 '3곳 중 1위' 라는 말은 뜻이 없습니다.
 *   그럴 때는 '전자·통신장비' 같은 큰 묶음으로 다시 셉니다.
 *   (파이썬 쪽 우량주 찾기와 같은 방식입니다)
 */
import { sql } from "./db";
import { sectorGroup, sectorName, UNKNOWN } from "./ksic";

/** 이 인원보다 적으면 큰 묶음으로 물러섭니다. */
const MIN_PEERS = 5;

export type Rank = {
  /** 견준 무리의 이름 */
  group: string;
  /** 그 무리의 회사 수 */
  count: number;
  /** 이 종목이 몇 번째인지 (1 부터) */
  rank: number;
  /** 무리의 한가운데 값 */
  median: number;
  /** 낮은 것이 좋은 지표인지 (PER·PBR·부채비율) */
  lowerIsBetter: boolean;
};

export type Peers = {
  /** 업종 이름 (자세한 쪽) */
  sector: string;
  /** 실제로 견주는 데 쓴 무리 이름 — 회사가 적으면 큰 묶음이 됩니다 */
  used: string;
  count: number;
  per: Rank | null;
  pbr: Rank | null;
  roe: Rank | null;
  debt: Rank | null;
};

type Row = {
  code: string;
  sector_code: string | null;
  per: string | number | null;
  pbr: string | number | null;
  roe: string | number | null;
  debt_ratio: string | number | null;
};

const numOf = (v: string | number | null): number | null => {
  if (v === null) return null;
  const x = typeof v === "number" ? v : Number(v);
  return Number.isFinite(x) ? x : null;
};

/**
 * 한 종목을 같은 업종 회사들과 견줍니다.
 *
 * 값이 없는 회사는 세지 않습니다. 'PER 이 없는 회사' 를 순위에 넣으면
 * 등수가 부풀려집니다.
 */
export async function getPeers(code: string): Promise<Peers | null> {
  const rows = await sql<Row[]>`
    WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price),
    latest_fin AS (
      SELECT DISTINCT ON (f.code) f.code, f.roe, f.debt_ratio
        FROM financial f
       ORDER BY f.code, f.fiscal_year DESC, f.fiscal_quarter DESC
    )
    SELECT t.code, t.sector_code, c.per, c.pbr, lf.roe, lf.debt_ratio
      FROM ticker t
      CROSS JOIN bound b
      JOIN LATERAL (
        SELECT p.per, p.pbr FROM daily_price p
         WHERE p.code = t.code AND p.trade_date >= b.last_d - INTERVAL '30 days'
         ORDER BY p.trade_date DESC LIMIT 1
      ) c ON TRUE
      LEFT JOIN latest_fin lf ON lf.code = t.code
     WHERE t.is_active AND t.kind = 'STOCK' AND t.sector_code IS NOT NULL
  `;

  const me = rows.find((r) => r.code === code);
  if (!me || !me.sector_code) return null;

  const sector = sectorName(me.sector_code);
  if (sector === UNKNOWN) return null;

  // 자세한 업종으로 먼저 모아보고, 적으면 큰 묶음으로.
  let mates = rows.filter((r) => sectorName(r.sector_code) === sector);
  let used = sector;
  if (mates.length < MIN_PEERS) {
    const group = sectorGroup(me.sector_code);
    if (group === UNKNOWN) return null;
    mates = rows.filter((r) => sectorGroup(r.sector_code) === group);
    used = group;
    if (mates.length < MIN_PEERS) return null;
  }

  /**
   * lowerIsBetter : 낮을수록 좋은 지표인가 (PER·PBR·부채비율)
   * positiveOnly  : 0 이하를 빼야 하는가
   *   PER·PBR 은 0 이하가 '값이 없다' 는 뜻이라 세면 안 됩니다.
   *   ROE 는 마이너스가 '적자' 라는 진짜 값이고, 부채비율도 0 이 있을 수
   *   있어서 그대로 셉니다.
   */
  const rankOf = (
    pick: (r: Row) => string | number | null,
    lowerIsBetter: boolean,
    positiveOnly: boolean,
  ): Rank | null => {
    const mine = numOf(pick(me));
    if (mine === null || (positiveOnly && mine <= 0)) return null;

    const vals = mates
      .map((r) => numOf(pick(r)))
      .filter((v): v is number => v !== null && (!positiveOnly || v > 0));
    if (vals.length < MIN_PEERS) return null;

    const sorted = [...vals].sort((a, b) => (lowerIsBetter ? a - b : b - a));
    const rank = sorted.findIndex((v) => v === mine) + 1;
    if (rank === 0) return null;

    const mid = [...vals].sort((a, b) => a - b);
    const median =
      mid.length % 2
        ? mid[(mid.length - 1) / 2]
        : (mid[mid.length / 2 - 1] + mid[mid.length / 2]) / 2;

    return { group: used, count: vals.length, rank, median, lowerIsBetter };
  };

  return {
    sector,
    used,
    count: mates.length,
    per: rankOf((r) => r.per, true, true),
    pbr: rankOf((r) => r.pbr, true, true),
    roe: rankOf((r) => r.roe, false, false),
    debt: rankOf((r) => r.debt_ratio, true, false),
  };
}

/**
 * 등수를 한 문장으로.
 *
 * ★ 무엇을 기준으로 센 등수인지 밝혀야 합니다 ★
 *   그냥 "6곳 중 6번째" 라고만 하면 좋은 건지 나쁜 건지 알 수 없고,
 *   "6번째로 적어" 라고 쓰면 낮은 순 6위(=가장 많음)일 때 말이
 *   거꾸로 됩니다. 실제로 "6번째로 적어, 아주 높은 편입니다" 라는
 *   앞뒤가 안 맞는 문장이 나왔습니다.
 *
 *   그래서 센 방향을 그대로 적습니다 — '낮은 순 6위'.
 *   부채비율·PER·PBR 은 낮은 순, ROE 는 높은 순으로 셉니다.
 */
export function rankSentence(r: Rank): string {
  const 기준 = r.lowerIsBetter ? "낮은 순" : "높은 순";
  const 자리 =
    r.rank === 1
      ? r.lowerIsBetter ? "가장 낮습니다" : "가장 높습니다"
      : r.rank === r.count
        ? r.lowerIsBetter ? "가장 높습니다" : "가장 낮습니다"
        : `${기준} ${r.rank}위입니다`;
  return `같은 ${r.group} ${r.count.toLocaleString("ko-KR")}곳 중 ${자리}`;
}

/**
 * 등수를 말로. '5/32' 는 초보자에게 아무 뜻이 없습니다.
 * 위·아래 어느 쪽인지를 말로 붙여야 읽힙니다.
 */
export function rankWord(r: Rank): string {
  const 상위 = r.rank / r.count;
  if (상위 <= 0.2) return r.lowerIsBetter ? "아주 낮은 편" : "아주 높은 편";
  if (상위 <= 0.4) return r.lowerIsBetter ? "낮은 편" : "높은 편";
  if (상위 <= 0.6) return "가운데쯤";
  if (상위 <= 0.8) return r.lowerIsBetter ? "높은 편" : "낮은 편";
  return r.lowerIsBetter ? "아주 높은 편" : "아주 낮은 편";
}
