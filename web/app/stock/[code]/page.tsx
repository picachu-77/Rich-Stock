import Link from "next/link";
import { notFound } from "next/navigation";
import PriceChart from "@/components/PriceChart";
import NewsList from "@/components/NewsList";
import DisclosureList from "@/components/DisclosureList";
import Fact from "@/components/Fact";
import TrendTable from "@/components/TrendTable";
import TargetCard from "@/components/TargetCard";
import DividendList from "@/components/DividendList";
import DeskReport from "@/components/DeskReport";
import Readout from "@/components/Readout";
import { getHistory, getStock } from "@/lib/stocks";
import { getStockNews, newsReady } from "@/lib/news";
import { getStockDisclosures } from "@/lib/disclosures";
import { getPeers, rankWord } from "@/lib/peers";
import { getTarget } from "@/lib/reports";
import { getDividends } from "@/lib/dividends";
import { getDeskReport } from "@/lib/desk";
import { getTrend } from "@/lib/trend";
import * as 설명 from "@/lib/explain";
import { readout } from "@/lib/readout";
import { PERIODS } from "@/lib/periods";
import { eok, flow, limitHit, num, price, signed, tone } from "@/lib/format";

export const revalidate = 3600;

export default async function StockPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const [stock, history] = await Promise.all([getStock(code), getHistory(code)]);
  if (!stock) notFound();

  // 공시는 창고에서 바로 읽습니다. 뉴스는 종목 이름으로 찾기 때문에
  // 종목을 확인한 뒤에 부릅니다. 둘 다 실패해도 이 화면은 열립니다.
  const [disclosures, news, peers, trend, target, dividends, desk] =
    await Promise.all([
    // 미국 회사는 DART(한국 전자공시) 대상이 아닙니다. 빈 목록을
    // 보여주면 '이 회사는 아무것도 신고하지 않았다' 로 읽혀 틀립니다.
    stock.currency === "USD"
      ? Promise.resolve([])
      : getStockDisclosures(stock.code),
    newsReady() ? getStockNews(stock.name) : Promise.resolve([]),
    // ETF 는 회사가 아니라 업종이 없고 재무제표도 없습니다.
    stock.kind === "ETF" ? Promise.resolve(null) : getPeers(stock.code),
    stock.kind === "ETF" ? Promise.resolve([]) : getTrend(stock.code),
    // ETF 와 미국 종목은 한경컨센서스 대상이 아닙니다.
    stock.kind === "ETF" || stock.currency === "USD"
      ? Promise.resolve(null)
      : getTarget(stock.code),
    // 미국 종목은 DART 공시 대상이 아닙니다.
    stock.currency === "USD" ? Promise.resolve([]) : getDividends(stock.code),
    getDeskReport(stock.code),
  ]);

  const dir = tone(stock.change_pct);

  /**
   * 그날 오간 돈 (거래대금).
   *
   * ★ 왜 거래량이 아니라 거래대금인가 ★
   *   '10만 주 거래' 는 그 종목이 500원짜리인지 50만원짜리인지에 따라
   *   5천만원일 수도, 500억일 수도 있습니다. 주식 수로는 많은지 적은지를
   *   알 수 없습니다.
   *
   * ★ 왜 이걸 봐야 하는가 ★
   *   초보자가 잘 모르고 다치는 곳입니다. 오가는 돈이 적은 종목은
   *   **팔고 싶을 때 제값에 못 팝니다.** 사는 것은 언제나 쉽지만 파는 것은
   *   상대가 있어야 합니다.
   */
  const 거래대금 =
    stock.volume !== null && stock.close !== null
      ? (stock.volume * stock.close) / 100_000_000   // 억 원
      : null;
  // 하루 1억원은 한국 시장에서 꽤 한산한 축입니다. 딱 잘라 '위험'이라고
  // 하지는 않고, 팔 때를 생각해보라고만 말합니다.
  const 한산함 = 거래대금 !== null && 거래대금 < 100;
  // 아래 '숫자' 칸에 빈칸이 하나라도 있는가
  const 빈칸있음 =
    stock.market_cap === null ||
    !(stock.per && stock.per > 0) ||
    !stock.pbr ||
    !stock.div_yield ||
    stock.roe === null ||
    stock.debt_ratio === null;
  const lim = limitHit(stock.change_pct, stock.currency);
  const 달러 = stock.currency === "USD";

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
            {달러
              ? (price(stock.close_local, "USD") || "—")
              : (stock.close === null ? "—" : num(stock.close))}
          </span>
          <span className={`n ${dir}`} style={{ fontSize: "1rem", fontWeight: 700 }}>
            {signed(stock.change_pct)}{stock.change_pct !== null && "%"}
            {lim && <span className={`limit ${lim}`}>{lim === "up" ? "상한가" : "하한가"}</span>}
          </span>
          <span style={{ fontSize: ".76rem", color: "var(--ink-3)", marginLeft: "auto" }}>
            <span className="n">{stock.trade_date}</span> 기준
          </span>
        </div>

        {거래대금 !== null && (
          <p className={`liq${한산함 ? " thin" : ""}`}>
            그날 오간 돈 <b className="n">{flow(거래대금)}</b>
            <span className="liq-x">
              (거래량 <span className="n">{num(stock.volume)}</span>주)
            </span>
            {한산함 && (
              <span className="liq-care">
                오가는 돈이 적은 편입니다. 이런 종목은 <b>팔고 싶을 때 제값에
                못 팔 수 있습니다</b> — 사는 것은 쉬워도 파는 것은 사줄 사람이
                있어야 합니다.
              </span>
            )}
          </p>
        )}

        {/* 미국 종목은 달러가 진짜 시세입니다. 원화는 그날 환율로 바꾼
            어림값이라, 그렇다고 밝혀 적습니다. 실제로 살 때는 증권사
            환율과 수수료가 붙어서 이 값과 조금 다릅니다. */}
        {달러 && stock.close !== null && (
          <p className="fx-note">
            원화로는 약 <b className="n">{num(stock.close)}원</b> 입니다
            (<span className="n">{stock.trade_date}</span> 환율 기준).
            아래 시가총액도 원화로 바꾼 값이고, <b>수익률과 등락률은 달러
            기준</b> 입니다 — 환율 움직임을 섞으면 이 회사가 얼마나 올랐는지가
            흐려집니다.
          </p>
        )}
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

        {/* 수익률도 설명이 필요합니다. '지난 수익률은 앞으로를
            알려주지 않는다' 는 것이 초보자가 가장 크게 다치는 지점입니다. */}
        <details className="hint">
          <summary>수익률이 무슨 뜻인가요?</summary>
          <div className="hint-x">
            <p>{설명.수익률().뜻}</p>
            <p>{설명.수익률().지금}</p>
            <p className="hint-care">
              <b>지난 수익률은 앞으로를 알려주지 않습니다.</b> 많이 오른 종목을
              보면 &lsquo;더 오르겠다&rsquo; 싶고 많이 내린 종목을 보면
              &lsquo;이제 오르겠다&rsquo; 싶어지는데, 둘 다 근거가 없습니다.
              왜 올랐는지·내렸는지를 봐야 합니다.
            </p>
          </div>
        </details>

        <PriceChart data={history} currency={stock.currency} />

        {/* 숫자를 보기 전에 먼저 읽어줍니다. 초보자는 숫자를 봐도
            무엇이 이상한지 모르기 때문에 순서가 중요합니다. */}
        <div className="sec-h">
          <h2>이 회사 읽어주기</h2>
          <span>숫자에서 눈에 띄는 것</span>
        </div>
        <Readout notes={readout(stock, disclosures, peers, trend)} />

        {/* 규칙이 읽어준 것 바로 다음에 둡니다. 둘 다 '읽어주기' 라
            같은 자리에 있어야 견줘 볼 수 있습니다. */}
        <DeskReport report={desk} />

        <div className="sec-h">
          <h2>숫자</h2>
          <span>{peers ? `${peers.used} ${num(peers.count)}곳과 견줌` : "눌러보세요"}</span>
        </div>
        <div className="facts">
          <Fact
            label="시가총액"
            value={eok(stock.market_cap)}
            explain={설명.시가총액(stock.market_cap)}
          />
          <Fact
            label="PER"
            value={stock.per && stock.per > 0 ? num(stock.per, 2) : ""}
            peer={peers?.per ?? null}
            explain={설명.PER(stock.per, stock.kind)}
          />
          <Fact
            label="PBR"
            value={stock.pbr ? num(stock.pbr, 2) : ""}
            peer={peers?.pbr ?? null}
            explain={설명.PBR(stock.pbr, stock.kind)}
          />
          <Fact
            label="배당수익률"
            value={stock.div_yield ? `${num(stock.div_yield, 2)}%` : ""}
            explain={설명.배당수익률(stock.div_yield)}
          />
          <Fact
            label="ROE"
            value={stock.roe !== null ? `${num(stock.roe, 2)}%` : ""}
            peer={peers?.roe ?? null}
            explain={설명.ROE(stock.roe, stock.kind)}
          />
          <Fact
            label="부채비율"
            value={stock.debt_ratio !== null ? `${num(stock.debt_ratio, 0)}%` : ""}
            peer={peers?.debt ?? null}
            explain={설명.부채비율(stock.debt_ratio, stock.kind)}
          />
        </div>

        {/* 공시가 먼저입니다. 회사가 직접 신고한 사실이라 기사보다
            정확합니다. 뉴스는 열쇠가 있을 때만 그 아래에 붙습니다. */}
        {trend.length >= 2 && <TrendTable rows={trend} />}

        {/* 회사 자체를 본 다음에 놓습니다. 남이 어떻게 보는지는 내가
            보고 난 뒤에 참고할 것이지, 먼저 볼 것이 아닙니다. */}
        {target && <TargetCard target={target} close={stock.close} />}

        {/* 배당은 '이 회사를 계속 들고 있을 것인가' 쪽 이야기라
            숫자·리포트 다음에 둡니다. */}
        <DividendList items={dividends} />

        {/* 보다가 바로 연습으로. 목록 3,931개에서 다시 찾게 하면
            보는 일과 연습하는 일이 끊깁니다. */}
        <Link href={`/practice?code=${stock.code}`} className="go-practice">
          <b>이 종목 연습으로 사보기</b>
          <span>진짜 돈은 쓰지 않습니다 — 왜 사는지 적어두고 나중에 되돌아봅니다</span>
        </Link>

        {달러 ? (
          <p className="foot" style={{ marginTop: 18 }}>
            미국 회사는 한국 전자공시(DART) 대상이 아닙니다. 미국 공시는
            SEC 의 EDGAR 에 올라옵니다.
          </p>
        ) : (
          <>
            <div className="sec-h">
              <h2>공시</h2>
              <span>전자공시(DART)</span>
            </div>
            <DisclosureList
              items={disclosures}
              empty={`최근 1년 사이 '${stock.name}' 이름으로 올라온 공시가 없습니다. ETF 는 회사가 아니라서 공시가 없습니다.`}
            />
          </>
        )}

        {newsReady() && (
          <>
            <div className="sec-h">
              <h2>관련 뉴스</h2>
              <span>네이버 뉴스</span>
            </div>
            <NewsList
              articles={news}
              ready
              empty={`최근 '${stock.name}' 이야기를 다룬 기사를 찾지 못했습니다. 이름이 짧거나 비슷한 회사가 많으면 확실한 것만 남기느라 비어 있을 수 있습니다.`}
            />
          </>
        )}

        {/* 빈칸의 뜻은 빈칸이 실제로 있을 때만 말합니다. 늘 적어두면
            빈칸이 하나도 없는 종목에서도 읽어야 하는 글이 됩니다. */}
        <p className="foot">
          {달러
            ? "야후 파이낸스 기준"
            : "PER·PBR·배당은 한국거래소, ROE·부채비율은 DART 기준"}
          {빈칸있음 && " · 빈칸은 0이 아니라 아직 자료가 없다는 뜻입니다"}
        </p>
      </main>
    </div>
  );
}
