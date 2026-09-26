import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import TabBar from "@/components/TabBar";

/**
 * 숫자 전용 글꼴.
 *
 * 폭이 일정해서 목록을 훑을 때 자릿수가 흔들리지 않습니다. 이 화면의
 * 주인공은 숫자라, 숫자만 따로 이 글꼴로 받습니다. 라틴 문자만 받으면
 * 20KB 안팎입니다.
 *
 * 한글은 IBM Plex Sans KR 을 씁니다 (globals.css). 같은 집안이라 뼈대와
 * 글자 높이가 맞아서, 한글과 숫자가 한 줄에 섞여도 어긋나 보이지
 * 않습니다. 한글 웹폰트는 원래 몇 MB 짜리지만, 글자마다 쪼개 받는
 * 방식이라 화면에 실제로 쓰인 몫만 옵니다.
 *
 * 두 글꼴 모두 굵기가 700 까지입니다. 그보다 굵게 적으면 브라우저가
 * 억지로 굵혀 그려서 한글이 번져 보입니다 — 그래서 700 을 넘기지
 * 않습니다.
 */
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "주식",
  description: "한국·미국 주식 시세·재무·공시·리포트와 모의투자",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "주식" },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // 확대를 막지 않습니다. 글씨를 키워 봐야 하는 분이 있습니다.
  maximumScale: 5,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f1e7" },
    { media: "(prefers-color-scheme: dark)", color: "#222831" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={mono.variable}>
      <head>
        {/* 한글 글꼴. 글자마다 쪼개 받기라 화면에 쓰인 글자 몫만
            내려받습니다. display=swap 이라 글꼴이 늦어도 글은 먼저
            뜹니다 — 빈 화면을 보여주지 않습니다. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap"
        />
      </head>
      <body>
        {children}
        <TabBar />
      </body>
    </html>
  );
}
