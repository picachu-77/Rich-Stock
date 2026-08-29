import type { Quarter } from "@/lib/trend";
import { num, tone } from "@/lib/format";

/**
 * 재무 추이 — 최근 분기들을 나란히.
 *
 * ★ 표로 둡니다 (선 그림이 아니라) ★
 *   점이 많아야 열 개 남짓이고, 값이 %라 눈금이 없으면 읽기 어렵습니다.
 *   무엇보다 초보자는 "그래서 몇 %인데?" 를 알고 싶어 합니다.
 *   숫자를 그대로 보여주는 편이 낫습니다.
 *
 * ★ 최근 것이 왼쪽이 아니라 오른쪽입니다 ★
 *   왼쪽에서 오른쪽으로 시간이 흐르는 것이 눈에 익습니다.
 *   가로로 넘겨 볼 수 있게 두고, 첫 칸(항목 이름)은 붙여 둡니다.
 */
const pct = (v: number | null) => (v === null ? "—" : `${num(v, 1)}%`);

export default function TrendTable({ rows }: { rows: Quarter[] }) {
  // 오래된 것부터 왼쪽. 화면이 좁으니 최근 8개까지만.
  const qs = rows.slice(-8);

  const line = (
    label: string,
    pick: (q: Quarter) => number | null,
    colorize = false,
  ) => (
    <tr>
      <th scope="row">{label}</th>
      {qs.map((q) => {
        const v = pick(q);
        return (
          <td key={`${q.year}-${q.quarter}`} className={colorize && v !== null ? tone(v) : ""}>
            <span className="n">{pct(v)}</span>
          </td>
        );
      })}
    </tr>
  );

  return (
    <>
      <div className="sec-h">
        <h2>재무 흐름</h2>
        <span>한 시점보다 방향</span>
      </div>
      <div className="tt-wrap">
        <table className="tt">
          <thead>
            <tr>
              <th scope="col">
                <span className="tt-corner" />
              </th>
              {qs.map((q) => (
                <th key={`${q.year}-${q.quarter}`} scope="col">
                  <span className="n">{String(q.year).slice(2)}</span>
                  <br />
                  {q.quarter === 0
                    ? "최근"
                    : q.quarter === 4
                      ? "연간"
                      : q.quarter === 2
                        ? "반기"
                        : `${q.quarter}Q`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {line("ROE", (q) => q.roe, true)}
            {line("영업이익률", (q) => q.opMargin, true)}
            {line("부채비율", (q) => q.debt)}
          </tbody>
        </table>
      </div>
      <p className="tt-note">
        ROE 는 자기 돈으로 얼마나 벌었는지, 영업이익률은 판 돈 중 얼마가 남았는지,
        부채비율은 빚이 자기 돈의 몇 %인지입니다. <b>계절을 타는 회사가 많아
        작년 같은 분기와 견주는 편이 낫습니다</b> — 4분기와 1분기를 나란히 놓고
        늘었다·줄었다 하면 틀린 말이 됩니다.
      </p>
    </>
  );
}
