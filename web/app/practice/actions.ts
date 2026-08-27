"use server";

/**
 * 모의투자에서 실제로 기록을 남기는 곳.
 *
 * ★ 모든 함수가 맨 먼저 자물쇠를 확인합니다 ★
 *   화면에서 막는 것만으로는 부족합니다. 주소를 직접 부르면 그만이라,
 *   저장하는 쪽에서 한 번 더 봐야 합니다.
 *
 * ★ 화면에서 막은 것을 여기서 또 막습니다 ★
 *   '가진 것보다 많이 팔기', '없는 돈으로 사기' 같은 것은 화면에서도
 *   막지만 여기서도 막습니다. 화면은 사용자를 돕는 장치이고,
 *   기록이 망가지지 않게 지키는 것은 이쪽 일입니다.
 */
import { revalidatePath } from "next/cache";
import { sql } from "@/lib/db";
import { allowed, unlock, lock } from "@/lib/gate";
import {
  OWNER,
  costs,
  getDeposits,
  getTrades,
  cashLeft,
  walk,
  packReason,
} from "@/lib/paper";

export type Result = { ok: boolean; msg: string };

const 실패 = (msg: string): Result => ({ ok: false, msg });
const 성공 = (msg: string): Result => ({ ok: true, msg });

/** 화면을 다시 그리게 합니다. 안 하면 방금 산 것이 목록에 안 보입니다. */
const 새로고침 = () => revalidatePath("/practice");

/* ── 자물쇠 ───────────────────────────────────────────────── */

export async function 열기(_prev: Result | null, form: FormData): Promise<Result> {
  const ok = await unlock(String(form.get("passcode") ?? ""));
  if (!ok) return 실패("암호가 맞지 않습니다.");
  새로고침();
  return 성공("");
}

export async function 잠그기(): Promise<void> {
  await lock();
  새로고침();
}

/* ── 예수금 ───────────────────────────────────────────────── */

export async function 돈넣기(_prev: Result | null, form: FormData): Promise<Result> {
  if (!(await allowed())) return 실패("먼저 암호를 넣어주세요.");

  const amount = Number(form.get("amount"));
  if (!Number.isFinite(amount) || amount === 0) {
    return 실패("금액을 넣어주세요.");
  }

  const memo = String(form.get("memo") ?? "").trim();

  // 뺄 때는 있는 돈보다 많이 뺄 수 없습니다.
  if (amount < 0) {
    const [trades, deposits] = await Promise.all([getTrades(), getDeposits()]);
    const cash = cashLeft(trades, deposits);
    if (cash + amount < 0) {
      return 실패(`뺄 수 있는 돈은 ${Math.floor(cash).toLocaleString("ko-KR")}원까지입니다.`);
    }
  }

  await sql`
    INSERT INTO paper_cash (owner, cash_date, amount, memo)
    VALUES (${OWNER}, CURRENT_DATE, ${amount}, ${memo || null})
  `;
  새로고침();
  return 성공(
    amount > 0
      ? `${Math.round(amount).toLocaleString("ko-KR")}원을 넣었습니다.`
      : `${Math.round(-amount).toLocaleString("ko-KR")}원을 뺐습니다.`,
  );
}

/* ── 사기 ─────────────────────────────────────────────────── */

export async function 사기(_prev: Result | null, form: FormData): Promise<Result> {
  if (!(await allowed())) return 실패("먼저 암호를 넣어주세요.");

  const code = String(form.get("code") ?? "").trim();
  const qty = Math.floor(Number(form.get("qty")));
  const price = Number(form.get("price"));
  const kind = String(form.get("kind") ?? "").trim();
  const memo = String(form.get("memo") ?? "");
  const target = form.get("target") ? Number(form.get("target")) : null;
  const stop = form.get("stop") ? Number(form.get("stop")) : null;

  if (!code) return 실패("종목을 골라주세요.");
  if (!Number.isFinite(qty) || qty <= 0) return 실패("몇 주를 살지 넣어주세요.");
  if (!Number.isFinite(price) || price <= 0) return 실패("가격이 이상합니다.");
  if (!kind) return 실패("왜 사는지 골라주세요. 이걸 적어야 나중에 복기가 됩니다.");
  if (target === null || !Number.isFinite(target) || target <= 0) {
    return 실패("목표가를 정해주세요. 얼마가 되면 팔지 미리 정하는 것이 연습의 핵심입니다.");
  }
  if (stop === null || !Number.isFinite(stop) || stop <= 0) {
    return 실패("손절가를 정해주세요. 얼마까지 내리면 그만둘지 미리 정해야 합니다.");
  }
  if (target <= price) return 실패("목표가는 지금 값보다 높아야 합니다.");
  if (stop >= price) return 실패("손절가는 지금 값보다 낮아야 합니다.");

  const amount = qty * price;
  const { fee } = costs(amount, "BUY");

  const [trades, deposits] = await Promise.all([getTrades(), getDeposits()]);
  const cash = cashLeft(trades, deposits);
  if (amount + fee > cash) {
    return 실패(
      `돈이 모자랍니다. 남은 돈 ${Math.floor(cash).toLocaleString("ko-KR")}원, ` +
        `필요한 돈 ${Math.ceil(amount + fee).toLocaleString("ko-KR")}원(수수료 포함).`,
    );
  }

  await sql`
    INSERT INTO paper_trade
      (owner, trade_date, code, side, qty, price, fee, tax, reason, target_price, stop_price)
    VALUES
      (${OWNER}, CURRENT_DATE, ${code}, 'BUY', ${qty}, ${price}, ${fee}, 0,
       ${packReason(kind, memo)}, ${target}, ${stop})
  `;
  새로고침();
  return 성공(
    `${qty.toLocaleString("ko-KR")}주를 샀습니다. ` +
      `약속 — ${Math.round(target).toLocaleString("ko-KR")}원이 되면 팔고, ` +
      `${Math.round(stop).toLocaleString("ko-KR")}원까지 내리면 손절하기로 정했습니다.`,
  );
}

/* ── 팔기 ─────────────────────────────────────────────────── */

export async function 팔기(_prev: Result | null, form: FormData): Promise<Result> {
  if (!(await allowed())) return 실패("먼저 암호를 넣어주세요.");

  const code = String(form.get("code") ?? "").trim();
  const qty = Math.floor(Number(form.get("qty")));
  const price = Number(form.get("price"));
  const kind = String(form.get("kind") ?? "").trim();
  const memo = String(form.get("memo") ?? "");

  if (!code) return 실패("종목을 골라주세요.");
  if (!Number.isFinite(qty) || qty <= 0) return 실패("몇 주를 팔지 넣어주세요.");
  if (!Number.isFinite(price) || price <= 0) return 실패("가격이 이상합니다.");
  if (!kind) return 실패("왜 파는지 골라주세요.");

  const trades = await getTrades();
  const { held } = walk(trades);
  const have = held.get(code)?.qty ?? 0;
  if (qty > have) {
    return 실패(`가진 것은 ${have.toLocaleString("ko-KR")}주뿐입니다.`);
  }

  const amount = qty * price;
  const { fee, tax } = costs(amount, "SELL");

  await sql`
    INSERT INTO paper_trade
      (owner, trade_date, code, side, qty, price, fee, tax, reason)
    VALUES
      (${OWNER}, CURRENT_DATE, ${code}, 'SELL', ${qty}, ${price}, ${fee}, ${tax},
       ${packReason(kind, memo)})
  `;
  새로고침();
  return 성공(`${qty.toLocaleString("ko-KR")}주를 팔았습니다. 복기 칸에서 결과를 확인해 보세요.`);
}
