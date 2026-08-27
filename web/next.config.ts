import type { NextConfig } from "next";

/**
 * 시세는 하루에 한 번(밤 11시 수집)만 바뀝니다.
 * 그래서 화면을 미리 만들어 두고 1시간마다 다시 만듭니다.
 * 볼 때마다 데이터베이스에 물어보지 않으니 훨씬 빠릅니다.
 * (그 설정은 각 화면 파일의 `export const revalidate` 에 있습니다)
 */
const nextConfig: NextConfig = {
  /**
   * 사진 손질 기능을 끕니다.
   *
   * 이 사이트에는 사진이 한 장도 없습니다. next/image 를 쓰는 곳이
   * 없고, 아이콘도 글자로 그린 SVG 한 개뿐입니다. 그런데 이 설정을
   * 켜 둔 채로 두면 Next 는 '사진 크기를 줄여주는 일꾼'(/_next/image)
   * 을 결과물에 함께 넣고, 그 일꾼은 sharp 라는 무거운 꾸러미를
   * 함께 싣습니다. 쓰지도 않을 것을 올리느라 배포가 무거워집니다.
   */
  images: { unoptimized: true },
};

export default nextConfig;
