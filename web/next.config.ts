import type { NextConfig } from "next";

/**
 * 시세는 하루에 한 번(밤 11시 수집)만 바뀝니다.
 * 그래서 화면을 미리 만들어 두고 1시간마다 다시 만듭니다.
 * 볼 때마다 데이터베이스에 물어보지 않으니 훨씬 빠릅니다.
 * (그 설정은 각 화면 파일의 `export const revalidate` 에 있습니다)
 */
const nextConfig: NextConfig = {};

export default nextConfig;
