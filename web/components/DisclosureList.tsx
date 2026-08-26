import {
  categoryLabel,
  dartUrl,
  daysAgo,
  isWarning,
  type Disclosure,
} from "@/lib/disclosures";

/**
 * 공시 몇 줄.
 *
 * ★ 갈래를 제목보다 먼저 보여줍니다 ★
 *   '주요사항보고서(유상증자결정)' 같은 제목은 익숙하지 않으면 무슨 뜻인지
 *   알기 어렵습니다. 그래서 '돈을 구합니다' 를 앞에 두고 원래 제목을
 *   그 아래에 둡니다. 뜻을 먼저 읽고 정확한 이름을 확인하는 순서입니다.
 *
 * ★ 색은 '조심할 일' 에만 씁니다 ★
 *   이 화면에서 빨강은 '올랐다' 라는 뜻입니다. 공시에까지 색을 뿌리면
 *   그 약속이 깨집니다. 다만 횡령·상장폐지·감사의견거절 같은 것은
 *   놓치면 안 되므로 이것만 표시를 답니다.
 */
export default function DisclosureList({
  items,
  empty,
  showName = false,
}: {
  items: Disclosure[];
  /** 공시가 없을 때 보여줄 말 */
  empty: string;
  /** 첫 화면처럼 여러 종목이 섞여 나올 때는 종목 이름도 보여줍니다. */
  showName?: boolean;
}) {
  if (items.length === 0) {
    return <p className="news-none">{empty}</p>;
  }

  return (
    <ul className="news">
      {items.map((d) => (
        <li key={d.id}>
          {/* 원문은 DART 에서 봅니다. 공시는 반드시 원문을 볼 수 있어야
              합니다 — 저희가 붙인 갈래는 제목을 보고 짐작한 것입니다. */}
          <a href={dartUrl(d.id)} target="_blank" rel="noopener noreferrer">
            <span className="dc-top">
              {showName && <b className="dc-name">{d.name}</b>}
              <span className={isWarning(d.category) ? "dc-cat warn" : "dc-cat"}>
                {categoryLabel(d.category)}
              </span>
            </span>
            <span className="news-t">{d.title}</span>
            <span className="news-m">
              <time dateTime={d.at.toISOString().slice(0, 10)}>
                {daysAgo(d.at)}
              </time>
              <i aria-hidden="true">·</i>
              전자공시
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}
