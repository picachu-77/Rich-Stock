import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

/**
 * 숫자 전용 글꼴.
 *
 * 한글은 휴대폰에 이미 있는 글꼴을 씁니다. 한글 웹폰트는 글자가 수천 자라
 * 몇 MB 를 내려받아야 해서, 화면이 늦게 뜨는 문제를 더 키웁니다.
 *
 * 대신 숫자만 이 글꼴로 받습니다. 라틴 문자만 받으면 20KB 안팎입니다.
 *   · 폭이 일정해서 목록을 훑을 때 자릿수가 흔들리지 않습니다
 *   · 시세판 같은 인상을 줍니다 — 이 화면의 주인공은 숫자입니다
 */
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "국내주식",
  description: "코스피·코스닥 전 종목 시세와 수익률",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "국내주식" },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // 확대를 막지 않습니다. 글씨를 키워 봐야 하는 분이 있습니다.
  maximumScale: 5,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fcfcfa" },
    { media: "(prefers-color-scheme: dark)", color: "#0e0f12" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={mono.variable}>
      <body>{children}</body>
    </html>
  );
}
