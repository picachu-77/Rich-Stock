import { ago, type Article } from "@/lib/news";

/**
 * 뉴스 몇 줄.
 *
 * ★ 이 화면에서 제목이 전부입니다 ★
 *   목록에 요약을 함께 넣어봤자 휴대폰에서는 제목이 밀려 내려가서
 *   훑기가 어려워집니다. 어차피 자세한 건 눌러서 읽습니다.
 *   그래서 제목 · 언제 · 어디 세 가지만 둡니다.
 *
 * ★ 시세 색을 쓰지 않습니다 ★
 *   이 화면에서 빨강·파랑은 '올랐다/내렸다' 라는 뜻으로만 씁니다.
 *   뉴스에 색을 칠하면 그 약속이 깨집니다. 좋은 뉴스인지 나쁜 뉴스인지는
 *   저희가 판단할 일도 아닙니다.
 */
export default function NewsList({
  articles,
  ready,
  empty,
  compact = false,
}: {
  articles: Article[];
  ready: boolean;
  /** 기사가 없을 때 보여줄 말 */
  empty: string;
  /**
   * 첫 화면처럼 뉴스가 '곁들이' 인 자리에서 씁니다.
   * 제목을 한 줄로 줄여 목록이 화면 밖으로 밀려나지 않게 합니다.
   * (두 줄짜리 넷을 놓으니 종목 목록이 통째로 첫 화면 밖으로 나갔습니다)
   */
  compact?: boolean;
}) {
  if (!ready) {
    return (
      <p className="news-none">
        뉴스는 아직 준비 중입니다.
        <br />
        <span className="news-none-sub">
          네이버 검색 열쇠를 넣으면 여기에 뉴스가 나옵니다.
        </span>
      </p>
    );
  }

  if (articles.length === 0) {
    return <p className="news-none">{empty}</p>;
  }

  return (
    <ul className={compact ? "news compact" : "news"}>
      {articles.map((a) => (
        <li key={a.link}>
          {/*
            새 창으로 엽니다. 기사를 읽고 뒤로 가기를 눌렀을 때 보던
            종목 화면이 그대로 있어야 합니다.
            rel 은 새 창이 이 화면을 건드리지 못하게 막는 안전장치입니다.
          */}
          <a href={a.link} target="_blank" rel="noopener noreferrer">
            <span className="news-t">{a.title}</span>
            <span className="news-m">
              <time dateTime={a.at.toISOString()}>{ago(a.at)}</time>
              {a.press && (
                <>
                  <i aria-hidden="true">·</i>
                  {a.press}
                </>
              )}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}
