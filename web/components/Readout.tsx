import type { Note } from "@/lib/readout";

/**
 * '이 회사 읽어주기' — 눈에 띄는 것만 문장으로.
 *
 * 숫자 칸보다 먼저 놓습니다. 초보자는 숫자를 봐도 무엇이 이상한지
 * 모르기 때문에, 짚어준 다음에 숫자를 보는 순서라야 뜻이 있습니다.
 *
 * 색은 '살필 것' 에만 씁니다. 좋은 쪽까지 색을 칠하면 화면이
 * 신호등처럼 되어서, 정작 조심해야 할 것이 묻힙니다.
 */
export default function Readout({ notes }: { notes: Note[] }) {
  return (
    <ul className="ro">
      {notes.map((n, i) => (
        <li key={i} className={`ro-${n.tone}`}>
          <span className="ro-dot" aria-hidden="true" />
          <span>{md(n.text)}</span>
        </li>
      ))}
    </ul>
  );
}

function md(s: string) {
  return s.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? <b key={i}>{part}</b> : <span key={i}>{part}</span>,
  );
}
