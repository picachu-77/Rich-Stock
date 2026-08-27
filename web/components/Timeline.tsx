import type { Event } from "@/lib/paper";
import { unpackReason } from "@/lib/paper";
import { num, signed, tone } from "@/lib/format";

/**
 * 여태 한 일을 한 줄씩, 최근 것부터.
 *
 * 지금 가진 것과 판 것만 보면 '무엇을 해왔는지' 가 사라집니다.
 * 같은 종목을 세 번 나눠 산 것은 평균단가 하나로 뭉쳐져 흔적이 없습니다.
 * 연습은 쌓인 것을 되돌아보는 일이라, 한 일은 한 일대로 남아 있어야 합니다.
 */
const won = (v: number) => `${num(Math.round(v))}원`;

export default function Timeline({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return <p className="news-none">아직 한 일이 없습니다.</p>;
  }

  let 앞날짜 = "";
  return (
    <ul className="tl">
      {events.map((e) => {
        const 새날 = e.date !== 앞날짜;
        앞날짜 = e.date;
        return (
          <li key={`${e.kind}-${e.id}`}>
            <span className="tl-d n">{새날 ? e.date : ""}</span>
            <span className="tl-b">{row(e)}</span>
          </li>
        );
      })}
    </ul>
  );
}

function row(e: Event) {
  if (e.kind === "CASH") {
    return (
      <>
        <b className="tl-t">
          {e.amount > 0 ? "돈을 넣었습니다" : "돈을 뺐습니다"}{" "}
          <span className="n">{won(Math.abs(e.amount))}</span>
        </b>
        {e.memo && <span className="tl-m">{e.memo}</span>}
      </>
    );
  }

  const r = unpackReason(e.reason);
  const 금액 = e.qty * e.price;
  const 실제 = e.kind === "BUY" ? 금액 + e.fee : 금액 - e.fee - e.tax;

  return (
    <>
      <b className="tl-t">
        <span className={e.kind === "BUY" ? "up" : "down"}>
          {e.kind === "BUY" ? "샀습니다" : "팔았습니다"}
        </span>{" "}
        {e.name} <span className="n">{num(e.qty)}주</span>
      </b>
      <span className="tl-m n">
        {won(e.price)} × {num(e.qty)}주 ={" "}
        {e.kind === "BUY" ? `${won(실제)} 나감` : `${won(실제)} 들어옴`}
      </span>
      {r.kind && (
        <span className="tl-m">
          {r.kind}
          {r.memo && ` — ${r.memo}`}
          {e.kind === "BUY" && e.target !== null && (
            <>
              {" "}
              · 목표 <span className="n">{won(e.target)}</span>
              {e.stop !== null && (
                <>
                  {" "}
                  · 손절 <span className="n">{won(e.stop)}</span>
                </>
              )}
            </>
          )}
        </span>
      )}
    </>
  );
}
