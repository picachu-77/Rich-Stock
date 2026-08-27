import type { Point } from "@/lib/paper";
import { num, signed, tone } from "@/lib/format";

/**
 * 연습 자산이 어떻게 움직였나.
 *
 * ★ 두 줄을 함께 그립니다 ★
 *   총자산만 그리면 돈을 더 넣었을 때도 선이 올라가서, 잘한 것인지
 *   그냥 넣은 것인지 구분이 안 됩니다. 넣은 돈을 점선으로 같이 그리면
 *   두 선 사이의 벌어짐이 곧 연습 성과가 됩니다.
 *
 * ★ 차트 라이브러리를 쓰지 않습니다 ★
 *   선 두 개뿐이라 직접 그리는 편이 훨씬 가볍습니다.
 *   이 화면 전체가 그 원칙으로 만들어져 있습니다.
 */
const W = 700;
const H = 150;
const PAD = { t: 12, r: 8, b: 8, l: 8 };

export default function AssetChart({ points }: { points: Point[] }) {
  // 점이 하나뿐이면 선이 안 그려집니다. 그때는 그리지 않습니다.
  if (points.length < 2) return null;

  const vals = points.flatMap((p) => [p.총자산, p.넣은돈]);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || Math.max(hi * 0.02, 1); // 전부 같은 값이면 납작해집니다

  const x = (i: number) => PAD.l + (i / (points.length - 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b);

  const line = (pick: (p: Point) => number) =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(pick(p)).toFixed(1)}`).join(" ");

  const 마지막 = points[points.length - 1];
  const 손익 = 마지막.총자산 - 마지막.넣은돈;
  const 손익률 = 마지막.넣은돈 > 0 ? (손익 / 마지막.넣은돈) * 100 : 0;
  const dir = tone(손익);

  return (
    <div className="ac">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`연습 자산 흐름. 지금 총자산 ${num(Math.round(마지막.총자산))}원, 넣은 돈 ${num(Math.round(마지막.넣은돈))}원.`}
      >
        {/* 넣은 돈 — 기준선 */}
        <path d={line((p) => p.넣은돈)} className="ac-base" />
        {/* 총자산 */}
        <path d={line((p) => p.총자산)} className={`ac-line ${dir}`} />
      </svg>
      <p className="ac-cap">
        <span className="n">{points[0].d}</span> 부터 · 넣은 돈보다{" "}
        <b className={`n ${dir}`}>
          {signed(손익, 0)}원 ({signed(손익률, 1)}%)
        </b>
      </p>
      <p className="ac-note">
        점선이 넣은 돈입니다. 두 선이 벌어진 만큼이 연습 성과입니다 — 돈을 더
        넣어서 올라간 것과 구분하려고 함께 그립니다.
      </p>
    </div>
  );
}
