import Link from "next/link";
import { notFound } from "next/navigation";
import PriceChart from "@/components/PriceChart";
import { getHistory, getStock } from "@/lib/stocks";
import { PERIODS } from "@/lib/periods";
import { eok, num, signed, tone, won } from "@/lib/format";

export const revalidate = 3600;

export default async function StockPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const [stock, history] = await Promise.all([getStock(code), getHistory(code)]);
  if (!stock) notFound();

  return (
    <>
      <header className="top">
        <div className="top-in">
          <Link href="/" className="back">← 목록으로</Link>
          <h1 className="title" style={{ marginTop: 2 }}>{stock.name}</h1>
          <div className="sub tnum">
            {stock.code} · {stock.kind === "ETF" ? "ETF" : stock.market}
            {stock.trade_date ? ` · ${stock.trade_date} 기준` : ""}
          </div>
        </div>
      </header>

      <main className="wrap">
        <div className="card-mid" style={{ margin: "12px 0 4px" }}>
          <span className="card-price tnum" style={{ fontSize: "1.5rem" }}>
            {won(stock.close)}
          </span>
          <span className={`card-chg tnum ${tone(stock.change_pct)}`}
                style={{ fontSize: "1rem" }}>
            {signed(stock.change_pct)}
            {stock.change_pct !== null ? "%" : ""}
          </span>
        </div>

        {/* ── 기간별 수익률 ──
            자료가 없는 기간은 '—' 로 둡니다. 억지로 숫자를 만들면
            1개월 수익률이 3년 전 값으로 계산되는 일이 생깁니다. */}
        <div className="metrics">
          {PERIODS.map((p, i) => {
            const v = stock.returns[i];
            return (
              <div className="metric" key={p.label}>
                <div className="metric-l">{p.label}</div>
                {v === null ? (
                  <div className="metric-v none" title="그만큼의 과거 자료가 아직 없습니다">
                    —
                  </div>
                ) : (
                  <div className={`metric-v tnum ${tone(v)}`}>
                    {signed(v)}%
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <PriceChart data={history} />

        <div className="metrics" style={{ marginTop: 16 }}>
          <Cell label="시가총액" value={eok(stock.market_cap)} />
          <Cell label="PER" value={stock.per && stock.per > 0 ? num(stock.per, 2) : ""} />
          <Cell label="PBR" value={stock.pbr ? num(stock.pbr, 2) : ""} />
          <Cell label="배당수익률" value={stock.div_yield ? `${num(stock.div_yield, 2)}%` : ""} />
          <Cell label="ROE" value={stock.roe !== null ? `${num(stock.roe, 2)}%` : ""} />
          <Cell label="부채비율" value={stock.debt_ratio !== null ? `${num(stock.debt_ratio, 0)}%` : ""} />
        </div>

        <div style={{ fontSize: ".78rem", color: "#98a2b3", marginTop: 12 }}>
          PER·PBR·배당수익률은 한국거래소, ROE·부채비율은 DART 전자공시 기준입니다.
          ETF 는 재무제표가 없어 빈칸입니다.
        </div>
      </main>
    </>
  );
}

/** 값이 없으면 '—' 로 둡니다. 빈칸보다 '없다' 는 것이 분명해 보입니다. */
function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-l">{label}</div>
      {value ? (
        <div className="metric-v tnum">{value}</div>
      ) : (
        <div className="metric-v none">—</div>
      )}
    </div>
  );
}
