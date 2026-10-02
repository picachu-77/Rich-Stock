import Link from "next/link";
import { getPicks } from "@/lib/desk";
import { num, price, signed, tone } from "@/lib/format";

/**
 * 리서치 — 여섯 부서가 추린 종목을 증권사 리포트처럼.
 *
 * ★ 왜 장기와 단기를 나누나 ★
 *   같은 회사가 장기로는 좋고 단기로는 들어갈 자리가 아닐 수 있고,
 *   그 반대도 됩니다. 한 줄로 뭉뚱그리면 둘 다 틀립니다.
 *   찾는 것부터가 다릅니다 —
 *     장기: 실적이 꾸준히 늘고, 빚이 적고, 값이 과하지 않은 회사
 *     단기: 최근 흐름과 거래가 살아난 회사
 *
 * ★ '관심' 만 올리지 않습니다 ★
 *   보류·제외도 같이 보여줍니다. 추린 것만 보여주면 "AI 가 고른
 *   종목" 이 되고, 그건 이 앱이 하려던 일과 정반대입니다. 무엇을
 *   왜 걸렀는지가 보여야 판단을 배웁니다.
 */
export const revalidate = 1800;

const 순서 = { 관심: 0, 보류: 1, 제외: 2 } as const;
const 등급 = (v: string | null) => 순서[(v ?? "") as keyof typeof 순서] ?? 3;

export default async function ResearchPage() {
  const picks = await getPicks();

  const 장기 = [...picks]
    .filter((p) => p.verdictLong)
    .sort((a, b) => 등급(a.verdictLong) - 등급(b.verdictLong));
  const 단기 = [...picks]
    .filter((p) => p.verdictShort)
    .sort((a, b) => 등급(a.verdictShort) - 등급(b.verdictShort));

  const 최신 = picks.length
    ? picks.reduce((a, b) => (a.createdAt > b.createdAt ? a : b)).createdAt
    : null;

  const 칸 = (
    제목: string,
    설명: string,
    목록: typeof picks,
    쪽: "long" | "short",
  ) => (
    <section className="rs-sec">
      <div className="rs-h">
        <h2>{제목}</h2>
        <span>{설명}</span>
      </div>
      {목록.length === 0 ? (
        <p className="rs-none">아직 추린 종목이 없습니다.</p>
      ) : (
        <div className="rs-list">
          {목록.map((p) => {
            const 의견 = 쪽 === "long" ? p.verdictLong : p.verdictShort;
            const 이유 = 쪽 === "long" ? p.reasonLong : p.reasonShort;
            return (
              <Link key={p.code} href={`/stock/${p.code}`} className="rs">
                <div className="rs-top">
                  <span className="rs-name">{p.name}</span>
                  <span className="rs-code n">{p.code}</span>
                  <span className={`rs-verdict v-${의견}`}>{의견}</span>
                </div>
                {이유 && <p className="rs-why">{이유}</p>}
                <div className="rs-sub">
                  {p.sector && <span>{p.sector}</span>}
                  {p.close !== null && (
                    <span className="n">{price(p.close, "KRW")}</span>
                  )}
                  {p.changePct !== null && (
                    <span className={`n ${tone(p.changePct)}`}>
                      {signed(p.changePct)}%
                    </span>
                  )}
                  <span className="n">{p.createdAt}</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );

  return (
    <div className="wrap">
      <header className="head">
        <div className="head-top">
          <h1>리서치</h1>
          {최신 && <span className="head-date n">{최신}</span>}
        </div>
        <p className="rs-intro">
          여섯 부서가 나눠 보고 모은 결과입니다. <b>장기</b>와 <b>단기</b>는
          찾는 것부터 다릅니다 — 같은 회사가 한쪽은 관심이고 다른 쪽은
          보류일 수 있습니다.
        </p>
      </header>

      <main>
        {picks.length === 0 ? (
          <div className="empty">
            <b>아직 리포트가 없습니다</b>
            여섯 부서를 한 번도 돌리지 않았거나, 최근 30일 사이에 쓴 것이
            없습니다.
          </div>
        ) : (
          <>
            {칸("장기", "몇 년 들고 있을 회사", 장기, "long")}
            {칸("단기", "지금 흐름이 살아 있는 회사", 단기, "short")}
          </>
        )}

        <p className="foot">
          AI 가 창고에 있는 자료만 보고 쓴 글입니다. <b>사라는 말이 아닙니다.</b>{" "}
          <b>관심</b>은 &lsquo;더 알아볼 값어치가 있다&rsquo;, <b>보류</b>는
          &lsquo;판단할 근거가 모자라다&rsquo;, <b>제외</b>는 &lsquo;지금 보기에
          안 맞는다&rsquo;는 뜻입니다. 종목을 눌러 부서별 보고서와 반대
          의견까지 읽어보세요.
        </p>
      </main>
    </div>
  );
}
