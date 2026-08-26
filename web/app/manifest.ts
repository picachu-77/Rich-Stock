import type { MetadataRoute } from "next";

/**
 * 홈화면에 추가했을 때 앱처럼 보이게 하는 설명서.
 * (Streamlit 으로는 할 수 없던 것입니다)
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "국내주식 대시보드",
    short_name: "주식",
    description: "코스피·코스닥 전 종목 시세와 수익률",
    start_url: "/",
    display: "standalone",
    background_color: "#f7f8fa",
    theme_color: "#f7f8fa",
    lang: "ko",
  };
}
