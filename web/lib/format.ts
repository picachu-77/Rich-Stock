/**
 * 숫자를 사람이 읽기 좋게 바꿉니다.
 *
 * 규칙 하나: **모든 숫자에 자릿수 구분기호를 넣습니다.**
 * 1000000 은 자릿수를 세어야 알 수 있지만 1,000,000 은 한눈에 들어옵니다.
 * 값이 없으면 빈 글자로 둡니다. 'null' 이나 '-' 가 찍히면 오류처럼 보입니다.
 */

export const num = (v: number | null | undefined, digits = 0): string =>
  v === null || v === undefined || Number.isNaN(v)
    ? ""
    : v.toLocaleString("ko-KR", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

export const won = (v: number | null | undefined, digits = 0): string =>
  v === null || v === undefined || Number.isNaN(v) ? "" : `${num(v, digits)}원`;

/**
 * 시세 한 줄. 나라마다 돈 단위가 달라서 기호를 함께 붙입니다.
 *
 * 미국 종목은 달러가 진짜 시세입니다. 원화 값은 그날 환율로 바꾼
 * 어림값이라, 그것만 보여주면 실제로 주문할 때 나오는 숫자와 달라
 * 헷갈립니다.
 */
export const price = (
  v: number | null | undefined,
  currency = "KRW",
): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  return currency === "USD" ? `$${num(v, 2)}` : num(v);
};

/** 부호가 중요한 값(등락률·수익률)은 + 를 붙여 방향이 바로 보이게 합니다. */
export const signed = (v: number | null | undefined, digits = 2): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  const s = v.toLocaleString("ko-KR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return v > 0 ? `+${s}` : s;
};

/**
 * 큰 금액을 '조/억' 으로 읽어줍니다. (시가총액용)
 * 들어오는 값의 단위는 '억원' 입니다.
 */
export const eok = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  if (v >= 10000) {
    const 조 = Math.floor(v / 10000);
    const 억 = Math.round(v % 10000);
    return 억 ? `${num(조)}조 ${num(억)}억` : `${num(조)}조`;
  }
  return `${num(Math.round(v))}억`;
};

/** 오름/내림에 따라 색을 고릅니다. (한국은 오르면 빨강, 내리면 파랑) */
export const tone = (v: number | null | undefined): string =>
  v === null || v === undefined || Number.isNaN(v)
    ? "flat"
    : v > 0
      ? "up"
      : v < 0
        ? "down"
        : "flat";

/**
 * 상한가·하한가인지.
 *
 * 한국 증시는 하루에 오르내릴 수 있는 폭이 ±30% 로 정해져 있습니다.
 * 그 끝에 닿은 것은 보통 일이 아니라서 따로 표시해 줍니다.
 *
 * ★ 미국 종목에는 이 표시를 쓰면 안 됩니다 ★
 *   미국 증시에는 이런 상·하한이 없습니다. 하루에 40% 오르는 일이
 *   실제로 있고, 그것을 '상한가' 라고 부르면 틀린 말입니다.
 *   그래서 돈 단위가 원인 종목에만 붙입니다.
 */
export const limitHit = (
  v: number | null | undefined,
  currency = "KRW",
): "up" | "down" | null => {
  if (currency !== "KRW") return null;
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  if (v >= 29.5) return "up";
  if (v <= -29.5) return "down";
  return null;
};

/**
 * 등락 막대의 길이(%).
 *
 * ±5% 를 꽉 찬 길이로 봅니다. 대부분의 날은 ±3% 안쪽이라, ±30% 를 기준으로
 * 삼으면 거의 모든 막대가 점처럼 보여서 아무것도 알 수 없습니다.
 * 5% 를 넘는 큰 움직임은 막대가 끝까지 찬 것으로 보여주고, 정확한 값은
 * 옆의 숫자가 알려줍니다.
 */
export const railWidth = (v: number | null | undefined): number => {
  if (v === null || v === undefined || Number.isNaN(v)) return 0;
  return Math.min(Math.abs(v) / 5, 1) * 50; // 가운데 기준이라 최대 50%
};
