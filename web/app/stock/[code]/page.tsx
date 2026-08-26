import Link from "next/link";
import { notFound } from "next/navigation";
import PriceChart from "@/components/PriceChart";
import NewsList from "@/components/NewsList";
import { getHistory, getStock } from "@/lib/stocks";
import { getStockNews, newsReady } from "@/lib/news";
import { PERIODS } from "@/lib/periods";
import { eok, limitHit, num, railWidth, signed, tone } from "@/lib/format";

export const revalidate = 3600;

export default async function StockPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const [stock, history] = await Promise.all([getStock(code), getHistory(code)]);
  if (!stock) notFound();

  // 뉴스는 종목 이름으로 찾기 때문에 종목을 먼저 확인한 뒤에 부릅니다.
  // 네이버가 느리거나 열쇠가 없어도 이 화면은 그대로 열립니다.
  const news = await getStockNews(stock.name);

  const dir = tone(stock.change_pct);
  const lim = limitHit(stock.change_pct);

  return (
    <div className="wrap">
      <header className="head" style={{ paddingBottom: 0 }}>
        <Link href="/" className="back">← 목록</Link>

        <div className="head-top" style={{ marginTop: 2 }}>
          <h1 style={{ fontSize: "1.3rem" }}>{stock.name}</h1>
          <span className="row-code n">{stock.code}</span>
          <span className="tag">{stock.kind === "ETF" ? "ETF" : stock.market}</span>
        </div>

        <div className="px-row">
          <span className={`px-big n ${dir}`}>
            {stock.close === null ? "—" : num(stock.close)}
          </span>
          <span className={`n ${dir}`} style={{ fontSize: "1rem", fontWeight: 700 }}>
            {signed(stock.change_pct)}{stock.change_pct !== null && "%"}
            {lim && <span className={`limit ${lim}`}>{lim === "up" ? "상한가" : "하한가"}</span>}
          </span>
          <span style={{ fontSize: ".76rem", color: "var(--ink-3)", marginLeft: "auto" }}>
            <span className="n">{stock.trade_date}</span> 기준
          </span>
        </div>

        <div className="rail" aria-hidden="true">
          {stock.change_pct !== null && stock.change_pct !== 0 && (
            <i className={dir} style={{ width: `${railWidth(stock.change_pct)}%` }} />
          )}
        </div>
      </header>

      <main>
        {/* 기간별 수익률.
            자료가 없는 기간은 '—' 로 둡니다. 억지로 숫자를 만들면 1개월
            수익률이 3년 전 값으로 계산되는 일이 생깁니다. */}
        <div className="stats">
          {PERIODS.map((p, i) => {
            const v = stock.returns[i];
            return (
              <div className="stat" key={p.label}>
                <div className="stat-k">{p.label}</div>
                {v === null ? (
                  <div className="stat-v none" title="그만큼의 과거 자료가 아직 없습니다">—</div>
                ) : (
                  <div className={`stat-v n ${tone(v)}`}>{signed(v, 1)}%</div>
                )}
              </div>
            );
          })}
        </div>

        <PriceChart data={history} />

        <div className="facts">
          <Fact k="시가총액" v={eok(stock.market_cap)} />
          <Fact k="PER" v={stock.per && stock.per > 0 ? num(stock.per, 2) : ""} />
          <Fact k="PBR" v={stock.pbr ? num(stock.pbr, 2) : ""} />
          <Fact k="배당수익률" v={stock.div_yield ? `${num(stock.div_yield, 2)}%` : ""} />
          <Fact k="ROE" v={stock.roe !== null ? `${num(stock.roe, 2)}%` : ""} />
          <Fact k="부채비율" v={stock.debt_ratio !== null ? `${num(stock.debt_ratio, 0)}%` : ""} />
        </div>

        <div className="sec-h">
          <h2>관련 뉴스</h2>
          <span>네이버 뉴스</span>
        </div>
        <NewsList
          articles={news}
          ready={newsReady()}
          empty={`최근 '${stock.name}' 이야기를 다룬 기사를 찾지 못했습니다. 이름이 짧거나 비슷한 회사가 많으면 확실한 것만 남기느라 비어 있을 수 있습니다.`}
        />

        <p className="foot">
          PER·PBR·배당수익률은 한국거래소, ROE·부채비율은 DART 전자공시 기준입니다.
          ETF 는 재무제표가 없어 빈칸입니다. 빈칸은 &lsquo;0&rsquo; 이 아니라
          &lsquo;아직 자료가 없다&rsquo;는 뜻입니다.
        </p>
      </main>
    </div>
  );
}

/** 값이 없으면 '—'. 빈칸보다 '없다'는 것이 분명해 보입니다. */
function Fact({ k, v }: { k: string; v: string }) {
  return (
    <div className="fact">
      <div className="fact-k">{k}</div>
      {v ? <div className="fact-v n">{v}</div> : <div className="fact-v none">—</div>}
    </div>
  );
}
