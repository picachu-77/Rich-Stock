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
