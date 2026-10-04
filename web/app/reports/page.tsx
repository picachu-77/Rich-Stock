import ReportList from "@/components/ReportList";
import { getOpinionMix, getRecentReports } from "@/lib/reports";
import { num } from "@/lib/format";

/**
 * 리포트 탭 — 증권사는 이 회사를 어떻게 보는가.
 *
 * ★ 맨 위에 쏠림부터 보여줍니다 ★
 *   목록만 보면 '전문가들이 사라고 하네' 로 읽힙니다. 실제로는 거의 다
 *   매수입니다. 그 사실을 목록보다 먼저 보여줘야 나머지가 제대로
 *   읽힙니다.
 */
export const revalidate = 3600;

export default async function ReportsPage() {
  const [reports, mix] = await Promise.all([
    getRecentReports(40),
    getOpinionMix(90),
  ]);

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>리포트</h1>
          <span className="head-date">한경컨센서스</span>
        </div>
      </header>

      <main>
        {mix && (
          <div className="mix">
            <div className="mix-h">최근 3개월 기업 리포트 {num(mix.total)}건</div>
            <div className="mix-bar" role="img"
                 aria-label={`매수 ${num(mix.buy)}건, 중립 ${num(mix.hold)}건, 매도 ${num(mix.sell)}건`}>
              <i className="m-buy" style={{ width: `${bar(mix.buy, mix)}%` }} />
              <i className="m-hold" style={{ width: `${bar(mix.hold, mix)}%` }} />
              <i className="m-sell" style={{ width: `${bar(mix.sell, mix)}%` }} />
            </div>
            <div className="mix-k">
              <span>매수 <b className="n">{num(mix.buy)}</b></span>
              <span>중립 <b className="n">{num(mix.hold)}</b></span>
              <span>매도 <b className="n">{num(mix.sell)}</b></span>
            </div>
            <p className="mix-note">
              {mix.sell === 0 ? (
                <><b>매도 의견은 한 건도 없습니다.</b> 목표주가를 &apos;여기까지
                  오른다&apos; 로 읽으면 안 되는 이유입니다.</>
              ) : (
                <>매도는 <b className="n">{num(mix.sell)}건</b> 뿐입니다.
                  목표주가보다 <b>왜 그렇게 봤는지</b> 를 보세요.</>
              )}
            </p>
          </div>
        )}

        <div className="sec-h">
          <h2>최근 리포트</h2>
          <span>누르면 원문</span>
        </div>
        <ReportList
          items={reports}
          showName
          empty="아직 받아온 리포트가 없습니다. 깃허브 Actions 의 '증권사 리포트 수집' 을 한 번 돌려주세요."
        />

        <p className="foot">한경컨센서스에서 모은 목록입니다. 원문은 각 증권사의 것입니다.</p>
      </main>
    </div>
  );
}

const bar = (v: number, m: { buy: number; hold: number; sell: number }) => {
  const sum = m.buy + m.hold + m.sell;
  return sum ? (v / sum) * 100 : 0;
};
