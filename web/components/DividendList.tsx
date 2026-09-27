import type { Payout } from "@/lib/dividends";
import { num } from "@/lib/format";

/**
 * 배당 내역.
 *
 * ★ 이 칸이 답해야 하는 것은 하나입니다 ★
 *   "배당 받으려면 언제까지 사야 하나."
 *   그래서 아직 오지 않은 기준일이 있으면 그것부터 크게 보여줍니다.
 *
 * ★ 모르면 모른다고 합니다 ★
 *   '기준일 전전 거래일' 은 그 사이에 장이 며칠 서는지를 알아야
 *   셀 수 있습니다. 기준일이 앞으로의 날이면 아직 모릅니다. 그럴 때
 *   날짜를 지어내지 않고 규칙만 말합니다 — 하루 늦게 사면 못 받습니다.
 *
 * ★ 색을 쓰지 않습니다 ★
 *   배당은 오르내리는 것이 아닙니다. 진한 색은 시세에만 씁니다.
 */
export default function DividendList({ items }: { items: Payout[] }) {
  if (items.length === 0) return null;

  const 다음 = items.find((p) => p.upcoming);
  const 지난 = items.filter((p) => !p.upcoming);

  return (
    <>
      <div className="sec-h">
        <h2>배당</h2>
        <span>전자공시(DART)</span>
      </div>

      {다음 && (
        <div className="dv-next">
          <span className="dv-next-k">다음 배당기준일</span>
          <b className="dv-next-v n">{다음.recordDate}</b>
          {다음.perShare !== null && (
            <span className="dv-next-amt n">1주당 {num(다음.perShare)}원</span>
          )}
          <p className="dv-next-x">
            {다음.buyBy ? (
              <>
                <b className="n">{다음.buyBy}</b> 까지 사야 받습니다.
              </>
            ) : (
              <>
                <b>기준일 이틀 전(거래일 기준)</b>까지 사야 받습니다. 정확한
                날짜는 그 사이 쉬는 날이 며칠인지에 달려 있어 아직
                셀 수 없습니다.
              </>
            )}{" "}
            산 주식이 내 것이 되기까지 이틀 걸리기 때문입니다. 기준일 당일에
            사면 늦습니다.
          </p>
        </div>
      )}

      {지난.length > 0 && (
        <div className="dv-list">
          {지난.map((p) => (
            <div className="dv" key={p.rcept_no}>
              <div className="dv-l">
                <span className="dv-kind">{p.kind ?? "배당"}</span>
                <span className="dv-date n">
                  기준일 {p.recordDate}
                  {p.payDate && <> · 지급 {p.payDate}</>}
                </span>
              </div>
              <div className="dv-r">
                <b className="n">
                  {p.perShare === null ? "—" : `${num(p.perShare)}원`}
                </b>
                {p.yieldPct !== null && (
                  <span className="dv-y n">{num(p.yieldPct, 2)}%</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="foot" style={{ marginTop: 8 }}>
        1주당 금액은 보통주 기준입니다. 배당은 <b>회사가 그때그때 정하는
        것</b>이라 지난번에 줬다고 다음에도 준다는 보장이 없습니다.
      </p>
    </>
  );
}
