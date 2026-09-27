import Link from "next/link";
import NewsList from "@/components/NewsList";
import DisclosureList from "@/components/DisclosureList";
import IndexStrip from "@/components/IndexStrip";
import EconomyGrid from "@/components/EconomyGrid";
import ReportList from "@/components/ReportList";
import { getBreadth, getLastDate } from "@/lib/stocks";
import { getMarketNews, newsReady } from "@/lib/news";
import { getRecentDisclosures } from "@/lib/disclosures";
import { getIndexes } from "@/lib/indexes";
import { getEconomy } from "@/lib/economy";
import { getRecentReports } from "@/lib/reports";
import { num } from "@/lib/format";

/**
 * 홈 — 오늘 시장이 어땠나.
 *
 * ★ 종목 목록을 여기서 뺐습니다 ★
 *   전에는 이 화면 아래로 3,900줄이 이어졌습니다. '오늘 어땠나' 만
 *   보려던 사람도 종목 전체를 받아야 했습니다. 목록은 종목 탭으로
 *   옮기고, 여기는 한눈에 들어오는 것만 둡니다.
 *
 * ★ 탭과 겹치는 배너를 뺐습니다 ★
 *   '종목 보러 가기' 와 '모의투자' 큰 단추가 있었는데, 둘 다 아래
 *   탭에 그대로 있습니다. 같은 곳으로 가는 길이 두 개씩 있으면
 *   화면만 길어지고 어느 쪽이 맞는지 잠깐 생각하게 됩니다.
 *
 * ★ 오른 종목 수를 창고에서 셉니다 ★
 *   막대 하나 그리려고 4천 개를 받아오지 않습니다. 세는 일은
 *   창고가 훨씬 잘합니다.
 */
export const revalidate = 3600;

export default async function Home() {
  const [breadth, lastDate, disclosures, news, indexes, reports, economy] =
    await Promise.all([
      getBreadth(),
      getLastDate(),
      getRecentDisclosures(3),
      newsReady() ? getMarketNews(3) : Promise.resolve([]),
      getIndexes(),
      getRecentReports(3, "기업"),
      getEconomy(),
    ]);

  const moved = breadth.up + breadth.down;

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>오늘 시장</h1>
          {lastDate && <span className="head-date n">{lastDate}</span>}
        </div>

        {/* 오늘의 얼굴. 이 화면의 주인공은 숫자라, 작은 글씨로 흘리지
            않고 크게 세웁니다. 그 아래 지수를 붙여 '시장 전체가
            그랬나' 를 한 카드 안에서 읽게 합니다. */}
        {moved > 0 && (
          <div className="today">
            <div className="breadth">
              <span className="side">
                <span className="k">오른 종목</span>
                <span className="v up n">{num(breadth.up)}</span>
              </span>
              <span className="side r">
                <span className="k">내린 종목</span>
                <span className="v down n">{num(breadth.down)}</span>
              </span>
            </div>
            <div
              className="breadth-bar"
              role="img"
              aria-label={`오른 종목 ${num(breadth.up)}개, 내린 종목 ${num(breadth.down)}개`}
            >
              <i className="b-up" style={{ width: `${(breadth.up / moved) * 100}%` }} />
              <i className="b-down" style={{ width: `${(breadth.down / moved) * 100}%` }} />
            </div>
            <span className="breadth-total">
              오늘 움직인 <b className="n">{num(moved)}</b>개 · 전체{" "}
              <b className="n">{num(breadth.total)}</b>개
            </span>

            {/* 종목 하나가 빠진 날, 시장 전체가 빠진 것인지 이 회사만
                그런 것인지 알려면 기준선이 있어야 합니다. */}
            <IndexStrip points={indexes} />
          </div>
        )}
      </header>

      <main>
        {/* 지수 바로 다음입니다. 지수가 '오늘 어땠나' 라면 이건 그
            뒤에 있는 사정이라, 공시·리포트보다 먼저 와야 순서가
            맞습니다 — 넓은 것에서 좁은 것으로. */}
        {economy.length > 0 && (
          <>
            <div className="sec-h" style={{ marginTop: 4 }}>
              <h2>경제 지표</h2>
              <span>눌러서 뜻 보기</span>
            </div>
            <EconomyGrid items={economy} />
          </>
        )}

        <div className="sec-h">
          <h2>최근 공시</h2>
          <span>전자공시(DART)</span>
        </div>
        <DisclosureList
          items={disclosures}
          empty="최근 일주일 사이 올라온 공시가 없습니다."
          showName
        />

        {reports.length > 0 && (
          <>
            <div className="sec-h">
              <h2>오늘 리포트</h2>
              <Link href="/reports" className="sec-more">모두 보기</Link>
            </div>
            <ReportList items={reports} showName empty="" />
          </>
        )}

        {newsReady() && (
          <>
            <div className="sec-h">
              <h2>오늘 증시</h2>
              <span>네이버 뉴스</span>
            </div>
            <NewsList
              articles={news}
              ready
              empty="지금은 가져올 증시 뉴스가 없습니다."
              compact
            />
          </>
        )}
      </main>
    </div>
  );
}
