"use client";

/**
 * 업종 고르기.
 *
 * 왜 select 를 안 쓰나요?
 *   업종은 한국만 150가지가 넘습니다. 기본 select 는 그걸 한 덩어리로
 *   펼쳐서, 원하는 업종을 찾으려면 손가락으로 계속 굴려야 합니다.
 *   '반도체' 를 찾고 싶은데 ㄱ 부터 훑어야 하는 셈입니다.
 *
 *   그래서 찾는 칸을 붙였습니다. 이름 일부로도, 초성으로도 됩니다.
 *   (ㅂㄷㅊ → 반도체)
 *
 * 다루기
 *   · 열면 찾는 칸에 바로 커서가 갑니다 — 열자마자 칠 수 있습니다
 *   · Esc 로 닫힙니다. 바깥을 눌러도 닫힙니다
 *   · 열려 있는 동안 뒤 화면은 스크롤되지 않습니다
 *
 * 창을 body 바로 아래에 그리는 이유
 *   이 단추는 위에 붙어 따라오는 칸(.sticky, z-index 20) 안에 있습니다.
 *   그 안에서 그리면 아무리 높은 z-index 를 줘도 그 칸의 20 안에
 *   갇혀서, 바깥에 있는 탭바(50)가 창을 덮어버립니다. 하필 둘 다
 *   화면 아래쪽이라 정확히 겹칩니다.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { chosungOf, isChosungQuery } from "@/lib/search";

export default function SectorPicker({
  sectors,
  value,
  onChange,
}: {
  /** [업종 이름, 종목 수] — 많은 업종부터 */
  sectors: [string, number][];
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // 열릴 때마다 찾는 칸을 비우고 커서를 넣습니다. 지난번에 친 글자가
  // 남아 있으면 '업종이 몇 개 없네' 로 잘못 읽힙니다.
  useEffect(() => {
    if (!open) return;
    setQ("");
    inputRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  const chosung = useMemo(() => {
    const m = new Map<string, string>();
    for (const [name] of sectors) m.set(name, chosungOf(name));
    return m;
  }, [sectors]);

  const found = useMemo(() => {
    const query = q.trim();
    if (!query) return sectors;
    if (isChosungQuery(query))
      return sectors.filter(([name]) => (chosung.get(name) ?? "").includes(query));
    return sectors.filter(([name]) => name.includes(query));
  }, [sectors, q, chosung]);

  // 창을 body 에 그립니다. 서버에서는 document 가 없으니 켜진 뒤에만.
  const [탈자리, set탈자리] = useState<HTMLElement | null>(null);
  useEffect(() => set탈자리(document.body), []);

  const 고름 = (next: string) => {
    onChange(next);
    setOpen(false);
  };

  const total = useMemo(
    () => sectors.reduce((n, [, c]) => n + c, 0),
    [sectors],
  );

  return (
    <>
      <button
        type="button"
        className={`pick wide as-button${value ? " chosen" : ""}`}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
      >
        {value || "업종 전체"}
      </button>

      {open && 탈자리 && createPortal(
        <div
          className="sheet-back"
          onPointerDown={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            className="sheet"
            role="dialog"
            aria-modal="true"
            aria-label="업종 고르기"
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          >
            <div className="sheet-head">
              <h2>업종</h2>
              <button type="button" className="sheet-x" onClick={() => setOpen(false)}
                      aria-label="닫기">✕</button>
            </div>

            <input
              ref={inputRef}
              className="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="업종 찾기 — 이름 · 초성"
              inputMode="search"
              autoComplete="off"
              aria-label="업종 찾기. 이름 일부나 초성으로 찾을 수 있습니다."
            />

            <div className="sheet-list" role="listbox" aria-label="업종 목록">
              {/* 찾는 중에는 '업종 전체' 를 숨깁니다. 찾은 결과가 아닌데도
                  맨 위, 가장 누르기 쉬운 자리를 차지합니다 — 'ㅂㄷㅊ' 을
                  치고 첫 줄을 누르면 반도체가 아니라 전체가 골라집니다. */}
              {!q.trim() && (
                <button
                  type="button"
                  role="option"
                  aria-selected={value === ""}
                  className={`sheet-row${value === "" ? " on" : ""}`}
                  onClick={() => 고름("")}
                >
                  <span>업종 전체</span>
                  <b className="n">{total.toLocaleString("ko-KR")}</b>
                </button>
              )}

              {found.map(([name, n]) => (
                <button
                  key={name}
                  type="button"
                  role="option"
                  aria-selected={value === name}
                  className={`sheet-row${value === name ? " on" : ""}`}
                  onClick={() => 고름(name)}
                >
                  <span>{name}</span>
                  <b className="n">{n.toLocaleString("ko-KR")}</b>
                </button>
              ))}

              {found.length === 0 && (
                <p className="sheet-none">
                  &lsquo;{q.trim()}&rsquo; 에 맞는 업종이 없습니다.
                  <br />초성으로도 됩니다. (예: ㅂㄷㅊ)
                </p>
              )}
            </div>
          </div>
        </div>,
        탈자리,
      )}
    </>
  );
}
