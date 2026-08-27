import Link from "next/link";
import { sql } from "@/lib/db";
import { allowed, gateReady } from "@/lib/gate";
import {
  BUY_REASONS,
  SELL_REASONS,
  cashLeft,
  getDeposits,
  getTrades,
  holdings,
  unpackReason,
  walk,
} from "@/lib/paper";
import { num, signed, tone } from "@/lib/format";
import { BuyForm, SellForm, CashForm, GateForm } from "@/components/PracticeForms";
import { 사기, 팔기, 돈넣기, 열기, 잠그기 } from "./actions";

/**
 * 모의투자 — 진짜 돈 없이 사고파는 연습.
 *
 * 볼 때마다 새로 계산합니다. 방금 산 것이 바로 보여야 하는 화면이라
 * 미리 만들어 두면 안 됩니다.
 */
export const dynamic = "force-dynamic";

const won = (v: number) => `${num(Math.round(v))}원`;

export default async function PracticePage() {
  if (!gateReady()) {
    return (
      <Shell>
        <p className="news-none">
          모의투자는 아직 잠겨 있습니다.
          <br />
          <span className="news-none-sub">
            Vercel &gt; Settings &gt; Environment Variables 에{" "}
            <b>PAPER_PASSCODE</b> 를 넣으면 열립니다. 이 화면은 기록을 남기는
            곳이라, 주소를 아는 사람이면 누구나 손댈 수 있게 두지 않았습니다.
          </span>
        </p>
      </Shell>
    );
  }

  if (!(await allowed())) {
    return (
      <Shell>
        <p className="pf-note" style={{ marginTop: 0 }}>
          연습 기록을 지키기 위해 암호를 한 번 확인합니다. 한 번 넣으면 30일
          동안 다시 묻지 않습니다.
        </p>
        <GateForm action={열기} />
      </Shell>
    );
  }

  /* ── 자료 모으기 ── */
  const [trades, deposits] = await Promise.all([getTrades(), getDeposits()]);

  // 지금 값을 붙이려면 최근 시세가 필요합니다.
  const priceRows = await sql<{ code: string; name: string; close: string | number }[]>`
    WITH bound AS (SELECT max(trade_date) AS last_d FROM daily_price)
    SELECT t.code, t.name, c.close
      FROM ticker t
      CROSS JOIN bound b
      JOIN LATERAL (
        SELECT p.close FROM daily_price p
         WHERE p.code = t.code AND p.trade_date >= b.last_d - INTERVAL '30 days'
         ORDER BY p.trade_date DESC LIMIT 1
      ) c ON TRUE
     WHERE c.close IS NOT NULL
     ORDER BY t.name
  `;
  const priceOf = new Map(priceRows.map((r) => [r.code, Number(r.close)]));
  const nameOf = new Map(priceRows.map((r) => [r.code, r.name]));

  const held = holdings(trades, priceOf, nameOf);
  const { closed } = walk(trades);
  const cash = cashLeft(trades, deposits);

  const 평가액 = held.reduce((s, h) => s + (h.value ?? h.cost), 0);
  const 총자산 = cash + 평가액;
  const 손익 = deposits > 0 ? 총자산 - deposits : 0;
  const 손익률 = deposits > 0 ? (손익 / deposits) * 100 : 0;

  /* ── 처음 오신 분 ── */
  if (deposits === 0 && trades.length === 0) {
    return (
      <Shell onLock>
        <p className="pf-note" style={{ marginTop: 0 }}>
          <b>진짜 돈은 한 푼도 쓰지 않습니다.</b> 사고파는 연습만 하는
          곳입니다. 목적은 돈을 버는 게 아니라, 내가 왜 사고 왜 파는지를
          기록해두고 나중에 되돌아보는 것입니다.
          <br />
          <br />
          먼저 연습에 쓸 돈을 정해주세요. 실제로 투자할 만한 금액으로
          잡으셔야 연습이 됩니다. 1억을 넣고 연습하면 실제와 느낌이 너무
          달라집니다.
        </p>
        <CashForm action={돈넣기} />
      </Shell>
    );
  }

  const 살수있는종목 = priceRows
    .map((r) => ({ code: r.code, name: r.name, price: Number(r.close) }))
    .filter((s) => s.price > 0);

  return (
    <Shell onLock>
      {/* ── 지금 상태 ── */}
      <div className="stats" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
        <div className="stat">
          <div className="stat-k">총자산</div>
          <div className="stat-v n">{won(총자산)}</div>
        </div>
        <div className="stat">
          <div className="stat-k">넣은 돈 대비</div>
          <div className={`stat-v n ${tone(손익)}`}>
            {deposits > 0 ? `${signed(손익률, 1)}%` : "—"}
          </div>
        </div>
        <div className="stat">
          <div className="stat-k">쓸 수 있는 돈</div>
          <div className="stat-v n">{won(cash)}</div>
        </div>
        <div className="stat">
          <div className="stat-k">넣은 돈</div>
          <div className="stat-v n">{won(deposits)}</div>
        </div>
      </div>

      {/* ── 가진 종목 ── */}
      <div className="sec-h">
        <h2>가진 종목</h2>
        <span className="n">{num(held.length)}개</span>
      </div>
      {held.length === 0 ? (
        <p className="news-none">아직 가진 종목이 없습니다.</p>
      ) : (
        <ul className="news">
          {held.map((h) => {
            const r = unpackReason(h.reason);
            const 목표도달 = h.price !== null && h.target !== null && h.price >= h.target;
            const 손절도달 = h.price !== null && h.stop !== null && h.price <= h.stop;
            return (
              <li key={h.code}>
                <div style={{ padding: "12px 14px" }}>
                  <span className="dc-top">
                    <b className="dc-name">{h.name}</b>
                    {r.kind && <span className="dc-cat">{r.kind}</span>}
                  </span>
                  <span className="news-t" style={{ fontWeight: 500 }}>
                    {num(h.qty)}주 · 산 값 {won(h.avg)}
                    {h.price !== null && <> · 지금 {won(h.price)}</>}
                  </span>
                  <span className="news-m">
                    {h.pnl === null ? (
                      "지금 값을 몰라 손익을 낼 수 없습니다"
                    ) : (
                      <>
                        <b className={tone(h.pnl)}>
                          {signed(h.pnl, 0)}원 ({signed(h.pnlPct ?? 0, 1)}%)
                        </b>
                        {h.since && <> · {h.since}부터</>}
                      </>
                    )}
                  </span>
                  {(목표도달 || 손절도달) && (
                    <p className={목표도달 ? "vow hit" : "vow stop"}>
                      {목표도달
                        ? `목표가 ${won(h.target!)}에 닿았습니다. 팔기로 하셨던 자리입니다.`
                        : `손절가 ${won(h.stop!)}까지 내렸습니다. 그만두기로 하셨던 자리입니다.`}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* ── 사기 ── */}
      <div className="sec-h">
        <h2>사기</h2>
        <span>왜 사는지 적어야 합니다</span>
      </div>
      <BuyForm action={사기} stocks={살수있는종목} reasons={BUY_REASONS} cash={cash} />

      {/* ── 팔기 ── */}
      <div className="sec-h">
        <h2>팔기</h2>
      </div>
      <SellForm
        action={팔기}
        holdings={held.map((h) => ({
          code: h.code,
          name: h.name,
          qty: h.qty,
          price: h.price,
          target: h.target,
          stop: h.stop,
        }))}
        reasons={SELL_REASONS}
      />

      {/* ── 복기 ── */}
      <div className="sec-h">
        <h2>복기</h2>
        <span>판 뒤에 되돌아보기</span>
      </div>
      {closed.length === 0 ? (
        <p className="news-none">
          아직 판 것이 없습니다. 팔고 나면 <b>그때 왜 샀는지</b>와 결과를 나란히
          보여드립니다. 이게 이 연습의 진짜 목적입니다.
        </p>
      ) : (
        <ul className="news">
          {[...closed].reverse().map((c, i) => {
            const 산이유 = unpackReason(c.buyReason);
            const 판이유 = unpackReason(c.sellReason);
            const 약속지킴 =
              판이유.kind === "목표가에 닿아서" || 판이유.kind === "손절가에 닿아서";
            return (
              <li key={i}>
                <div style={{ padding: "12px 14px" }}>
                  <span className="dc-top">
                    <b className="dc-name">{c.name}</b>
                    <span className={`dc-cat ${약속지킴 ? "" : "warn"}`}>
                      {약속지킴 ? "약속대로" : "약속과 다르게"}
                    </span>
                  </span>
                  <span className="news-t">
                    <span className={tone(c.pnl)}>
                      {signed(c.pnl, 0)}원 ({signed(c.pnlPct, 1)}%)
                    </span>
                  </span>
                  <span className="news-m">
                    {num(c.qty)}주 · {won(c.avg)} → {won(c.sellPrice)}
                    {c.days !== null && <> · {num(c.days)}일 들고 있었습니다</>}
                  </span>
                  <p className="rv">
                    <b>살 때</b> {산이유.kind || "적지 않음"}
                    {산이유.memo && ` — ${산이유.memo}`}
                    {c.target !== null && ` (목표 ${won(c.target)})`}
                    <br />
                    <b>팔 때</b> {판이유.kind || "적지 않음"}
                    {판이유.memo && ` — ${판이유.memo}`}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* ── 예수금 ── */}
      <div className="sec-h">
        <h2>연습에 쓸 돈</h2>
      </div>
      <CashForm action={돈넣기} />

      <p className="foot">
        진짜 돈은 한 푼도 쓰지 않습니다. 수수료 0.015%, 증권거래세 0.18%(팔 때만)로
        계산합니다 — 실제 증권사와는 다를 수 있지만, 사고팔 때마다 돈이 조금씩
        나간다는 것을 느끼시라고 넣었습니다. 지금 값은 마지막 거래일 종가라
        장중 실제 가격과는 다릅니다.
      </p>

      <form action={잠그기}>
        <button className="btn ghost">잠그기</button>
      </form>
    </Shell>
  );
}

function Shell({ children, onLock }: { children: React.ReactNode; onLock?: boolean }) {
  return (
    <div className="wrap">
      <header className="head" style={{ paddingBottom: 0 }}>
        <Link href="/" className="back">← 목록</Link>
        <div className="head-top" style={{ marginTop: 2 }}>
          <h1 style={{ fontSize: "1.3rem" }}>모의투자</h1>
          <span className="tag">연습</span>
        </div>
      </header>
      <main>{children}</main>
      {onLock === undefined && <div style={{ height: 20 }} />}
    </div>
  );
}
