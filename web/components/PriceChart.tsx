"use client";

/**
 * 시세 차트.
 *
 * 왜 차트 라이브러리를 안 쓰나요?
 *   차트 라이브러리는 보통 수백 KB 라 휴대폰에서 화면이 늦게 뜹니다.
 *   여기서 그리는 것은 선 하나뿐이라 직접 그리는 편이 훨씬 가볍습니다.
 *
 * 읽기
 *   값 눈금을 오른쪽에 둡니다. 예전에는 눈금이 없어서, 짚어보기 전에는
 *   이 선이 얼마짜리인지 알 수 없었습니다. 게다가 최저·최고값을 차트
 *   아래 왼쪽·오른쪽에 나란히 적어놔서 시작값·끝값처럼 읽혔습니다.
 *
 *   점선은 이 기간의 시작값입니다. 선이 점선 위에 있으면 그 시점까지
 *   올라 있었다는 뜻이라, '언제 본전을 넘었나' 가 한눈에 보입니다.
 *
 * 다루기
 *   짚기: 손가락으로 끌거나(휴대폰), 마우스를 올리면(컴퓨터) 그날 값이
 *   위에 나옵니다. 키보드로도 됩니다 — 탭으로 차트에 들어와 화살표로
 *   하루씩, Home·End 로 처음·끝, Esc 로 놓습니다.
 *
 *   글자는 SVG 가 아니라 HTML 로 얹습니다. SVG 안에 글자를 넣으면
 *   차트가 늘어날 때 글자도 같이 늘어나서, 좁은 화면에서는 깨알같고
 *   넓은 화면에서는 커집니다.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import type { PricePoint } from "@/lib/stocks";
import { num, signed, tone } from "@/lib/format";

const RANGES = [
  { label: "1개월", months: 1 },
  { label: "3개월", months: 3 },
  { label: "6개월", months: 6 },
  { label: "1년", months: 12 },
  { label: "3년", months: 36 },
  { label: "전체", months: 0 },
] as const;

const W = 700;
const H = 210;
const PAD = { t: 10, r: 6, b: 10, l: 6 };

/** 2026-09-25 → 26.09 (눈금은 짧아야 합니다) */
const shortDate = (iso: string) => `${iso.slice(2, 4)}.${iso.slice(5, 7)}`;

export default function PriceChart({
  data,
  currency = "KRW",
}: {
  data: PricePoint[];
  /** 돈 단위. 미국 종목은 달러로 적습니다. */
  currency?: string;
}) {
  const money = (v: number) =>
    currency === "USD" ? `$${num(v, 2)}` : `${num(v)}원`;

  const [range, setRange] = useState<(typeof RANGES)[number]["label"]>("1년");
  const [hit, setHit] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const pts = useMemo(() => {
    const conf = RANGES.find((r) => r.label === range)!;
    if (!conf.months || data.length === 0) return data;
    const last = new Date(data[data.length - 1].d);
    const from = new Date(last);
    from.setMonth(from.getMonth() - conf.months);
    const iso = from.toISOString().slice(0, 10);
    return data.filter((p) => p.d >= iso);
  }, [data, range]);

  const geo = useMemo(() => {
    if (pts.length === 0) return null;
    const lo = Math.min(...pts.map((p) => p.c));
    const hi = Math.max(...pts.map((p) => p.c));
    const span = hi - lo || 1;
    const iw = W - PAD.l - PAD.r;
    const ih = H - PAD.t - PAD.b;
    const x = (i: number) =>
      PAD.l + (pts.length === 1 ? iw / 2 : (i / (pts.length - 1)) * iw);
    const y = (c: number) => PAD.t + ih - ((c - lo) / span) * ih;
    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.c)}`).join("");
    const area = `${line}L${x(pts.length - 1)},${H - PAD.b}L${x(0)},${H - PAD.b}Z`;
    return { lo, hi, x, y, line, area };
  }, [pts]);

  /** 짚은 자리를 옮깁니다. 값이 그대로면 손대지 않습니다 (헛 그리기 방지) */
  const move = useCallback(
    (i: number) =>
      setHit((prev) => {
        const next = Math.max(0, Math.min(pts.length - 1, i));
        return prev === next ? prev : next;
      }),
    [pts.length],
  );

  /** 손가락·마우스가 짚은 x 위치에서 가장 가까운 날을 찾습니다. */
  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const ratio = (clientX - box.left) / box.width;
    const iw = W - PAD.l - PAD.r;
    move(Math.round(((ratio * W - PAD.l) / iw) * (pts.length - 1)));
  };

  if (pts.length === 0 || !geo) {
    return (
      <div className="note">
        이 기간의 시세가 아직 없습니다. 과거 시세를 채우는 중일 수 있습니다.
      </div>
    );
  }

  const first = pts[0];
  const last = pts[pts.length - 1];
  const 변동 = first.c ? (last.c / first.c - 1) * 100 : null;
  const color = (변동 ?? 0) >= 0 ? "var(--up-bar)" : "var(--down-bar)";
  const cur = hit === null ? null : pts[hit];

  // 짚은 날이 시작값보다 얼마나 위인지. '그날 샀으면' 이 아니라
  // '이 기간 시작에 샀다면 그날 얼마였나' 입니다.
  const 짚은변동 = cur && first.c ? (cur.c / first.c - 1) * 100 : null;

  const pct = (v: number) => `${(v / H) * 100}%`;

  // 시작값이 곧 최저(또는 최고)인 기간이 있습니다. 그때 점선을 그리면
  // 눈금선 위에 겹쳐 그어지고, 아래 설명은 이미 오른쪽에 적힌 숫자를
  // 한 번 더 말하게 됩니다. 그런 날은 점선을 뺍니다.
  const 시작선보임 = first.c !== geo.lo && first.c !== geo.hi;

  return (
    <>
      <div className="chips" role="group" aria-label="차트 기간">
        {RANGES.map((r) => (
          <button
            key={r.label}
            className="chip"
            aria-pressed={range === r.label}
            onClick={() => {
              setRange(r.label);
              setHit(null);
            }}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* 짚었을 때와 안 짚었을 때가 같은 자리에서 바뀝니다. 자리가
          움직이면 손가락을 끌 때 글이 튀어서 읽기 어렵습니다. */}
      <div className="chart-cap" role="status" aria-live="polite">
        {cur ? (
          <>
            <b className="n">{cur.d}</b>
            <span className="n">{money(cur.c)}</span>
            {짚은변동 !== null && (
              <span className={`n ${tone(짚은변동)}`}>
                시작 대비 {signed(짚은변동)}%
              </span>
            )}
          </>
        ) : (
          <>
            <b className={`n ${tone(변동)}`}>
              {signed(변동)}
              {변동 !== null ? "%" : ""}
            </b>
            <span className="n">
              {first.d} ~ {last.d}
            </span>
          </>
        )}
      </div>

      <div className="chart">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          tabIndex={0}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            pick(e.clientX);
          }}
          onPointerMove={(e) => {
            // 마우스는 그냥 올리기만 해도, 손가락은 끌 때만 따라옵니다.
            if (e.pointerType === "mouse" || e.buttons > 0) pick(e.clientX);
          }}
          onPointerLeave={(e) => e.pointerType === "mouse" && setHit(null)}
          onKeyDown={(e) => {
            const at = hit ?? pts.length - 1;
            const step = e.shiftKey ? 10 : 1;
            if (e.key === "ArrowLeft") move(at - step);
            else if (e.key === "ArrowRight") move(at + step);
            else if (e.key === "Home") move(0);
            else if (e.key === "End") move(pts.length - 1);
            else if (e.key === "Escape") setHit(null);
            else return;
            e.preventDefault();
          }}
          role="img"
          aria-label={
            `시세 차트. ${first.d} ${money(first.c)} 에서 ` +
            `${last.d} ${money(last.c)} 까지, ${signed(변동)}%. ` +
            `최고 ${money(geo.hi)}, 최저 ${money(geo.lo)}. ` +
            `화살표 키로 하루씩 짚어볼 수 있습니다.`
          }
        >
          <defs>
            <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.16" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* 최고·최저 눈금선. 오른쪽 숫자가 어느 높이의 값인지 알려줍니다 */}
          <line x1={PAD.l} y1={geo.y(geo.hi)} x2={W - PAD.r} y2={geo.y(geo.hi)}
                stroke="var(--rule-2)" strokeWidth="1" />
          <line x1={PAD.l} y1={geo.y(geo.lo)} x2={W - PAD.r} y2={geo.y(geo.lo)}
                stroke="var(--rule-2)" strokeWidth="1" />

          {/* 이 기간 시작값. 선이 이 위에 있으면 그때까지 올라 있었습니다 */}
          {시작선보임 && (
            <line x1={PAD.l} y1={geo.y(first.c)} x2={W - PAD.r} y2={geo.y(first.c)}
                  stroke="var(--ink-3)" strokeWidth="1" strokeDasharray="4 4" />
          )}

          <path d={geo.area} fill="url(#fade)" />
          <path d={geo.line} fill="none" stroke={color} strokeWidth="2"
                strokeLinejoin="round" strokeLinecap="round" />

          {cur && hit !== null && (
            <>
              <line x1={geo.x(hit)} y1={PAD.t} x2={geo.x(hit)} y2={H - PAD.b}
                    stroke="var(--ink-2)" strokeWidth="1" />
              <circle cx={geo.x(hit)} cy={geo.y(cur.c)} r="5"
                      fill="var(--surface)" stroke={color} strokeWidth="2.5" />
            </>
          )}
        </svg>

        {/* 값 눈금 — 차트 밖 오른쪽 여백에 붙습니다. 선을 가리지 않습니다 */}
        <span className="chart-y" style={{ top: pct(geo.y(geo.hi)) }}>
          <i>최고</i>
          <b className="n">{money(geo.hi)}</b>
        </span>
        <span className="chart-y" style={{ top: pct(geo.y(geo.lo)) }}>
          <i>최저</i>
          <b className="n">{money(geo.lo)}</b>
        </span>
      </div>

      <div className="chart-x n">
        <span>{shortDate(first.d)}</span>
        <span>{shortDate(pts[Math.floor((pts.length - 1) / 2)].d)}</span>
        <span>{shortDate(last.d)}</span>
      </div>

      {시작선보임 && (
        <p className="chart-legend">
          <i aria-hidden="true" /> 점선은 이 기간 시작값 <b className="n">{money(first.c)}</b> 입니다.
        </p>
      )}
    </>
  );
}
