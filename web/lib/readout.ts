/**
 * 이 회사 읽어주기 — 숫자 여섯 개 대신 눈에 띄는 것만 문장으로.
 *
 * ★ 사실만 말합니다 ★
 *   '좋은 회사입니다' '사도 됩니다' 같은 말은 하지 않습니다.
 *   저희가 가진 것은 숫자 몇 개뿐이고, 그것으로 회사의 앞날을 알 수는
 *   없습니다. 여기서 하는 일은 딱 하나입니다 —
 *   **초보자가 혼자서는 못 보고 지나칠 것을 짚어주는 것.**
 *
 *   "부채비율 320%" 는 초보자에게 아무 신호도 아닙니다.
 *   "빚이 자기 돈의 3배가 넘습니다" 는 신호입니다. 판단은 본인이 합니다.
 *
 * ★ 좋은 것도 나쁜 것도 같이 보여줍니다 ★
 *   나쁜 것만 모으면 겁만 주고, 좋은 것만 모으면 부추깁니다.
 *   눈에 띄는 것을 그대로 늘어놓고, 중요한 순서로만 정렬합니다.
 */
import type { Stock } from "./stocks";
import type { Disclosure } from "./disclosures";
import { num } from "./format";

export type Note = {
  /** 살필 것 / 좋은 쪽 / 그냥 사실 */
  tone: "watch" | "good" | "plain";
  text: string;
};

/**
 * 순서가 곧 중요도입니다. 휴대폰에서는 위의 두세 줄만 읽힙니다.
 * 그래서 '살필 것' 을 먼저 놓습니다. 놓치면 손해가 큰 쪽이 먼저입니다.
 */
const ORDER: Record<Note["tone"], number> = { watch: 0, good: 1, plain: 2 };

export function readout(stock: Stock, disclosures: Disclosure[] = []): Note[] {
  const notes: Note[] = [];
  const isETF = stock.kind === "ETF";

  /* ── ETF 는 회사가 아니라 바구니입니다 ── */
  if (isETF) {
    notes.push({
      tone: "plain",
      text:
        "이 종목은 **ETF** 입니다. 회사 하나가 아니라 여러 종목을 담아둔 바구니라서, " +
        "재무제표(ROE·부채비율)가 없습니다. 한 회사가 망해도 바구니 전체가 " +
        "사라지지는 않아서, 처음 시작할 때 고르는 사람이 많습니다.",
    });
  }

  /* ── 공시에 '조심할 일' 이 있으면 무엇보다 먼저 ── */
  const 위험공시 = disclosures.filter((d) => d.category === "위험");
  if (위험공시.length > 0) {
    notes.push({
      tone: "watch",
      text:
        `최근 공시에 **조심할 일이 ${num(위험공시.length)}건** 있습니다 ` +
        `(${위험공시[0].title}). 아래 공시 칸에서 원문을 꼭 읽어보세요.`,
    });
  }

  /* ── 적자 ── */
  if (!isETF && stock.roe !== null && stock.roe < 0) {
    notes.push({
      tone: "watch",
      text:
        "**적자입니다.** 자기 돈을 굴려서 오히려 잃었습니다. " +
        "왜 적자인지(한 해뿐인 일인지, 계속되는 일인지)를 보셔야 합니다.",
    });
  } else if (!isETF && (stock.per === null || stock.per <= 0) && stock.pbr !== null) {
    // PER 이 비었는데 PBR 은 있다 = 순이익이 없다는 뜻일 때가 많습니다.
    notes.push({
      tone: "watch",
      text:
        "**PER 이 비어 있습니다.** 회사가 번 돈이 없어서 계산이 안 되는 " +
        "경우가 대부분입니다. 실적을 꼭 확인하세요.",
    });
  }

  /* ── 빚 ── */
  if (!isETF && stock.debt_ratio !== null) {
    const d = stock.debt_ratio;
    if (d >= 400) {
      notes.push({
        tone: "watch",
        text: `**빚이 자기 돈의 ${num(d / 100, 1)}배** 입니다 (부채비율 ${num(d, 0)}%). 아주 높은 편입니다. 다만 은행·카드·건설은 원래 이렇습니다.`,
      });
    } else if (d >= 200) {
      notes.push({
        tone: "watch",
        text: `빚이 자기 돈의 **${num(d / 100, 1)}배** 입니다 (부채비율 ${num(d, 0)}%). 높은 편이라 이자를 감당할 만큼 버는지 보세요.`,
      });
    } else if (d < 100) {
      notes.push({
        tone: "good",
        text: `빚이 자기 돈보다 적습니다 (부채비율 ${num(d, 0)}%). 재무가 튼튼한 편입니다.`,
      });
    }
  }

  /* ── 돈 버는 힘 ── */
  if (!isETF && stock.roe !== null && stock.roe >= 15) {
    notes.push({
      tone: "good",
      text: `자기 돈 100원으로 1년에 **${num(stock.roe, 0)}원** 을 남겼습니다 (ROE ${num(stock.roe, 2)}%). 잘 버는 축입니다.`,
    });
  }

  /* ── 배당 ── */
  if (stock.div_yield !== null && stock.div_yield >= 3) {
    notes.push({
      tone: "good",
      text:
        `배당수익률이 **${num(stock.div_yield, 2)}%** 입니다. 100만원어치면 1년에 약 ` +
        `${num(Math.round(stock.div_yield * 10_000))}원입니다. ` +
        "다만 주가가 떨어져서 높아진 것은 아닌지 확인하세요.",
    });
  }

  /* ── 크기 ── */
  if (stock.market_cap !== null && stock.market_cap < 1_000) {
    notes.push({
      tone: "watch",
      text:
        "**작은 회사입니다** (시가총액 1,000억원 미만). 작은 회사는 " +
        "사려는 사람이 적어서 주가가 크게 흔들리고, 팔고 싶을 때 " +
        "제값에 못 파는 일이 생깁니다.",
    });
  }

  /* ── 많이 움직였나 ── */
  const 일년 = stock.returns[3] ?? null; // PERIODS 4번째 = 1년
  if (일년 !== null) {
    if (일년 >= 100) {
      notes.push({
        tone: "watch",
        text: `1년 사이 **${num(일년, 0)}%** 올랐습니다. 많이 오른 뒤라 왜 올랐는지를 모르고 들어가면 위험합니다.`,
      });
    } else if (일년 <= -50) {
      notes.push({
        tone: "watch",
        text: `1년 사이 **${num(일년, 0)}%** 내렸습니다. 싸 보인다고 사기 전에 왜 내렸는지를 먼저 보세요.`,
      });
    }
  }

  /* ── 아무것도 짚을 게 없을 때 ── */
  if (notes.length === 0) {
    notes.push({
      tone: "plain",
      text:
        "숫자만 놓고 보면 특별히 눈에 띄는 점이 없습니다. " +
        "무엇을 하는 회사인지, 앞으로 더 벌 수 있을지는 숫자 밖의 일이라 " +
        "공시와 사업 내용을 함께 보셔야 합니다.",
    });
  }

  return notes.sort((a, b) => ORDER[a.tone] - ORDER[b.tone]);
}
