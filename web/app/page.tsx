import StockList from "@/components/StockList";
import { getLastDate, getStocks } from "@/lib/stocks";
import { num } from "@/lib/format";

/**
 * 첫 화면 — 종목 목록.
 *
 * 시세는 하루에 한 번(밤 11시)만 바뀝니다. 그래서 이 화면을 미리 만들어
 * 두고 1시간마다 다시 만듭니다. 볼 때마다 데이터베이스에 묻지 않습니다.
 */
export const revalidate = 3600;

export default async function Home() {
  const [stocks, lastDate] = await Promise.all([getStocks(), getLastDate()]);

  // 오늘 장이 어땠는지 한 줄. 숫자를 하나하나 읽기 전에 분위기가 먼저
  // 들어옵니다. 오른 종목이 많은 날인지 내린 날인지가 이 한 줄에 있습니다.
  const up = stocks.filter((s) => (s.change_pct ?? 0) > 0).length;
  const down = stocks.filter((s) => (s.change_pct ?? 0) < 0).length;
  const moved = up + down;

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>국내주식</h1>
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
      </header>

      <main>
        <StockList stocks={stocks} />
      </main>
    </div>
  );
}
