"use client";

/**
 * 사고파는 입력칸. 여기만 브라우저에서 도는 코드입니다.
 *
 * ★ 왜 이 파일만 "use client" 인가 ★
 *   나머지 화면은 전부 서버에서 만들어 보냅니다. 그래야 휴대폰이 받는
 *   자바스크립트가 적어져 빨리 뜹니다. 그런데 사고팔기는
 *   '얼마어치인지 바로 보여주기' 와 '눌렀을 때 두 번 안 눌리게 막기' 가
 *   필요해서 이 부분만 브라우저에서 돌립니다.
 */
import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import type { Result } from "@/app/practice/actions";

const won = (v: number) => `${Math.round(v).toLocaleString("ko-KR")}원`;

/** 누르는 동안 다시 못 누르게 막습니다. 두 번 눌러 두 번 사지는 일을 막습니다. */
function Submit({ label, tone = "" }: { label: string; tone?: string }) {
  const { pending } = useFormStatus();
  return (
    <button className={`btn ${tone}`} disabled={pending}>
      {pending ? "잠깐만요…" : label}
    </button>
  );
}

function Msg({ r }: { r: Result | null }) {
  if (!r || !r.msg) return null;
  return <p className={r.ok ? "msg ok" : "msg bad"}>{r.msg}</p>;
}

/* ── 사기 ─────────────────────────────────────────────────── */

export function BuyForm({
  action,
  stocks,
  reasons,
  cash,
}: {
  action: (p: Result | null, f: FormData) => Promise<Result>;
  stocks: { code: string; name: string; price: number }[];
  reasons: [string, string][];
  cash: number;
}) {
  const [res, run] = useActionState(action, null);
  const [code, setCode] = useState("");
  const [qty, setQty] = useState("");

  const picked = stocks.find((s) => s.code === code);
  const price = picked?.price ?? 0;
  const n = Number(qty) || 0;
  const amount = price * n;
  const fee = Math.round((amount * 0.015) / 100);
  const 살수있는수량 = price > 0 ? Math.floor(cash / (price * 1.00015)) : 0;

  return (
    <form action={run} className="pf">
      <label className="pf-l">
        어떤 종목을
        <select name="code" value={code} onChange={(e) => setCode(e.target.value)} required>
          <option value="">— 고르세요 —</option>
          {stocks.map((s) => (
            <option key={s.code} value={s.code}>
              {s.name} · {won(s.price)}
            </option>
          ))}
        </select>
      </label>

      {picked && (
        <>
          <label className="pf-l">
            몇 주
            <input
              name="qty"
              type="number"
              inputMode="numeric"
              min={1}
              step={1}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder={`최대 ${살수있는수량.toLocaleString("ko-KR")}주`}
              required
            />
          </label>
          <input type="hidden" name="price" value={price} />

          {n > 0 && (
            <p className="pf-sum">
              {won(price)} × {n.toLocaleString("ko-KR")}주 = <b>{won(amount)}</b>
              <br />
              <span className="pf-dim">
                수수료 {won(fee)} 를 더해 <b>{won(amount + fee)}</b> 가 나갑니다
                {amount + fee > cash && " — 돈이 모자랍니다"}
              </span>
            </p>
          )}

          <label className="pf-l">
            왜 사나요?
            <select name="kind" required defaultValue="">
              <option value="">— 고르세요 —</option>
              {reasons.map(([k, d]) => (
                <option key={k} value={k}>
                  {k} ({d})
                </option>
              ))}
            </select>
          </label>

          <label className="pf-l">
            <span className="pf-opt">덧붙일 말 (안 써도 됩니다)</span>
            <input name="memo" maxLength={100} placeholder="예: 2분기 영업이익이 늘어서" />
          </label>

          <div className="pf-two">
            <label className="pf-l">
              목표가 — 얼마가 되면 팔까요
              <input
                name="target"
                type="number"
                inputMode="numeric"
                min={1}
                defaultValue={Math.round(price * 1.2)}
                required
              />
            </label>
            <label className="pf-l">
              손절가 — 얼마까지 내리면 그만둘까요
              <input
                name="stop"
                type="number"
                inputMode="numeric"
                min={1}
                defaultValue={Math.round(price * 0.9)}
                required
              />
            </label>
          </div>

          <p className="pf-note">
            목표가와 손절가는 <b>사기 전에</b> 정해야 뜻이 있습니다. 사고 나면
            오르든 내리든 마음이 흔들려서, 그때 정한 값은 이유가 아니라 변명이
            됩니다.
          </p>

          <Submit label="샀다고 기록하기" />
        </>
      )}
      <Msg r={res} />
    </form>
  );
}

/* ── 팔기 ─────────────────────────────────────────────────── */

export function SellForm({
  action,
  holdings,
  reasons,
}: {
  action: (p: Result | null, f: FormData) => Promise<Result>;
  holdings: { code: string; name: string; qty: number; price: number | null; target: number | null; stop: number | null }[];
  reasons: [string, string][];
}) {
  const [res, run] = useActionState(action, null);
  const [code, setCode] = useState("");
  const [qty, setQty] = useState("");

  const picked = holdings.find((h) => h.code === code);
  const price = picked?.price ?? 0;
  const n = Number(qty) || 0;
  const amount = price * n;
  const fee = Math.round((amount * 0.015) / 100);
  const tax = Math.round((amount * 0.18) / 100);

  // 가진 것이 없을 때도 방금 판 결과는 보여줘야 합니다.
  // 여기서 그냥 돌려보내면, 다 팔고 나서 '팔았다' 는 말이 사라집니다.
  // (기록은 남는데 화면이 아무 말도 안 하니 안 된 줄 압니다)
  if (holdings.length === 0) {
    return (
      <>
        <Msg r={res} />
        <p className="news-none">
          지금 가진 종목이 없습니다. 판 결과는 아래 복기 칸에서 보실 수 있습니다.
        </p>
      </>
    );
  }

  return (
    <form action={run} className="pf">
      <label className="pf-l">
        어떤 종목을
        <select name="code" value={code} onChange={(e) => setCode(e.target.value)} required>
          <option value="">— 고르세요 —</option>
          {holdings.map((h) => (
            <option key={h.code} value={h.code}>
              {h.name} · {h.qty.toLocaleString("ko-KR")}주
            </option>
          ))}
        </select>
      </label>

      {picked && (
        <>
          {/* 살 때 한 약속을 여기서 다시 보여줍니다. 팔지 말지 정하는
              자리에서 그때의 기준이 눈앞에 있어야 합니다. */}
          {(picked.target || picked.stop) && (
            <p className="pf-vow">
              살 때 정하신 약속 —{" "}
              {picked.target && <>목표 <b>{won(picked.target)}</b></>}
              {picked.target && picked.stop && " · "}
              {picked.stop && <>손절 <b>{won(picked.stop)}</b></>}
            </p>
          )}

          <label className="pf-l">
            몇 주
            <input
              name="qty"
              type="number"
              inputMode="numeric"
              min={1}
              max={picked.qty}
              step={1}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder={`최대 ${picked.qty.toLocaleString("ko-KR")}주`}
              required
            />
          </label>
          <input type="hidden" name="price" value={price} />

          {n > 0 && (
            <p className="pf-sum">
              {won(price)} × {n.toLocaleString("ko-KR")}주 = <b>{won(amount)}</b>
              <br />
              <span className="pf-dim">
                수수료 {won(fee)} · 세금 {won(tax)} 를 빼고{" "}
                <b>{won(amount - fee - tax)}</b> 가 들어옵니다
              </span>
            </p>
          )}

          <label className="pf-l">
            왜 파나요?
            <select name="kind" required defaultValue="">
              <option value="">— 고르세요 —</option>
              {reasons.map(([k, d]) => (
                <option key={k} value={k}>
                  {k} ({d})
                </option>
              ))}
            </select>
          </label>

          <label className="pf-l">
            <span className="pf-opt">덧붙일 말 (안 써도 됩니다)</span>
            <input name="memo" maxLength={100} />
          </label>

          <Submit label="팔았다고 기록하기" tone="sell" />
        </>
      )}
      <Msg r={res} />
    </form>
  );
}

/* ── 예수금 ───────────────────────────────────────────────── */

export function CashForm({
  action,
}: {
  action: (p: Result | null, f: FormData) => Promise<Result>;
}) {
  const [res, run] = useActionState(action, null);
  return (
    <form action={run} className="pf">
      <label className="pf-l">
        얼마를 (빼려면 앞에 - 를 붙이세요)
        <input name="amount" type="number" inputMode="numeric" step={10000} required placeholder="1000000" />
      </label>
      <label className="pf-l">
        <span className="pf-opt">메모 (안 써도 됩니다)</span>
        <input name="memo" maxLength={60} />
      </label>
      <Submit label="기록하기" />
      <Msg r={res} />
    </form>
  );
}

/* ── 자물쇠 ───────────────────────────────────────────────── */

export function GateForm({
  action,
}: {
  action: (p: Result | null, f: FormData) => Promise<Result>;
}) {
  const [res, run] = useActionState(action, null);
  return (
    <form action={run} className="pf">
      <label className="pf-l">
        암호
        <input name="passcode" type="password" autoComplete="current-password" required />
      </label>
      <Submit label="들어가기" />
      <Msg r={res} />
    </form>
  );
}
