/**
 * 경제 지표 — '요즘 돈의 사정이 어떤가'.
 *
 * ★ 지수와 무엇이 다른가 ★
 *   지수(lib/indexes.ts)는 '오늘 시장이 오른 날인가' 를 말합니다.
 *   여기 있는 것들은 그보다 뒤에 있는 배경입니다. 금리가 오르는 중이면
 *   시장이 하루 올랐다고 해서 마음 놓을 일이 아니고, 유가가 계속 뛰면
 *   물건을 만들어 파는 회사들의 이익이 깎입니다.
 *
 *   초보자가 가장 자주 하는 오해가 '내 종목이 빠졌으니 이 회사에
 *   문제가 생겼다' 입니다. 시장 전체를 보면 절반은 풀리고, 경제 지표까지
 *   보면 나머지 절반도 설명될 때가 많습니다.
 *
 * ★ 금리는 %p 로 말합니다 ★
 *   금리는 그 자체가 % 입니다. 4.20% 에서 4.29% 가 된 것을 '+2.1%' 라고
 *   하면 금리가 두 배쯤 뛴 것처럼 읽히는데, 실제로 오른 폭은 0.09%p
 *   입니다. 그래서 금리만 '차이' 로, 나머지는 '몇 퍼센트 움직였나' 로
 *   말합니다.
 */
import { sql } from "./db";
import { num } from "./format";

export type Econ = {
  symbol: string;
  name: string;
  /** 사람이 읽을 수 있게 다듬은 값 (4.23% · $71.20 · 18.4) */
  value: string;
  /** 어제와 견준 말 (+0.09%p · -1.2%). 하루치밖에 없으면 null */
  diff: string | null;
  /** 색을 정할 방향. 지표는 오르는 것이 좋은 일도 나쁜 일도 아니라
      주가처럼 빨강·파랑을 쓰지 않습니다. 0 이면 색 없음 */
  dir: 0;
  /** 이게 뭔지, 오르면 주식에 어떤 뜻인지 */
  뜻: string;
};

type Spec = {
  name: string;
  /** 금리는 차이(%p)로, 나머지는 등락률(%)로 말합니다 */
  금리: boolean;
  fmt: (v: number) => string;
  뜻: string;
};

/** 화면에 보여줄 순서. 주식에 미치는 힘이 큰 것부터. */
const SHOW: [string, Spec][] = [
  [
    "^TNX",
    {
      name: "미국 10년 금리",
      금리: true,
      fmt: (v) => `${num(v, 2)}%`,
      뜻:
        "세계 돈값의 기준입니다. 이 금리가 오르면 그냥 채권만 사도 이만큼 " +
        "벌 수 있다는 뜻이라, 위험을 안고 주식을 살 이유가 줄어듭니다. " +
        "보통 주식에는 불리하게 작용합니다.",
    },
  ],
  [
    "^VIX",
    {
      name: "공포지수",
      금리: false,
      fmt: (v) => num(v, 1),
      뜻:
        "미국 시장이 앞으로 얼마나 출렁일 것으로 보는지를 나타냅니다. " +
        "20 아래면 잠잠한 편, 30을 넘으면 시장이 겁을 먹고 있다는 뜻입니다. " +
        "높을 때는 하루 만에 크게 오르내리니 서둘러 사고팔지 않는 편이 좋습니다.",
    },
  ],
  [
    "CL=F",
    {
      name: "국제 유가",
      금리: false,
      fmt: (v) => `$${num(v, 2)}`,
      뜻:
        "기름값입니다. 오르면 물건을 만들고 옮기는 비용이 올라 대부분의 " +
        "회사 이익이 깎이고, 물가가 올라 금리를 내리기도 어려워집니다. " +
        "정유·조선처럼 반대로 덕을 보는 업종도 있습니다.",
    },
  ],
  [
    "DX-Y.NYB",
    {
      name: "달러지수",
      금리: false,
      fmt: (v) => num(v, 2),
      뜻:
        "달러가 다른 나라 돈들에 견줘 얼마나 센지를 나타냅니다. " +
        "원달러 환율만 보면 '우리 돈이 약해진 것' 인지 '달러가 세진 것' 인지 " +
        "구별이 안 됩니다. 둘을 같이 봐야 갈립니다. 달러가 세지면 " +
        "우리 같은 나라에서 돈이 빠져나가는 쪽으로 봅니다.",
    },
  ],
  [
    "GC=F",
    {
      name: "금",
      금리: false,
      fmt: (v) => `$${num(v)}`,
      뜻:
        "사람들이 불안할 때 사두는 것입니다. 금이 계속 오른다는 것은 " +
        "돈을 주식 같은 위험한 곳에 두기 꺼리는 사람이 늘고 있다는 뜻으로 " +
        "읽습니다.",
    },
  ],
];

const SYMBOLS = SHOW.map(([s]) => s);

export async function getEconomy(): Promise<Econ[]> {
  try {
    // 기호마다 마지막 두 날이 필요합니다. 한국 장과 미국 장은 쉬는 날이
    // 달라서 '어제' 가 기호마다 다릅니다. 넉넉히 받아 와서 각자 최근
    // 두 개를 고릅니다. 지표는 넷뿐이라 이래도 가볍습니다.
    const rows = await sql<{ symbol: string; close: string | null }[]>`
      SELECT symbol, close
        FROM market_index
       WHERE trade_date >= (SELECT max(trade_date) FROM market_index)
                            - INTERVAL '21 days'
       ORDER BY symbol, trade_date DESC
    `;

    const 최근 = new Map<string, number[]>();
    for (const r of rows) {
      if (!SYMBOLS.includes(r.symbol) || r.close === null) continue;
      const list = 최근.get(r.symbol) ?? [];
      if (list.length < 2) list.push(Number(r.close));
      최근.set(r.symbol, list);
    }

    return SHOW.flatMap(([symbol, spec]) => {
      const [now, prev] = 최근.get(symbol) ?? [];
      if (now === undefined) return [];

      let diff: string | null = null;
      if (prev !== undefined && prev !== 0) {
        const d = spec.금리 ? now - prev : (now / prev - 1) * 100;
        const 단위 = spec.금리 ? "%p" : "%";
        const 자리 = spec.금리 ? 2 : 1;
        // 0.00 은 '+0.00' 보다 '0.00' 이 정직합니다. 부호를 붙이면
        // 아주 조금 올랐다는 뜻으로 읽힙니다.
        const sign = d > 0 ? "+" : d < 0 ? "−" : "";
        diff = `${sign}${num(Math.abs(d), 자리)}${단위}`;
      }

      return [{ symbol, name: spec.name, value: spec.fmt(now), diff, dir: 0 as const, 뜻: spec.뜻 }];
    });
  } catch (e) {
    // 지표가 아직 없거나 창고가 잠깐 안 될 때. 이것 때문에 첫 화면이
    // 통째로 안 열리면 손해가 더 큽니다.
    console.error("[경제지표] 읽지 못했습니다:", e);
    return [];
  }
}
