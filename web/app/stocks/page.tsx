import StockList from "@/components/StockList";
import { getLastDate, getStocks } from "@/lib/stocks";

/**
 * 종목 탭 — 전체 목록.
 *
 * ★ 첫 화면에서 떼어냈습니다 ★
 *   전에는 첫 화면 아래에 3,900줄이 이어져 있었습니다. 오늘 시장이
 *   어땠는지만 보려던 사람도 종목 목록을 통째로 받아야 했습니다.
 *   이제 목록을 보러 올 때만 받습니다.
 */
export const revalidate = 3600;

export default async function StocksPage() {
  const [stocks, lastDate] = await Promise.all([getStocks(), getLastDate()]);

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>종목</h1>
          {lastDate && <span className="head-date n">{lastDate}</span>}
        </div>
      </header>

      <main>
        {/* '전체 종목 4,033개' 머리말을 뺐습니다. 바로 아래 개수 줄이
            '4,033개 종목 · 시가총액 순' 이라고 다시 말합니다. */}
        <StockList stocks={stocks} />
      </main>
    </div>
  );
}
