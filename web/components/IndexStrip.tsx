import type { MarketPoint } from "@/lib/indexes";
import { num, signed, tone } from "@/lib/format";

/**
 * 지수 한 줄. 가로로 넘겨 봅니다.
 *
 * ★ 왜 표가 아니라 한 줄인가 ★
 *   여기서 알고 싶은 것은 딱 하나 — '오늘 시장이 오른 날인가 내린
 *   날인가'. 다섯 개를 세로로 쌓으면 첫 화면의 절반을 먹고, 정작
 *   보러 온 종목 목록은 더 아래로 밀립니다.
 */
export default function IndexStrip({ points }: { points: MarketPoint[] }) {
  if (points.length === 0) return null;

  return (
    <div className="idx" role="group" aria-label="지수와 환율">
      {points.map((p) => (
        <div key={p.symbol} className="idx-i">
          <span className="idx-k">{p.name}</span>
          <span className="idx-v n">{num(p.close, 2)}</span>
          {p.change_pct !== null && (
            /* 환율은 오르는 것이 좋은 일도 나쁜 일도 아닙니다.
               주가와 같은 색을 쓰면 '빨간 환율 = 좋다' 로 잘못 읽힙니다. */
            <span className={`idx-c n ${p.isFx ? "flat" : tone(p.change_pct)}`}>
              {signed(p.change_pct)}%
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
