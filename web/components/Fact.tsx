import type { Explain } from "@/lib/explain";
import type { Rank } from "@/lib/peers";
import { rankSentence, rankWord } from "@/lib/peers";
import { num } from "@/lib/format";

/**
 * 숫자 한 칸. 누르면 그 자리에서 설명이 열립니다.
 *
 * ★ 왜 <details> 인가 ★
 *   자바스크립트 없이 브라우저가 직접 여닫습니다. 화면이 뜨자마자 바로
 *   눌리고, 키보드로도 되고, 화면 읽어주는 프로그램도 알아듣습니다.
 *   이 화면은 차트도 라이브러리 없이 직접 그릴 만큼 가볍게 가고 있어서,
 *   설명 하나 여는 데 프레임워크를 들이는 것은 맞지 않습니다.
 *
 * ★ 왜 따로 띄우지(모달) 않는가 ★
 *   초보자는 여러 칸을 이어서 눌러봅니다. 창이 떴다 닫혔다 하면
 *   어디를 보고 있었는지 잃어버립니다. 제자리에서 펴지면 앞뒤 숫자를
 *   같이 보면서 읽을 수 있습니다.
 */
export default function Fact({
  label,
  value,
  explain,
  peer = null,
}: {
  label: string;
  /** 이미 사람이 읽을 수 있게 다듬은 값. 빈 글자면 '—' 로 나옵니다. */
  value: string;
  explain: Explain;
  /** 같은 업종 안에서 몇 번째인지. 없으면 안 보여줍니다. */
  peer?: Rank | null;
}) {
  return (
    <details className="fact">
      <summary>
        <span className="fact-k">
          {label}
          {/* 누를 수 있다는 표시. 없으면 아무도 안 누릅니다. */}
          <i className="fact-q" aria-hidden="true">
            ?
          </i>
        </span>
        {value ? (
          <span className="fact-v n">{value}</span>
        ) : (
          <span className="fact-v none">—</span>
        )}
        {/* 같은 업종 안에서 어느 쪽인지. 접힌 상태에서도 보여야 하므로
            summary 안에 둡니다. details 는 summary 말고는 다 숨깁니다 —
            밖에 두면 눌러야만 보이는데, 그러면 아무도 안 봅니다. */}
        {peer && <span className="fact-p">{rankWord(peer)}</span>}
      </summary>

      <div className="fact-x">
        <p>
          <b>뜻</b> {md(explain.뜻)}
        </p>
        <p>
          <b>지금</b> {md(explain.지금)}
        </p>
        {peer && (
          <p>
            <b>업종</b> {rankSentence(peer)}. 가운데쯤 되는 회사는{" "}
            <span className="n">{num(peer.median, 2)}</span> 입니다.
          </p>
        )}
        <p className="fact-care">
          <b>주의</b> {md(explain.주의)}
        </p>
      </div>
    </details>
  );
}

/**
 * **굵게** 만 처리합니다.
 *
 * 마크다운 라이브러리를 넣지 않는 이유: 설명 글에서 쓰는 꾸밈이 이것
 * 하나뿐입니다. 이거 하나 때문에 수십 KB 를 내려받게 할 이유가 없습니다.
 */
function md(s: string) {
  return s.split(/\*\*(.+?)\*\*/g).map((part, i) =>
    i % 2 === 1 ? <b key={i}>{part}</b> : <span key={i}>{part}</span>,
  );
}
