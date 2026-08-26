/**
 * 데이터베이스(Supabase) 접속 담당.
 *
 * 왜 Supabase 라이브러리 대신 Postgres 로 직접 붙나요?
 *   기간별 수익률을 구할 때 LATERAL JOIN 이라는 문법을 씁니다.
 *   ("1개월 전 종가를 종목마다 하나씩 찾아 붙이기")
 *   Supabase 의 자동 API 로는 이 문법을 표현할 수 없어서,
 *   파이썬 화면에서 쓰던 SQL 을 그대로 쓰려고 직접 붙습니다.
 *
 * 연결 문자열은 Session pooler 주소를 씁니다.
 *   Vercel 은 요청마다 서버를 새로 띄우는 구조라 연결이 자주 생겼다
 *   없어집니다. pooler 가 그 사이에서 연결을 모아 관리해 줍니다.
 */
import postgres from "postgres";

const url = process.env.DATABASE_URL;

if (!url) {
  throw new Error(
    "DATABASE_URL 이 없습니다.\n" +
      "Vercel > 프로젝트 > Settings > Environment Variables 에\n" +
      "Supabase 의 Session pooler 연결 문자열을 넣어주세요.",
  );
}

// 전역에 담아두는 이유:
//   개발 중에 파일을 고칠 때마다 모듈이 새로 읽히는데, 그때마다 연결을
//   새로 만들면 연결이 쌓여서 한도를 넘깁니다.
const globalForDb = globalThis as unknown as { sql?: postgres.Sql };

export const sql =
  globalForDb.sql ??
  postgres(url, {
    // Vercel 함수 하나가 동시에 여러 연결을 쥐지 않도록 적게 둡니다.
    max: 3,
    idle_timeout: 20,
    connect_timeout: 15,
    // pooler 를 거치므로 준비된 구문(prepared statement)은 쓰지 않습니다.
    prepare: false,
  });

if (process.env.NODE_ENV !== "production") globalForDb.sql = sql;
