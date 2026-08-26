import StockList from "@/components/StockList";
import { getLastDate, getStocks } from "@/lib/stocks";
import { num } from "@/lib/format";

/**
 * 첫 화면 — 종목 목록.
 *
 * 시세는 하루에 한 번(밤 11시)만 바뀝니다. 그래서 이 화면을 미리 만들어
 * 두고 1시간마다 다시 만듭니다. 볼 때마다 데이터베이스에 물어보지 않으니
 * 훨씬 빠릅니다.
 */
export const revalidate = 3600;

export default async function Home() {
  const [stocks, lastDate] = await Promise.all([getStocks(), getLastDate()]);

  return (
    <>
      <header className="top">
        <div className="top-in">
          <h1 className="title">📈 국내주식 대시보드</h1>
          <div className="sub tnum">
            {num(stocks.length)}개 종목
            {lastDate ? ` · ${lastDate} 기준` : ""}
          </div>
        </div>
      </header>

      <main className="wrap">
        <StockList stocks={stocks} />
      </main>
    </>
  );
}
