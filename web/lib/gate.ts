/**
 * 모의투자 화면을 아무나 못 건드리게 막는 자물쇠.
 *
 * ★ 왜 필요한가 ★
 *   보는 화면은 열려 있어도 됩니다. 시세와 공시는 공개된 자료입니다.
 *   그런데 모의투자는 **쓰는** 화면입니다. 주소만 알면 아무나
 *   남의 연습 기록을 사고팔고 지울 수 있으면 안 됩니다.
 *   게다가 창고가 500MB 중 444MB 를 쓰고 있어서, 지나가는 사람이
 *   기록을 만들기 시작하면 용량도 문제가 됩니다.
 *
 * ★ 왜 이렇게 간단한가 ★
 *   혼자 쓰는 연습장입니다. 아이디·비밀번호·이메일 인증까지 갖추면
 *   만들 것도 많고 개인정보도 떠안게 됩니다. 여기서 지켜야 할 것은
 *   '나 말고 아무나 손대지 못하게' 하나뿐이라, 암호 한 개로 충분합니다.
 *
 * ★ 암호를 어떻게 넣나 ★
 *   Vercel > 프로젝트 > Settings > Environment Variables 에
 *   PAPER_PASSCODE 를 넣으면 됩니다. 안 넣으면 모의투자 화면이
 *   아예 잠깁니다(열어두는 것보다 잠그는 쪽이 안전합니다).
 */
import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "crypto";

const COOKIE = "paper";
/** 한 번 들어오면 30일은 다시 안 묻습니다. 휴대폰에서 매번 치기 번거롭습니다. */
const DAYS = 30;

const passcode = (): string => process.env.PAPER_PASSCODE ?? "";

/** 암호가 아예 설정되지 않았으면 화면에서 안내를 다르게 냅니다. */
export const gateReady = (): boolean => passcode().length > 0;

/**
 * 쿠키에 넣을 표. 암호를 그대로 넣지 않고 서명값을 넣습니다.
 * 쿠키는 사용자 기기에 저장되는 것이라 열어볼 수 있기 때문입니다.
 */
function sign(): string {
  return createHmac("sha256", passcode()).update("paper-v1").digest("hex");
}

/** 두 글자열을 견줄 때 길이·내용에 따라 걸리는 시간이 달라지지 않게 합니다. */
function same(a: string, b: string): boolean {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

/** 지금 이 사람이 들어와도 되는지. */
export async function allowed(): Promise<boolean> {
  if (!gateReady()) return false;
  const jar = await cookies();
  const got = jar.get(COOKIE)?.value ?? "";
  return got.length > 0 && same(got, sign());
}

/** 암호가 맞으면 표를 내줍니다. */
export async function unlock(input: string): Promise<boolean> {
  if (!gateReady()) return false;
  if (!same(input.trim(), passcode())) return false;
  const jar = await cookies();
  jar.set(COOKIE, sign(), {
    httpOnly: true, // 자바스크립트가 못 읽게
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: DAYS * 24 * 60 * 60,
  });
  return true;
}

export async function lock(): Promise<void> {
  const jar = await cookies();
  jar.delete(COOKIE);
}
