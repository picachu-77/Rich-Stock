import Link from "next/link";
import StockList from "@/components/StockList";
import NewsList from "@/components/NewsList";
import DisclosureList from "@/components/DisclosureList";
import IndexStrip from "@/components/IndexStrip";
import { getLastDate, getStocks } from "@/lib/stocks";
import { getMarketNews, newsReady } from "@/lib/news";
import { getRecentDisclosures } from "@/lib/disclosures";
import { getIndexes } from "@/lib/indexes";
import { num } from "@/lib/format";

/**
 * 첫 화면 — 종목 목록.
 *
 * 시세는 하루에 한 번(밤 11시)만 바뀝니다. 그래서 이 화면을 미리 만들어
 * 두고 1시간마다 다시 만듭니다. 볼 때마다 데이터베이스에 묻지 않습니다.
 */
export const revalidate = 3600;

export default async function Home() {
  const [stocks, lastDate, disclosures, news, indexes] = await Promise.all([
    getStocks(),
    getLastDate(),
    getRecentDisclosures(4),
    newsReady() ? getMarketNews(3) : Promise.resolve([]),
    getIndexes(),
  ]);

  // 오늘 장이 어땠는지 한 줄. 숫자를 하나하나 읽기 전에 분위기가 먼저
  // 들어옵니다. 오른 종목이 많은 날인지 내린 날인지가 이 한 줄에 있습니다.
  const up = stocks.filter((s) => (s.change_pct ?? 0) > 0).length;
  const down = stocks.filter((s) => (s.change_pct ?? 0) < 0).length;
  const moved = up + down;

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>한국·미국 주식</h1>
          {lastDate && <span className="head-date n">{lastDate}</span>}
        </div>

        {moved > 0 && (
          <div className="breadth">
            <span className="up">▲ <b className="n">{num(up)}</b></span>
            <div
              className="breadth-bar"
              role="img"
              aria-label={`오른 종목 ${num(up)}개, 내린 종목 ${num(down)}개`}
            >
              <i className="b-up" style={{ width: `${(up / moved) * 100}%` }} />
              <i className="b-down" style={{ width: `${(down / moved) * 100}%` }} />
            </div>
            <span className="down"><b className="n">{num(down)}</b> ▼</span>
          </div>
        )}

        {/* 종목 하나가 빠진 날, 시장 전체가 빠진 것인지 이 회사만
            그런 것인지 알려면 기준선이 있어야 합니다. */}
        <IndexStrip points={indexes} />
      </header>

      <main>
        {/* 연습으로 가는 길. 목록 위에 둡니다 — 아래에 두면 3,900줄 뒤라
            아무도 닿지 못합니다. */}
        <Link href="/practice" className="go-practice">
          <b>모의투자</b>
          <span>진짜 돈 없이 사고파는 연습 — 왜 샀는지 적어두고 되돌아보기</span>
        </Link>

        {/* 무슨 일이 있었는지 먼저 읽고 종목을 봅니다.
            목록은 3,900줄이라 아래에 두면 아무도 닿지 못합니다. */}
        <div className="sec-h" style={{ marginTop: 4 }}>
          <h2>최근 공시</h2>
          <span>전자공시(DART)</span>
        </div>
        <DisclosureList
          items={disclosures}
          empty="최근 일주일 사이 올라온 공시가 없습니다."
          showName
        />

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

        <div className="sec-h">
          <h2>전체 종목</h2>
          <span className="n">{num(stocks.length)}개</span>
        </div>
        <StockList stocks={stocks} />
      </main>
    </div>
  );
}
