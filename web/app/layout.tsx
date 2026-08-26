import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "국내주식 대시보드",
  description: "코스피·코스닥 전 종목 시세와 수익률을 한눈에",
  // 홈화면에 추가하면 앱처럼 열립니다.
  appleWebApp: { capable: true, statusBarStyle: "default", title: "주식" },
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // 확대를 막지 않습니다. 글씨를 키워 봐야 하는 분이 있습니다.
  maximumScale: 5,
  themeColor: "#f7f8fa",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
