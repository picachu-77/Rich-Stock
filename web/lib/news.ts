/**
 * 뉴스 가져오기 (네이버 뉴스 검색).
 *
 * ★ 왜 저장하지 않고 그때그때 불러오나 ★
 *   공시(disclosure)처럼 데이터베이스에 쌓아둘 수도 있지만, 뉴스는 양이
 *   다릅니다. 종목 3,931개에 하루 10건씩만 잡아도 하루 4만 줄입니다.
 *   Supabase 무료 한도 500MB 중 이미 405MB 를 쓰고 있어서, 일주일이면
 *   창고가 꽉 찹니다. 그래서 종목을 열어볼 때만 불러옵니다.
 *   덤으로 언제 봐도 방금 것이 나옵니다.
 *
 * ★ 열쇠가 없으면 ★
 *   화면이 깨지지 않습니다. '뉴스 준비 중' 으로 조용히 비워 둡니다.
 *   뉴스가 없다고 종목 화면 전체가 안 열리면 안 됩니다.
 */

const ENDPOINT = "https://openapi.naver.com/v1/search/news.json";

export type Article = {
  title: string;
  link: string;
  press: string;
  at: Date;
};

/** 열쇠가 등록되어 있는지. 화면에서 안내문을 고르는 데 씁니다. */
export const newsReady = (): boolean =>
  Boolean(process.env.NAVER_CLIENT_ID && process.env.NAVER_CLIENT_SECRET);

/* ── 글자 다듬기 ──────────────────────────────────────────── */

/**
 * 네이버는 찾은 낱말에 <b> 를 씌워서 돌려줍니다. 그대로 찍으면
 * '&lt;b&gt;삼성전자&lt;/b&gt;가' 처럼 보입니다. 태그와 &amp; 같은 기호를 원래 글자로
 * 되돌립니다.
 */
const clean = (s: string): string =>
  s
    .replace(/<[^>]*>/g, "")
    .replace(/&quot;/g, '"')
    .replace(/&apos;|&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .trim()
    // 네이버가 긴 제목을 자르면서 붙인 말줄임표는 뗍니다.
    // 그대로 두면 화면에서 줄을 또 줄이면서 '…' 이 두 번 찍힙니다.
    .replace(/[.\u2026]+$/, "")
    .trim();

/**
 * 어느 언론사인지. 주소에서 알아냅니다.
 * 네이버 뉴스로 넘어가는 주소(n.news.naver.com)는 언론사를 알 수 없어서
 * 원문 주소를 함께 보고 고릅니다.
 */
const pressOf = (url: string): string => {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    const known: Record<string, string> = {
      "n.news.naver.com": "네이버뉴스",
      "news.naver.com": "네이버뉴스",
      "mk.co.kr": "매일경제",
      "hankyung.com": "한국경제",
      "sedaily.com": "서울경제",
      "mt.co.kr": "머니투데이",
      "edaily.co.kr": "이데일리",
      "fnnews.com": "파이낸셜뉴스",
      "yna.co.kr": "연합뉴스",
      "chosun.com": "조선일보",
      "donga.com": "동아일보",
      "hani.co.kr": "한겨레",
      "khan.co.kr": "경향신문",
      "joongang.co.kr": "중앙일보",
      "biz.sbs.co.kr": "SBS Biz",
      "news.sbs.co.kr": "SBS",
      "imbc.com": "MBC",
      "kbs.co.kr": "KBS",
      "thebell.co.kr": "더벨",
      "businesspost.co.kr": "비즈니스포스트",
      "inews24.com": "아이뉴스24",
      "zdnet.co.kr": "지디넷코리아",
      "etnews.com": "전자신문",
      "dt.co.kr": "디지털타임스",
      "asiae.co.kr": "아시아경제",
      "heraldcorp.com": "헤럴드경제",
      "newsis.com": "뉴시스",
      "news1.kr": "뉴스1",
      "seoul.co.kr": "서울신문",
      "kmib.co.kr": "국민일보",
      "segye.com": "세계일보",
      "munhwa.com": "문화일보",
      "hankookilbo.com": "한국일보",
      "wowtv.co.kr": "한국경제TV",
      "moneys.co.kr": "머니S",
      "ajunews.com": "아주경제",
      "cnbnews.com": "CNB뉴스",
      "bloter.net": "블로터",
    };
    if (known[host]) return known[host];
    // 모르는 곳은 주소 앞부분을 그대로 보여줍니다. 없는 것보다 낫습니다.
    return host.split(".")[0];
  } catch {
    return "";
  }
};

/* ── 이 기사가 정말 이 종목 이야기인가 ────────────────────── */

/**
 * 한국어에는 낱말 사이에 띄어쓰기가 없는 자리가 많아서, 이름이 들어 있다고
 * 해서 그 회사 이야기가 아닙니다. 실제로 '동양' 을 찾으면 이런 것들이
 * 딸려 옵니다.
 *
 *   동양생명 · 동양철관 · 동양이엔피 · "동양에서는 오랜 기간..."
 *
 * 그래서 이름 바로 뒤에 무엇이 오는지 봅니다.
 *   · 한글이 아니면(띄어쓰기·기호·끝)      → 이 회사 이야기가 맞습니다
 *   · 한글인데 '조사' 이면 (삼성전자'가')   → 맞습니다
 *   · 그 밖의 한글이면 (동양'생'명)         → 다른 회사입니다
 *
 * 앞쪽도 같이 봅니다. '한국항공우주' 를 찾을 때 '대한국항공우주' 같은
 * 것이 걸리지 않도록.
 */
const JOSA = [
  // 긴 것을 먼저 놓아야 합니다. '으로' 를 '으' 로 자르면 안 됩니다.
  "으로부터", "에서부터", "이라고", "라고는", "에게서", "이라는", "라는",
  "으로는", "으로도", "으로", "로는", "로도", "로써", "로서", "로",
  "에서는", "에서도", "에서", "에게", "에는", "에도", "에",
  "과의", "와의", "과", "와",
  "이라", "이란", "이는", "이가", "이도", "이나", "이며", "이면", "이",
  "가", "은", "는", "을", "를", "의", "도", "만", "요",
  "부터", "까지", "처럼", "보다", "마저", "조차", "밖에", "대로", "쯤",
  "주가", "주는", "주도", "株",
];

const isHangul = (ch: string): boolean => /[가-힣]/.test(ch);

/** 이름이 '낱말 하나'로 등장하는지. */
function mentions(text: string, name: string): boolean {
  if (!name) return false;
  let from = 0;
  for (;;) {
    const i = text.indexOf(name, from);
    if (i === -1) return false;
    from = i + 1;

    // 앞 글자가 한글이면 더 긴 이름의 일부입니다.
    const before = i > 0 ? text[i - 1] : "";
    if (before && isHangul(before)) continue;

    const rest = text.slice(i + name.length);
    // 뒤가 한글이 아니면(띄어쓰기·기호·끝) 통과.
    if (!rest || !isHangul(rest[0])) return true;
    // 뒤가 한글이면 조사일 때만 통과.
    const josa = JOSA.find((j) => rest.startsWith(j));
    if (josa) {
      const after = rest.slice(josa.length);
      if (!after || !isHangul(after[0])) return true;
    }
  }
}

/**
 * 이름이 짧으면 문법만으로는 가릴 수 없습니다.
 *
 *   "동양에서는 오랜 기간 음력을 사용해왔는데"
 *
 * 여기서 '동양' 은 회사가 아니라 '동쪽 나라' 인데, 글자만 보면
 * "동양에서는 오늘 상한가" 와 똑같이 생겼습니다. 조사도 멀쩡한 '에서는'
 * 입니다. 문법으로는 구분할 방법이 없습니다.
 *
 * 그래서 두 글자 이하 이름은 증시 낱말이 함께 나오는지 한 번 더 봅니다.
 * 상장회사 기사라면 이 중 하나는 거의 반드시 들어 있습니다.
 */
const MARKET_WORDS = [
  "주가", "증시", "코스피", "코스닥", "종목", "상한가", "하한가",
  "상승", "하락", "급등", "급락", "강세", "약세", "반등",
  "매수", "매도", "순매수", "순매도", "거래량", "거래대금",
  "시가총액", "실적", "영업이익", "매출", "공시", "배당", "주주",
  "투자", "증권", "상장", "주식",
];

const hasMarketWord = (text: string): boolean =>
  MARKET_WORDS.some((w) => text.includes(w));

/**
 * 종목 이름을 검색어로 다듬습니다.
 *
 * ETF 는 이름에 'TIGER 미국S&P500(H)' 처럼 괄호와 기호가 붙습니다.
 * 그대로 넣으면 검색이 거의 안 됩니다. 괄호 안은 떼어냅니다.
 */
export const searchName = (name: string): string =>
  name.replace(/\([^)]*\)/g, " ").replace(/\s+/g, " ").trim();

/**
 * 이 기사가 이 종목 이야기인지 최종 판단.
 * (규칙을 따로 시험할 수 있도록 밖으로 내놓았습니다)
 *
 * strict = true 면 제목에 이름이 있어야 합니다. 제목에 있으면 그 종목이
 * 기사의 주인공일 가능성이 훨씬 높습니다.
 */
export function relevant(
  name: string,
  title: string,
  body: string,
  strict = false,
): boolean {
  const q = searchName(name);
  if (!q) return false;

  const inTitle = mentions(title, q);
  if (strict ? !inTitle : !(inTitle || mentions(body, q))) return false;

  // 두 글자 이하 이름은 증시 낱말이 함께 있어야 인정합니다.
  if (q.replace(/\s/g, "").length <= 2 && !hasMarketWord(`${title} ${body}`)) {
    return false;
  }
  return true;
}

/* ── 네이버에 묻기 ────────────────────────────────────────── */

type NaverItem = {
  title?: string;
  link?: string;
  originallink?: string;
  description?: string;
  pubDate?: string;
};

async function ask(query: string, display: number): Promise<NaverItem[]> {
  const id = process.env.NAVER_CLIENT_ID;
  const secret = process.env.NAVER_CLIENT_SECRET;
  if (!id || !secret) return [];

  const url = `${ENDPOINT}?query=${encodeURIComponent(query)}&display=${display}&sort=date`;

  try {
    const res = await fetch(url, {
      headers: { "X-Naver-Client-Id": id, "X-Naver-Client-Secret": secret },
      // 뉴스는 화면과 같은 주기(1시간)로만 새로 받습니다. 볼 때마다
      // 부르면 하루 한도(25,000번)를 금방 씁니다.
      next: { revalidate: 3600 },
    });
    if (!res.ok) {
      // 화면에는 조용히 '기사 없음' 으로 나가지만, 왜 실패했는지는
      // 남겨야 합니다. 안 남기면 '열쇠가 틀린 것' 과 '기사가 없는 것' 을
      // 구분할 수 없어서, 안 나올 때 손댈 곳을 못 찾습니다.
      // (Vercel > 프로젝트 > Logs 에서 보입니다)
      //
      // 401 = 열쇠가 틀림 · 403 = 이 열쇠로는 검색을 못 씀
      // 429 = 하루 한도(25,000번) 초과
      //
      // 열쇠 자체는 절대 찍지 않습니다. 로그도 남는 기록입니다.
      console.error(
        `[뉴스] 네이버가 거절했습니다 — HTTP ${res.status}. ` +
          `응답: ${(await res.text()).slice(0, 200)}`,
      );
      return [];
    }
    const data = (await res.json()) as { items?: NaverItem[] };
    return data.items ?? [];
  } catch (err) {
    // 네이버가 느리거나 잠깐 막혀도 종목 화면은 열려야 합니다.
    console.error("[뉴스] 네이버를 부르지 못했습니다:", err);
    return [];
  }
}

/** 네이버가 준 것을 화면에서 쓸 모양으로 바꿉니다. */
function toArticle(it: NaverItem): Article | null {
  const title = clean(it.title ?? "");
  const link = it.link || it.originallink || "";
  if (!title || !link) return null;
  const at = new Date(it.pubDate ?? "");
  if (Number.isNaN(at.getTime())) return null;
  return { title, link, press: pressOf(it.originallink || link), at };
}

/* ── 화면에서 부르는 것 ───────────────────────────────────── */

/**
 * 종목 하나에 딸린 뉴스.
 *
 * 넉넉히 받아서 '정말 이 종목 이야기' 인 것만 남깁니다. 남는 게 없으면
 * 빈 채로 돌려줍니다. 엉뚱한 회사 뉴스를 보여주느니 없는 게 낫습니다.
 * 연습하려고 보는 화면인데 다른 회사 소식을 보고 판단하면 아무 의미가
 * 없습니다.
 */
export async function getStockNews(name: string, limit = 5): Promise<Article[]> {
  const q = searchName(name);
  if (!q) return [];

  const items = await ask(q, 40);
  const seen = new Set<string>();
  const out: Article[] = [];

  // 제목에 이름이 있는 기사를 먼저 채우고(strict), 모자라면 본문에만
  // 있는 기사로 채웁니다.
  for (const strict of [true, false]) {
    for (const it of items) {
      if (out.length >= limit) break;
      const a = toArticle(it);
      if (!a) continue;
      if (seen.has(a.link) || seen.has(a.title)) continue;
      if (!relevant(q, a.title, clean(it.description ?? ""), strict)) continue;

      seen.add(a.link);
      seen.add(a.title);
      out.push(a);
    }
  }
  return out;
}

/** 첫 화면에 놓을 '오늘 증시' 뉴스. 종목을 가리지 않는 시장 전체 이야기입니다. */
export async function getMarketNews(limit = 4): Promise<Article[]> {
  const items = await ask("코스피 코스닥 증시 마감", 20);
  const seen = new Set<string>();
  const out: Article[] = [];
  for (const it of items) {
    if (out.length >= limit) break;
    const a = toArticle(it);
    if (!a || seen.has(a.title)) continue;
    seen.add(a.title);
    out.push(a);
  }
  return out;
}

/**
 * '3시간 전' 처럼 읽어줍니다.
 * 뉴스는 '언제 나온 것인지' 가 제목만큼 중요합니다. 어제 것을 오늘
 * 것으로 착각하면 판단이 어긋납니다.
 */
export function ago(at: Date, now: Date = new Date()): string {
  const m = Math.floor((now.getTime() - at.getTime()) / 60000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}일 전`;
  return `${at.getMonth() + 1}월 ${at.getDate()}일`;
}
