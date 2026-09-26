/**
 * 종목을 이름·코드·초성으로 찾습니다.
 * 파이썬 쪽 src/search.py 와 같은 규칙입니다.
 */

const CHOSUNG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const HANGUL_START = 0xac00;
const HANGUL_END = 0xd7a3;

/** 글자에서 초성만 뽑아냅니다. ('삼성전자' → 'ㅅㅅㅈㅈ') */
export function chosungOf(text: string): string {
  let out = "";
  for (const ch of text) {
    const code = ch.codePointAt(0)!;
    if (code >= HANGUL_START && code <= HANGUL_END) {
      // 한글 한 글자는 '초성 19 × 중성 21 × 종성 28' 순서로 배열돼 있어서,
      // '가' 로부터 몇 번째인지를 588(=21×28)로 나누면 초성 번호가 나옵니다.
      out += CHOSUNG[Math.floor((code - HANGUL_START) / 588)];
    } else if (!/\s/.test(ch)) {
      out += ch;
    }
  }
  return out;
}

/** 검색어가 초성만으로 되어 있는지. ('ㅅㅅㅈㅈ' → true) */
export function isChosungQuery(q: string): boolean {
  const s = q.replace(/\s/g, "");
  return s.length > 0 && [...s].every((c) => CHOSUNG.includes(c));
}

const norm = (s: string) => s.replace(/\s/g, "").toUpperCase();

/**
 * 점수를 매겨 '그럴듯한 순서' 로 돌려줍니다.
 *   100 코드 정확 · 90 이름 정확 · 80 이름 시작 · 70 코드 시작
 *    60 이름 포함 · 50 초성 일치
 *    40 업종 정확 · 30 업종 포함
 *
 * ★ 업종으로도 찾습니다 ★
 *   '반도체' 라고 치면 반도체 회사가 다 나와야 합니다. 위에 고르는
 *   칸이 있긴 하지만, 업종 이름을 아는 사람은 그냥 치는 쪽이 빠릅니다.
 *   그리고 '반도체(집적회로)' 처럼 이름이 길어서 목록에서 찾기보다
 *   치는 편이 편할 때가 많습니다.
 *
 *   이름으로 맞은 것보다는 늘 뒤에 둡니다. '삼성전자' 를 쳤는데
 *   업종이 먼저 나오면 안 됩니다.
 *
 * 같은 점수끼리는 시가총액이 큰 회사를 먼저 보여줍니다.
 */
export function scoreOf(
  q: string,
  name: string,
  code: string,
  chosungCache?: string,
  sector?: string | null,
): number {
  const Q = norm(q);
  if (!Q) return 0;
  const N = norm(name);
  const C = norm(code);

  if (C === Q) return 100;
  if (N === Q) return 90;
  if (N.startsWith(Q)) return 80;
  if (C.startsWith(Q)) return 70;
  if (N.includes(Q)) return 60;
  if (isChosungQuery(q)) {
    const cho = chosungCache ?? chosungOf(name);
    if (cho.includes(Q)) return 50;
  }
  if (sector) {
    const S = norm(sector);
    if (S === Q) return 40;
    if (S.includes(Q)) return 30;
  }
  return 0;
}
