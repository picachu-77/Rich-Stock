"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * 아래쪽 탭 — 휴대폰 앱처럼.
 *
 * ★ 왜 아래인가 ★
 *   한 손으로 들고 엄지로 씁니다. 화면 위쪽은 엄지가 안 닿습니다.
 *   휴대폰 앱이 죄다 아래에 두는 데에는 이유가 있습니다.
 *
 * ★ 그림은 직접 그립니다 ★
 *   아이콘 꾸러미를 받으면 수십 KB 이고, 글꼴로 된 것은 글자 크기를
 *   키우면 같이 부풀어 망가집니다. 네 개뿐이라 직접 그리는 편이
 *   가볍고 확실합니다. 색은 currentColor 라 밝을 때·어두울 때가
 *   저절로 맞습니다.
 *
 * ★ 글자를 함께 답니다 ★
 *   그림만 있으면 무슨 뜻인지 짐작해야 합니다. 이 화면을 쓰실 분은
 *   주식도 처음인데 그림까지 알아맞히게 할 이유가 없습니다.
 */

type Tab = {
  href: string;
  label: string;
  /** 이 주소로 시작하면 이 탭이 켜진 것으로 봅니다 */
  match: (path: string) => boolean;
  icon: React.ReactNode;
};

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const TABS: Tab[] = [
  {
    href: "/",
    label: "홈",
    match: (p) => p === "/",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M3 11.2 12 4l9 7.2" />
        <path {...stroke} d="M5.5 9.8V20h13V9.8" />
      </svg>
    ),
  },
  {
    href: "/stocks",
    label: "종목",
    // 종목 상세(/stock/005930)도 이 탭 안입니다
    match: (p) => p.startsWith("/stocks") || p.startsWith("/stock/"),
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M4 16.5 9 11l3.5 3.5L20 6.5" />
        <path {...stroke} d="M20 11V6.5h-4.5" />
        <path {...stroke} d="M3.5 20h17" />
      </svg>
    ),
  },
  {
    href: "/reports",
    label: "리포트",
    match: (p) => p.startsWith("/reports"),
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M6 3.5h8.5L19 8v12.5H6z" />
        <path {...stroke} d="M14 3.5V8h5" />
        <path {...stroke} d="M9 12.5h7M9 16h5" />
      </svg>
    ),
  },
  {
    href: "/practice",
    label: "연습",
    match: (p) => p.startsWith("/practice"),
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle {...stroke} cx="12" cy="12" r="8" />
        <circle {...stroke} cx="12" cy="12" r="3.2" />
        <path {...stroke} d="M12 1.8v2.4M12 19.8v2.4M1.8 12h2.4M19.8 12h2.4" />
      </svg>
    ),
  },
];

export default function TabBar() {
  const path = usePathname() ?? "/";

  return (
    <nav className="tabs" aria-label="화면 이동">
      {TABS.map((t) => {
        const on = t.match(path);
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`tab${on ? " on" : ""}`}
            aria-current={on ? "page" : undefined}
          >
            <span className="tab-i">{t.icon}</span>
            <span className="tab-t">{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
