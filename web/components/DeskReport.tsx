import type { DeskReport as Report } from "@/lib/desk";
import { DESKS } from "@/lib/desk";

/**
 * 여섯 부서의 보고서.
 *
 * ★ 운용부 결론을 맨 위에, 나머지는 접어둡니다 ★
 *   다섯 편을 다 펼쳐두면 아무도 안 읽습니다. 결론과 '무너지는 조건'
 *   부터 보이고, 근거가 궁금하면 부서를 눌러 펴게 합니다.
 *
 * ★ 리스크관리부를 운용부 바로 다음에 둡니다 ★
 *   순서가 곧 메시지입니다. 반대 의견이 맨 아래 있으면 안 읽힙니다.
 *
 * ★ 의견에 색을 쓰지 않습니다 ★
 *   '관심' 을 빨갛게 칠하면 '오른다' 로 읽힙니다. 이건 시세가 아니라
 *   판단입니다. 진한 색은 이 앱에서 시세에만 씁니다.
 */
const 설명: Record<string, string> = {
  기술적분석부: "차트와 추세, 거래",
  펀더멘탈부: "실적과 값어치",
  마켓부: "시장 국면과 그 회사에 생긴 일",
  리스크관리부: "앞 부서에 반대하고 잃을 거리를 찾습니다",
  운용부: "넷을 모은 결론",
};

export default function DeskReport({ report }: { report: Report | null }) {
  if (!report) return null;

  const 결론 = report.reports.운용부;
  const 나머지 = DESKS.filter((d) => d !== "운용부" && report.reports[d]);
  const 오래됨 = report.daysAgo >= 7;

  return (
    <>
      <div className="sec-h">
        <h2>여섯 부서</h2>
        <span>
          <span className="n">{report.createdAt}</span> 작성
        </span>
      </div>

      {/* 언제 쓴 것인지를 먼저 말합니다. 오래된 보고서는 그렇다고
          분명히 적습니다 — 그 사이에 실적이 나왔을 수 있습니다. */}
      {오래됨 && (
        <p className="dk-old">
          <b className="n">{report.daysAgo}일</b> 전에 쓴 보고서입니다. 그 사이
          시세와 실적이 바뀌었을 수 있습니다.
        </p>
      )}

      {결론 && (
        <div className="dk-top">
          <div className="dk-top-h">
            <span className="dk-desk">운용부</span>
            {/* 장기와 단기를 따로 보여줍니다. 같은 회사가 장기로는
                관심이고 단기로는 보류일 수 있습니다. */}
            {report.verdictLong && (
              <span className="dk-verdict">
                <i>장기</i>
                {report.verdictLong}
              </span>
            )}
            {report.verdictShort && (
              <span className="dk-verdict">
                <i>단기</i>
                {report.verdictShort}
              </span>
            )}
          </div>
          <div className="dk-body">{결론}</div>
        </div>
      )}

      <div className="dk-list">
        {나머지.map((name) => (
          <details className="dk" key={name}>
            <summary>
              <span className="dk-desk">{name}</span>
              <span className="dk-note">{설명[name]}</span>
            </summary>
            <div className="dk-body">{report.reports[name]}</div>
          </details>
        ))}
      </div>

      <p className="foot">
        AI 가 창고에 있는 자료만 보고 쓴 글입니다. <b>사라는 말이 아닙니다.</b>{" "}
        틀릴 수 있고, 자료에 없는 것은 보지 못합니다. 원문(공시·리포트)을
        직접 확인하세요.
        {report.models && (
          <>
            {" "}
            <span className="n">{report.models}</span> 로 썼습니다.
          </>
        )}
      </p>
    </>
  );
}
