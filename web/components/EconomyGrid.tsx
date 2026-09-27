import type { Econ } from "@/lib/economy";

/**
 * 경제 지표 넉 줄.
 *
 * ★ 왜 색을 안 쓰는가 ★
 *   이 화면에서 빨강·파랑은 '올랐다·내렸다' 가 아니라 '좋다·나쁘다' 로
 *   읽힙니다. 그런데 금리가 오르는 것은 주식에 불리하고, 공포지수가
 *   오르는 것도 불리합니다. 오른 것을 빨갛게 칠해두면 정반대로
 *   읽히게 됩니다. 그래서 지표는 모두 무채색입니다.
 *
 *   진한 색은 이 앱 전체에서 시세에만 씁니다.
 *
 * ★ 왜 설명을 접어두는가 ★
 *   지표는 숫자만 봐서는 아무 뜻이 없습니다. '10년 금리 4.23%' 가
 *   높은 건지 낮은 건지, 내 주식과 무슨 상관인지 모르면 없는 것과
 *   같습니다. 그렇다고 넉 줄 모두에 설명을 펼쳐두면 첫 화면이 글
 *   덩어리가 됩니다. 숫자 칸(Fact)과 같은 방식으로, 누르면 그 자리에서
 *   펴집니다.
 */
export default function EconomyGrid({ items }: { items: Econ[] }) {
  if (items.length === 0) return null;

  return (
    <div className="econ">
      {items.map((e) => (
        <details className="ec" key={e.symbol}>
          <summary>
            <span className="ec-k">
              {e.name}
              <i className="ec-q" aria-hidden="true">?</i>
            </span>
            <span className="ec-row">
              <b className="ec-v n">{e.value}</b>
              {e.diff && <span className="ec-d n">{e.diff}</span>}
            </span>
          </summary>
          <div className="ec-x">{e.뜻}</div>
        </details>
      ))}
    </div>
  );
}
