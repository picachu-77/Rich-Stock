/**
 * 모의투자 — 진짜 돈을 쓰지 않고 사고파는 연습.
 *
 * ★ 목적은 돈을 버는 게 아니라 '연습' 입니다 ★
 *   그래서 살 때 세 가지를 반드시 적게 합니다.
 *     · 왜 사는지
 *     · 얼마가 되면 팔지 (목표가)
 *     · 얼마까지 내리면 손절할지
 *   적어두지 않으면 나중에 잘한 판단인지 운이었는지 알 수 없습니다.
 *   실제 투자에서 가장 크게 다치는 것도 이걸 안 정해두고 사는 경우입니다.
 *
 * ★ 계산은 파이썬 쪽(src/paper.py)과 같아야 합니다 ★
 *   같은 표를 두 화면이 함께 씁니다. 계산이 어긋나면 어느 쪽 숫자를
 *   믿어야 할지 알 수 없게 됩니다. 평균단가는 이동평균법,
 *   수수료는 평균단가에 포함 — 여기까지 똑같이 맞췄습니다.
 */
import { sql } from "./db";

/** 증권사 수수료 (%) — 살 때·팔 때 각각. src/paper.py 와 같은 값입니다. */
export const FEE_RATE = 0.015;
/** 증권거래세 (%) — 팔 때만. 손해를 봐도 냅니다. */
export const TAX_RATE = 0.18;

/** 이 화면이 쓰는 계좌 이름. Streamlit 화면과 같은 것을 씁니다. */
export const OWNER = "me";

export type Side = "BUY" | "SELL";

export type Trade = {
  id: number;
  date: string;
  code: string;
  name: string;
  side: Side;
  qty: number;
  price: number;
  fee: number;
  tax: number;
  reason: string | null;
  target: number | null;
  stop: number | null;
};

/** 지금 들고 있는 종목 하나. */
export type Holding = {
  code: string;
  name: string;
  qty: number;
  /** 수수료까지 포함한 1주당 산 값 */
  avg: number;
  /** 산 데 들어간 돈 전부 */
  cost: number;
  /** 지금 값 (모르면 null) */
  price: number | null;
  /** 지금 값으로 쳤을 때의 평가금액 */
  value: number | null;
  /** 아직 안 판 손익 */
  pnl: number | null;
  pnlPct: number | null;
  target: number | null;
  stop: number | null;
  reason: string | null;
  since: string | null;
};

/** 팔아서 끝난 거래 하나. */
export type Closed = {
  date: string;
  code: string;
  name: string;
  qty: number;
  sellPrice: number;
  avg: number;
  /** 확정된 손익 (수수료·세금 뺀 것) */
  pnl: number;
  pnlPct: number;
  /** 살 때 적었던 이유 — 이게 있어야 복기가 됩니다 */
  buyReason: string | null;
  sellReason: string | null;
  target: number | null;
  stop: number | null;
  days: number | null;
};

/* ── 수수료·세금 ──────────────────────────────────────────── */

export function costs(amount: number, side: Side) {
  const fee = Math.round((amount * FEE_RATE) / 100 * 100) / 100;
  const tax =
    side === "SELL" ? Math.round((amount * TAX_RATE) / 100 * 100) / 100 : 0;
  return { fee, tax };
}

/* ── 기록 읽기 ────────────────────────────────────────────── */

type TradeRow = {
  id: string | number;
  trade_date: Date | string;
  code: string;
  name: string | null;
  side: string;
  qty: number;
  price: string | number;
  fee: string | number;
  tax: string | number;
  reason: string | null;
  target_price: string | number | null;
  stop_price: string | number | null;
};

const n = (v: string | number | null): number =>
  v === null ? 0 : typeof v === "number" ? v : Number(v);
const nOrNull = (v: string | number | null): number | null =>
  v === null ? null : typeof v === "number" ? v : Number(v);
const day = (v: Date | string): string =>
  (v instanceof Date ? v : new Date(v)).toISOString().slice(0, 10);

export async function getTrades(owner = OWNER): Promise<Trade[]> {
  const rows = await sql<TradeRow[]>`
    SELECT p.id, p.trade_date, p.code, t.name, p.side, p.qty, p.price,
           p.fee, p.tax, p.reason, p.target_price, p.stop_price
      FROM paper_trade p
      LEFT JOIN ticker t ON t.code = p.code
     WHERE p.owner = ${owner}
     ORDER BY p.trade_date, p.id
  `;
  return rows.map((r) => ({
    id: Number(r.id),
    date: day(r.trade_date),
    code: r.code,
    name: r.name ?? r.code,
    side: r.side === "SELL" ? "SELL" : "BUY",
    qty: Number(r.qty),
    price: n(r.price),
    fee: n(r.fee),
    tax: n(r.tax),
    reason: r.reason,
    target: nOrNull(r.target_price),
    stop: nOrNull(r.stop_price),
  }));
}

/** 넣고 뺀 돈의 합계. */
export async function getDeposits(owner = OWNER): Promise<number> {
  const rows = await sql<{ total: string | null }[]>`
    SELECT COALESCE(sum(amount), 0) AS total FROM paper_cash WHERE owner = ${owner}
  `;
  return n(rows[0]?.total ?? 0);
}

/* ── 기록을 훑어 지금 상태 만들기 ─────────────────────────── */

type Pos = {
  qty: number;
  cost: number;
  avg: number;
  since: string | null;
  target: number | null;
  stop: number | null;
  reason: string | null;
};

/**
 * 매매 기록을 처음부터 훑으며 보유 상태와 확정 손익을 계산합니다.
 * (src/paper.py 의 walk() 와 같은 규칙)
 *
 * 평균단가는 이동평균법입니다. 살 때마다 '들어간 돈 전부 ÷ 가진 수량' 으로
 * 다시 냅니다. 팔 때는 평균단가를 그대로 두고 수량만 줄입니다.
 */
export function walk(trades: Trade[]): { held: Map<string, Pos>; closed: Closed[] } {
  const held = new Map<string, Pos>();
  const closed: Closed[] = [];

  for (const t of trades) {
    let pos = held.get(t.code);
    if (!pos) {
      pos = { qty: 0, cost: 0, avg: 0, since: null, target: null, stop: null, reason: null };
      held.set(t.code, pos);
    }

    if (t.side === "BUY") {
      // 다 팔았다가 다시 사면 보유 기간은 그때부터 새로 셉니다.
      if (pos.qty === 0) pos.since = t.date;
      pos.qty += t.qty;
      pos.cost += t.qty * t.price + t.fee;
      pos.avg = pos.qty ? pos.cost / pos.qty : 0;
      if (t.target !== null) pos.target = t.target;
      if (t.stop !== null) pos.stop = t.stop;
      if (t.reason && t.reason.trim()) pos.reason = t.reason.trim();
      continue;
    }

    // ── 팔 때 ──
    const sellQty = Math.min(t.qty, pos.qty);
    if (sellQty <= 0) continue;

    const avg = pos.avg;
    const got = sellQty * t.price - t.fee - t.tax; // 손에 들어온 돈
    const spent = avg * sellQty; // 그만큼 사는 데 들었던 돈

    closed.push({
      date: t.date,
      code: t.code,
      name: t.name,
      qty: sellQty,
      sellPrice: t.price,
      avg,
      pnl: got - spent,
      pnlPct: spent ? ((got - spent) / spent) * 100 : 0,
      buyReason: pos.reason,
      sellReason: t.reason,
      target: pos.target,
      stop: pos.stop,
      days: pos.since ? daysBetween(pos.since, t.date) : null,
    });

    pos.qty -= sellQty;
    pos.cost -= avg * sellQty;
    if (pos.qty === 0) {
      pos.cost = 0;
      pos.avg = 0;
      pos.since = null;
      pos.reason = null;
    }
  }

  return { held, closed };
}

const daysBetween = (a: string, b: string): number =>
  Math.round((Date.parse(b) - Date.parse(a)) / 86400000);

/** 지금 들고 있는 것만, 현재가를 붙여서. */
export function holdings(
  trades: Trade[],
  priceOf: Map<string, number>,
  nameOf: Map<string, string>,
): Holding[] {
  const { held } = walk(trades);
  const out: Holding[] = [];

  for (const [code, p] of held) {
    if (p.qty <= 0) continue;
    const price = priceOf.get(code) ?? null;
    const value = price === null ? null : price * p.qty;
    out.push({
      code,
      name: nameOf.get(code) ?? code,
      qty: p.qty,
      avg: p.avg,
      cost: p.cost,
      price,
      value,
      pnl: value === null ? null : value - p.cost,
      pnlPct: value === null || !p.cost ? null : ((value - p.cost) / p.cost) * 100,
      target: p.target,
      stop: p.stop,
      reason: p.reason,
      since: p.since,
    });
  }
  return out.sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
}

/**
 * 남은 현금.
 *   넣은 돈 − 산 데 쓴 돈(수수료 포함) + 판 돈(수수료·세금 뺀 것)
 */
export function cashLeft(trades: Trade[], deposits: number): number {
  let cash = deposits;
  for (const t of trades) {
    if (t.side === "BUY") cash -= t.qty * t.price + t.fee;
    else cash += t.qty * t.price - t.fee - t.tax;
  }
  return cash;
}

/* ── 왜 사는지 / 왜 파는지 ────────────────────────────────── */

/**
 * 고를 수 있는 이유들. src/practice.py 와 같은 목록입니다.
 * 마지막의 '그냥 느낌으로' 는 일부러 남겨 두었습니다. 없는 척하면
 * 다들 그럴듯한 이유를 고르게 되고, 그러면 복기가 거짓이 됩니다.
 */
export const BUY_REASONS: [string, string][] = [
  ["실적이 좋아서", "매출·이익이 늘고 있거나 재무가 튼튼해서"],
  ["값이 싸 보여서", "PER·PBR 이 예전보다, 또는 같은 업종보다 낮아서"],
  ["방향이 좋아서", "공시·신사업 등 회사가 가는 길이 마음에 들어서"],
  ["배당을 보고", "꾸준히 배당을 주는 점이 마음에 들어서"],
  ["뉴스·테마를 보고", "요즘 뜨는 이야기라서"],
  ["차트를 보고", "가격 흐름·이동평균선 등 그림을 보고"],
  ["그냥 느낌으로", "남들이 사길래 / 딱히 이유는 없이"],
];

export const SELL_REASONS: [string, string][] = [
  ["목표가에 닿아서", "살 때 정한 목표 가격까지 올라서"],
  ["손절가에 닿아서", "살 때 정한 손절 가격까지 내려서"],
  ["산 이유가 사라져서", "실적이 꺾이는 등 처음 산 근거가 없어져서"],
  ["더 좋은 곳에 쓰려고", "다른 종목이 더 나아 보여서"],
  ["불안해서", "많이 내려서 / 참기 힘들어서"],
  ["돈이 필요해서", "투자와 상관없는 이유로"],
];

/** 저장할 때는 '[갈래] 적은 말' 로 한 칸에 넣습니다. */
export const packReason = (kind: string, memo: string): string =>
  memo.trim() ? `[${kind}] ${memo.trim()}` : `[${kind}]`;

/** 읽을 때는 다시 갈래와 말로 나눕니다. */
export function unpackReason(s: string | null): { kind: string; memo: string } {
  if (!s) return { kind: "", memo: "" };
  const m = s.match(/^\[([^\]]+)\]\s*(.*)$/);
  return m ? { kind: m[1], memo: m[2] } : { kind: "", memo: s };
}

/* ── 쌓인 기록 ────────────────────────────────────────────── */

/** 입출금 한 줄. */
export type CashMove = {
  id: number;
  date: string;
  amount: number;
  memo: string | null;
};

export async function getCashMoves(owner = OWNER): Promise<CashMove[]> {
  const rows = await sql<
    { id: string | number; cash_date: Date | string; amount: string | number; memo: string | null }[]
  >`
    SELECT id, cash_date, amount, memo
      FROM paper_cash
     WHERE owner = ${owner}
     ORDER BY cash_date, id
  `;
  return rows.map((r) => ({
    id: Number(r.id),
    date: day(r.cash_date),
    amount: n(r.amount),
    memo: r.memo,
  }));
}

/**
 * 여태 한 일을 시간 순으로 한 줄씩.
 *
 * 지금 가진 것과 판 것만 보면, 사고팔기를 반복했을 때 '무엇을 해왔는지'
 * 가 사라집니다. 예를 들어 같은 종목을 세 번 나눠 산 것은 평균단가
 * 하나로 뭉쳐져서 흔적이 남지 않습니다. 연습은 쌓인 것을 되돌아보는
 * 일이라, 한 일은 한 일대로 남아 있어야 합니다.
 */
export type Event =
  | { kind: "BUY" | "SELL"; date: string; id: number; code: string; name: string;
      qty: number; price: number; fee: number; tax: number; reason: string | null;
      target: number | null; stop: number | null }
  | { kind: "CASH"; date: string; id: number; amount: number; memo: string | null };

export function timeline(trades: Trade[], cash: CashMove[]): Event[] {
  const out: Event[] = [
    ...trades.map(
      (t): Event => ({
        kind: t.side,
        date: t.date,
        id: t.id,
        code: t.code,
        name: t.name,
        qty: t.qty,
        price: t.price,
        fee: t.fee,
        tax: t.tax,
        reason: t.reason,
        target: t.target,
        stop: t.stop,
      }),
    ),
    ...cash.map((c): Event => ({ kind: "CASH", date: c.date, id: c.id, amount: c.amount, memo: c.memo })),
  ];
  // 최근 것이 위로. 같은 날이면 나중에 한 것이 위로.
  return out.sort((a, b) => (a.date === b.date ? b.id - a.id : a.date < b.date ? 1 : -1));
}

/* ── 자산이 어떻게 움직였나 ───────────────────────────────── */

export type Point = { d: string; 총자산: number; 넣은돈: number };

/**
 * 무슨 일이 있었던 날마다 그날 기준 총자산을 계산합니다.
 *
 * 왜 거래일 전부가 아니라 '일이 있었던 날' 인가:
 *   연습은 며칠에 한 번 하는 일이라 점이 몇 개 안 됩니다. 3년치 거래일
 *   748일을 전부 그리면 대부분 변화가 없는 평평한 선이 되고, 정작
 *   내가 무엇을 한 날인지가 안 보입니다. 마지막 날은 항상 넣습니다 —
 *   '지금 얼마인지' 로 끝나야 하니까요.
 *
 * priceAt: 종목코드 → (날짜 → 그날 종가)
 */
export function assetCurve(
  trades: Trade[],
  cash: CashMove[],
  priceAt: Map<string, Map<string, number>>,
  today: string,
): Point[] {
  const days = [...new Set([...trades.map((t) => t.date), ...cash.map((c) => c.date), today])].sort();
  const out: Point[] = [];

  for (const d of days) {
    const upto = trades.filter((t) => t.date <= d);
    const 넣은돈 = cash.filter((c) => c.date <= d).reduce((s, c) => s + c.amount, 0);
    const 현금 = cashLeft(upto, 넣은돈);

    const { held } = walk(upto);
    let 평가액 = 0;
    for (const [code, p] of held) {
      if (p.qty <= 0) continue;
      // 그날 값을 모르면 산 값으로 둡니다. 모르는 것을 0 으로 두면
      // 자산이 갑자기 사라진 것처럼 보입니다.
      const px = priceOn(priceAt, code, d);
      평가액 += px === null ? p.cost : px * p.qty;
    }
    out.push({ d, 총자산: 현금 + 평가액, 넣은돈 });
  }
  return out;
}

/** 그날 값이 없으면 그 전 가장 가까운 날의 값을 씁니다(휴장일 등). */
function priceOn(
  priceAt: Map<string, Map<string, number>>,
  code: string,
  d: string,
): number | null {
  const m = priceAt.get(code);
  if (!m) return null;
  const hit = m.get(d);
  if (hit !== undefined) return hit;
  let best: string | null = null;
  for (const k of m.keys()) if (k <= d && (best === null || k > best)) best = k;
  return best === null ? null : (m.get(best) ?? null);
}
