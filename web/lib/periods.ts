/**
 * 기간별 수익률에 쓰는 값들. 파이썬 쪽 src/market_data.py 와 같은 규칙입니다.
 */

export const PERIODS = [
  { label: "1개월", interval: "1 month" },
  { label: "3개월", interval: "3 months" },
  { label: "6개월", interval: "6 months" },
  { label: "1년", interval: "1 year" },
  { label: "3년", interval: "3 years" },
] as const;

export type PeriodLabel = (typeof PERIODS)[number]["label"];

/**
 * '얼마나 옛날 값까지 N개월 전으로 인정할지' (14일)
 *
 * 이 제한이 없으면, 자료가 드문드문할 때 1개월·3개월·6개월·1년 수익률이
 * 모두 똑같은 값으로 나옵니다. 넷 다 몇 년 전 종가 하나를 보게 되기
 * 때문입니다. '1개월에 270% 올랐다' 같은 틀린 숫자가 나옵니다.
 *
 * 설·추석이 주말과 붙어도 쉬는 날은 일주일을 넘지 않으므로 14일이면
 * 넉넉합니다. 그보다 멀면 자료가 없는 것으로 보고 빈칸으로 둡니다.
 * → 파이썬 쪽 src/market_data.py 의 NEAR_DAYS 와 같은 값이어야 합니다.
 */
export const NEAR_DAYS = 14;
