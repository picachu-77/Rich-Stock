/**
 * 공시 가져오기.
 *
 * ★ 왜 뉴스 대신 공시인가 ★
 *   네이버가 검색 API 창구를 개발자센터에서 네이버 클라우드로 옮기면서
 *   신규 등록을 막았습니다(2026년 8월). 그래서 뉴스를 못 받는 상태입니다.
 *
 *   그런데 창고에는 이미 공시가 13만 건 넘게 들어 있습니다. 게다가
 *   공시는 기자가 쓴 기사가 아니라 **회사가 직접 신고한 사실**입니다.
 *   "왜 올랐나" 를 되짚는 데는 오히려 이쪽이 정확합니다.
 *   열쇠도, 돈도, 바깥 연결도 필요 없습니다.
 *
 * ★ 갈래는 파이썬 쪽에서 이미 붙여 두었습니다 ★
 *   src/disclosure.py 가 제목을 보고 category 칸을 채워 저장합니다.
 *   여기서는 그 값을 읽어 쓰기만 합니다. 규칙을 두 군데 두면 반드시
 *   어긋납니다.
 */
import { sql } from "./db";

export type Disclosure = {
  id: string;
  code: string;
  name: string;
  at: Date;
  title: string;
  category: string;
};

/** DART 원문 주소. 공시는 반드시 원문을 볼 수 있어야 합니다. */
export const dartUrl = (id: string): string =>
  `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${id}`;

/**
 * 갈래마다 한눈에 보이는 이름과 색.
 *
 * 색은 딱 하나만 씁니다 — '조심할 일'. 나머지는 무채색입니다.
 * 이 화면에서 빨강·파랑은 '올랐다/내렸다' 라는 뜻이라, 공시에까지
 * 색을 뿌리면 그 약속이 깨집니다. 다만 횡령·상장폐지·감사의견거절 같은
 * 것은 놓치면 안 되는 일이라 이것만 눈에 띄게 둡니다.
 */
export const CATEGORY: Record<string, { label: string; warn?: boolean }> = {
  위험: { label: "조심할 일", warn: true },
  투자: { label: "돈을 씁니다" },
  수주: { label: "일감을 땄습니다" },
  조달: { label: "돈을 구합니다" },
  주주환원: { label: "주주에게 돌려줍니다" },
  지배구조: { label: "주인이 바뀝니다" },
  정기보고: { label: "정기 보고서" },
  기타: { label: "그 밖에" },
};

export const categoryLabel = (key: string): string =>
  CATEGORY[key]?.label ?? CATEGORY.기타.label;

export const isWarning = (key: string): boolean => CATEGORY[key]?.warn === true;

type Row = {
  rcept_no: string;
  code: string;
  name: string | null;
  rcept_dt: Date | string;
  report_nm: string;
  category: string | null;
};

const toDisclosure = (r: Row): Disclosure => ({
  id: r.rcept_no,
  code: r.code,
  name: r.name ?? r.code,
  at: r.rcept_dt instanceof Date ? r.rcept_dt : new Date(r.rcept_dt),
  title: r.report_nm,
  category: r.category ?? "기타",
});

/** 종목 하나의 최근 공시. */
export async function getStockDisclosures(
  code: string,
  limit = 8,
): Promise<Disclosure[]> {
  try {
    const rows = await sql<Row[]>`
      SELECT d.rcept_no, d.code, t.name, d.rcept_dt, d.report_nm, d.category
        FROM disclosure d
        LEFT JOIN ticker t ON t.code = d.code
       WHERE d.code = ${code}
       ORDER BY d.rcept_dt DESC, d.rcept_no DESC
       LIMIT ${limit}
    `;
    return rows.map(toDisclosure);
  } catch {
    // 공시를 못 읽어도 종목 화면은 열려야 합니다.
    return [];
  }
}

/**
 * 첫 화면에 놓을 '오늘의 공시'.
 *
 * 정기보고서는 뺍니다. 분기마다 수천 건이 한꺼번에 올라와서 그냥 두면
 * 화면이 사업보고서로만 도배됩니다. 정해진 때에 내는 것이라 신호도
 * 아닙니다.
 *
 * '조심할 일' 을 맨 위로 올립니다. 첫 화면에서 한 번은 눈에 띄어야 하는
 * 것들입니다.
 */
export async function getRecentDisclosures(limit = 6): Promise<Disclosure[]> {
  try {
    const rows = await sql<Row[]>`
      SELECT d.rcept_no, d.code, t.name, d.rcept_dt, d.report_nm, d.category
        FROM disclosure d
        JOIN ticker t ON t.code = d.code
       WHERE d.category <> '정기보고'
         AND d.rcept_dt >= (SELECT max(rcept_dt) - 7 FROM disclosure)
       ORDER BY (d.category = '위험') DESC, d.rcept_dt DESC, d.rcept_no DESC
       LIMIT ${limit}
    `;
    return rows.map(toDisclosure);
  } catch {
    return [];
  }
}

/** 공시가 창고에 있는지. 없으면 화면에서 안내문을 다르게 냅니다. */
export async function hasDisclosures(): Promise<boolean> {
  try {
    const rows = await sql<{ ok: boolean }[]>`
      SELECT EXISTS (SELECT 1 FROM disclosure) AS ok
    `;
    return rows[0]?.ok ?? false;
  } catch {
    return false;
  }
}

/** '3일 전' 처럼 읽어줍니다. 공시는 날짜만 있어 시각은 없습니다. */
export function daysAgo(at: Date, now: Date = new Date()): string {
  const a = Date.UTC(at.getFullYear(), at.getMonth(), at.getDate());
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  const d = Math.round((b - a) / 86400000);
  if (d <= 0) return "오늘";
  if (d === 1) return "어제";
  if (d < 7) return `${d}일 전`;
  return `${at.getMonth() + 1}월 ${at.getDate()}일`;
}
