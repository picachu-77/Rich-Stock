"use client";

/**
 * 시세 차트.
 *
 * 왜 차트 라이브러리를 안 쓰나요?
 *   차트 라이브러리는 보통 수백 KB 라 휴대폰에서 화면이 늦게 뜹니다.
 *   여기서 그리는 것은 선 하나뿐이라 직접 그리는 편이 훨씬 가볍습니다.
 *   ('느립니다' 가 이 화면을 새로 만드는 이유 중 하나였습니다)
 *
 * 손가락으로 짚으면 그날 값을 보여줍니다.
 */

import { useMemo, useRef, useState } from "react";
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
const H = 220;
const PAD = { t: 10, r: 8, b: 20, l: 8 };

export default function PriceChart({ data }: { data: PricePoint[] }) {
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

  if (pts.length === 0 || !geo) {
    return (
      <div className="note">
        이 기간의 시세가 아직 없습니다. 과거 시세를 채우는 중일 수 있습니다.
      </div>
    );
  }

  const first = pts[0];
  const last = pts[pts.length - 1];
  const 변동 = first.c ? ((last.c / first.c - 1) * 100) : null;
  const 오름 = (변동 ?? 0) >= 0;
  const color = 오름 ? "var(--up-bar)" : "var(--down-bar)";
  const cur = hit === null ? null : pts[hit];

  /** 손가락·마우스가 짚은 x 위치에서 가장 가까운 날을 찾습니다. */
  const pick = (clientX: number) => {
    const el = svgRef.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    const ratio = (clientX - box.left) / box.width;
    const iw = W - PAD.l - PAD.r;
    const i = Math.round(((ratio * W - PAD.l) / iw) * (pts.length - 1));
    setHit(Math.max(0, Math.min(pts.length - 1, i)));
  };

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

      <div className="chart-cap">
        {cur ? (
          <span className="n">
            <b style={{ color: "var(--ink)" }}>{cur.d}</b> · {num(cur.c)}원
          </span>
        ) : (
          <span className="n">
            <span className="nowrap">
              구간 변동{" "}
              <b className={tone(변동)}>
                {signed(변동)}
                {변동 !== null ? "%" : ""}
              </b>
            </span>{" · "}
            <span className="nowrap">{first.d} ~ {last.d}</span>{" · "}
            <span className="nowrap">거래일 {num(pts.length)}일</span>
          </span>
        )}
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", touchAction: "pan-y" }}
        onPointerDown={(e) => pick(e.clientX)}
        onPointerMove={(e) => e.buttons > 0 && pick(e.clientX)}
        onPointerLeave={() => setHit(null)}
        role="img"
        aria-label={`시세 차트 ${first.d} ~ ${last.d}`}
      >
        <defs>
          <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.18" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        <path d={geo.area} fill="url(#fade)" />
        <path d={geo.line} fill="none" stroke={color} strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />

        {cur && hit !== null && (
          <>
            <line x1={geo.x(hit)} y1={PAD.t} x2={geo.x(hit)} y2={H - PAD.b}
                  stroke="var(--ink-3)" strokeWidth="1" strokeDasharray="3 3" />
            <circle cx={geo.x(hit)} cy={geo.y(cur.c)} r="4.5"
                    fill="var(--surface)" stroke={color} strokeWidth="2.5" />
          </>
        )}
      </svg>

      <div className="n"
           style={{ display: "flex", justifyContent: "space-between",
                    fontSize: ".74rem", color: "var(--ink-3)", marginTop: -4 }}>
        <span className="n">{num(geo.lo)}원</span>
        <span className="n">{num(geo.hi)}원</span>
      </div>
      <div style={{ fontSize: ".76rem", color: "var(--ink-3)", marginTop: 4 }}>
        차트를 손가락으로 짚으면 그날 값이 나옵니다.
      </div>
    </>
  );
}
