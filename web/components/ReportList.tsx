import type { Report } from "@/lib/reports";
import { num } from "@/lib/format";

/**
 * 증권사 리포트 목록.
 *
 * ★ 원문은 한경컨센서스로 보냅니다 ★
 *   우리는 '이런 것이 나왔다' 만 알려줍니다. 남의 보고서를 퍼 나르지
 *   않습니다. 공시를 다루는 방식과 같습니다.
 */
export default function ReportList({
  items,
  empty,
  showName = false,
}: {
  items: Report[];
  empty: string;
  /** 종목 이름을 함께 보여줄지 (여러 종목이 섞인 목록에서) */
  showName?: boolean;
}) {
  if (items.length === 0) {
    return <div className="empty">{empty}</div>;
  }

  return (
    <div className="rp-list">
      {items.map((r) => (
        <a
          key={r.id}
          className="rp"
          href={r.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <div className="rp-top">
            {showName && r.name && <span className="rp-name">{r.name}</span>}
            {r.kind !== "기업" && <span className="tag">{r.kind}</span>}
            {r.opinion && (
              <span className={`rp-op ${opClass(r.opinion)}`}>{r.opinion}</span>
            )}
          </div>

          <div className="rp-title">{r.title}</div>

          <div className="rp-sub">
            {r.targetPrice !== null && (
              <span>
                목표 <b className="n">{num(r.targetPrice)}원</b>
              </span>
            )}
            {r.house && <span>{r.house}</span>}
            <span className="n">{r.writtenAt.slice(5).replace("-", "월 ")}일</span>
          </div>
        </a>
      ))}
    </div>
  );
}

/**
 * 의견에 따른 꾸밈.
 *
 * ★ 매수를 빨갛게 하지 않습니다 ★
 *   이 화면에서 빨강은 '올랐다' 입니다. 매수 의견을 빨갛게 하면
 *   '이 종목이 올랐다' 와 같은 색이 되어 눈이 헷갈립니다.
 *   그리고 거의 다 매수라, 온 화면이 빨개지면 아무 뜻도 없어집니다.
 *   드문 것(매도·중립)만 눈에 띄게 합니다.
 */
function opClass(op: string): string {
  if (op === "매도") return "sell";
  if (op === "중립") return "hold";
  if (op === "의견없음") return "none";
  return "buy";
}
