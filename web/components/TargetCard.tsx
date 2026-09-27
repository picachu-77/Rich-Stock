import type { Target } from "@/lib/reports";
import { num, signed } from "@/lib/format";

/**
 * 증권사 목표주가.
 *
 * ★ 숫자만 덩그러니 놓으면 안 됩니다 ★
 *   이 앱에서 직접 세어봤습니다. 한경컨센서스 2주치 77건 중
 *   매수 62 · 중립 2 · 매도 0 이었습니다. 증권사 의견은 한쪽으로 크게
 *   쏠려 있습니다. 목표주가만 크게 띄우면 '전문가가 오른다고 했다' 로
 *   읽히는데, 그건 사실이 아닙니다.
 *
 *   그래서 늘 함께 보여줍니다.
 *     · 몇 곳이 봤는지        — 한 곳이면 그냥 한 사람 의견입니다
 *     · 가장 낮게 본 곳은 얼마 — 평균만 보면 폭이 안 보입니다
 *     · 매수·중립·매도가 몇 대 몇
 *
 * ★ 이 칸에는 빨강·파랑을 쓰지 않습니다 ★
 *   '지금보다 +32%' 에 시세 빨강을 써봤다가 뺐습니다. 화면으로 보니
 *   이 종목이 32% 오른 것처럼 읽혔습니다. 실제로는 '증권사들이 평균
 *   32% 위를 보고 있다' 는 뜻일 뿐, 아직 아무 일도 일어나지 않았습니다.
 *   바로 세 줄 아래에서 경고하는 그 오해를 색으로 만들고 있었습니다.
 *
 *   방향은 +·− 부호가 말합니다. 색이 없어도 읽히고, 색 구분이 어려운
 *   분도 읽힙니다.
 */
export default function TargetCard({
  target,
  close,
}: {
  target: Target;
  /** 지금 값 (원). 목표가와 얼마나 떨어져 있는지 보려고 받습니다. */
  close: number | null;
}) {
  const 여지 = close && close > 0 ? (target.avg / close - 1) * 100 : null;
  const 의견 = target.buy + target.hold + target.sell;

  return (
    <>
      <div className="sec-h">
        <h2>증권사 목표주가</h2>
        <span>최근 6개월</span>
      </div>

      <div className="tg">
        <div className="tg-top">
          <div>
            <span className="tg-k">평균 목표주가</span>
            <b className="tg-v n">{num(target.avg)}원</b>
          </div>
          {여지 !== null && (
            <span className="tg-gap n">지금보다 {signed(여지, 0)}%</span>
          )}
        </div>

        {/* 평균만 보면 폭이 안 보입니다. 낮게 본 곳과 높게 본 곳이
            두 배씩 차이 나는 일이 드물지 않습니다. */}
        <div className="tg-range">
          <span>
            가장 낮게 <b className="n">{num(target.low)}원</b>
          </span>
          <span>
            가장 높게 <b className="n">{num(target.high)}원</b>
          </span>
        </div>

        <p className="tg-note">
          <b className="n">{num(target.count)}곳</b>이 목표주가를 냈습니다
          {의견 > 0 && (
            <>
              . 투자의견은 매수 <b className="n">{num(target.buy)}</b> · 중립{" "}
              <b className="n">{num(target.hold)}</b> · 매도{" "}
              <b className="n">{num(target.sell)}</b>
            </>
          )}
          . 가장 최근 리포트는 <span className="n">{target.last}</span> 입니다.
        </p>

        <p className="tg-care">
          목표주가는 <b>남의 의견</b>이지 약속이 아닙니다. 증권사 리포트는
          매도 의견이 거의 나오지 않습니다 — 이 앱이 모은 최근 리포트에서도
          매도는 손에 꼽습니다. 그러니 <b>목표주가가 지금 값보다 높다는 것만으로
          사면 안 됩니다.</b> 왜 그렇게 봤는지는 리포트 원문에 있습니다.
        </p>
      </div>
    </>
  );
}
