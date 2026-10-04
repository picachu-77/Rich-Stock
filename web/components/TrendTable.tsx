import type { Change, Quarter } from "@/lib/trend";
import { eok, num, tone } from "@/lib/format";

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
const dirClass = (c: Change) =>
  c === null ? "" : c.dir > 0 ? "up" : c.dir < 0 ? "down" : "flat";

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

  /**
   * 금액 줄. 숫자 아래에 작년 같은 분기와 견준 말을 붙입니다.
   *
   * ★ 왜 같은 칸에 붙이나 ★
   *   증감을 따로 한 줄로 빼면 표가 두 배로 길어지고, 눈이 위아래로
   *   오가며 짝을 맞춰야 합니다. 숫자 바로 밑에 있으면 한 번에 읽힙니다.
   */
  const money = (
    label: string,
    pick: (q: Quarter) => number | null,
    change: (q: Quarter) => Change,
  ) => (
    <tr>
      <th scope="row">{label}</th>
      {qs.map((q) => {
        const v = pick(q);
        const c = change(q);
        return (
          <td key={`${q.year}-${q.quarter}`}>
            <span className="n">{v === null ? "—" : eok(v)}</span>
            {c && <span className={`tt-yoy n ${dirClass(c)}`}>{c.text}</span>}
          </td>
        );
      })}
    </tr>
  );

  // 매출을 한 번도 못 받은 종목이 있습니다 (미국 종목은 야후가 비율만
  // 줍니다). 그럴 때 '—' 로만 찬 줄을 두 개 더 놓지 않습니다.
  const 금액있음 = qs.some((q) => q.revenue !== null || q.opProfit !== null);

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
            {/* 금액이 먼저입니다. '이 회사가 돈을 버는가, 늘고 있는가' 가
                가장 먼저 묻는 것이고, 비율은 그 다음 이야기입니다. */}
            {금액있음 && money("매출", (q) => q.revenue, (q) => q.revenueYoY)}
            {금액있음 && money("영업이익", (q) => q.opProfit, (q) => q.opProfitYoY)}
            {line("ROE", (q) => q.roe, true)}
            {line("영업이익률", (q) => q.opMargin, true)}
            {line("부채비율", (q) => q.debt)}
            {qs.some((q) => q.current !== null) && line("유동비율", (q) => q.current)}
          </tbody>
        </table>
      </div>
      <p className="tt-note">
        매출은 판 돈, 영업이익은 그중 남은 돈입니다. ROE 는 자기 돈으로 얼마나
        벌었는지, 영업이익률은 판 돈 중 얼마가 남았는지, 부채비율은 빚이 자기
        돈의 몇 %인지, 유동비율은 1년 안에 갚을 빚을 1년 안에 돈이 될
        자산으로 덮을 수 있는지입니다 — 100% 아래면 빠듯하다는 뜻입니다.
        {금액있음 && (
          <>
            {" "}
            매출·영업이익 아래 붙은 값은 <b>작년 같은 분기</b>와 견준 것입니다 —
            계절을 타는 회사가 많아, 4분기와 1분기를 나란히 놓고 늘었다·줄었다
            하면 틀린 말이 됩니다.
          </>
        )}
      </p>
    </>
  );
}
