"""
데이터베이스에 표(테이블)를 만드는 스크립트.  ★ 맨 처음 딱 한 번만 실행 ★

실행 방법 (프로젝트 폴더에서):
    .venv\\Scripts\\python.exe -m src.create_tables

만드는 표 3개
  1) ticker      : 종목 목록      (종목코드, 종목명, 시장구분, 종류)
  2) daily_price : 일별 시세      (종목코드, 날짜, 종가, 등락률, 거래량, 시가총액)
  3) ingest_log  : 수집 진행 기록 (어느 날짜까지 받았는지 표시 → 중단 후 이어받기용)

이미 만들어져 있으면 그냥 넘어갑니다(IF NOT EXISTS). 여러 번 실행해도 안전합니다.
"""

from .db import get_conn, run_sql

SCHEMA_SQL = """
-- ─────────────────────────────────────────────────────────────
-- 1) 종목 목록 표
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ticker (
    code        TEXT PRIMARY KEY,          -- 종목코드 (예: 005930). 중복 불가
    name        TEXT NOT NULL,             -- 종목명   (예: 삼성전자)
    market      TEXT NOT NULL,             -- 시장구분 : KOSPI / KOSDAQ
    kind        TEXT NOT NULL,             -- 종류     : STOCK(일반주식) / ETF
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,  -- 현재 상장중이면 TRUE
    first_seen  DATE,                      -- 처음 확인된 날 (신규 상장 파악용)
    last_seen   DATE,                      -- 마지막으로 확인된 날 (상장폐지 파악용)
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticker_kind_market ON ticker (kind, market);
CREATE INDEX IF NOT EXISTS idx_ticker_name        ON ticker (name);

-- ─────────────────────────────────────────────────────────────
-- 2) 일별 시세 표
--    PRIMARY KEY (code, trade_date) 덕분에
--    "같은 종목 + 같은 날짜" 조합은 절대 두 줄이 생기지 않습니다.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_price (
    code        TEXT NOT NULL,             -- 종목코드
    trade_date  DATE NOT NULL,             -- 거래일
    close       BIGINT,                    -- 종가 (원)
    change_pct  NUMERIC(10, 4),            -- 등락률 (%)
    volume      BIGINT,                    -- 거래량 (주)
    market_cap  BIGINT,                    -- 시가총액 (원)
    PRIMARY KEY (code, trade_date)         -- ← 중복 방지 장치
);

-- 조회 속도를 위한 색인(index). 책의 '찾아보기' 같은 것입니다.
-- 날짜로 훑는 조회(최근 30일 등)에 쓰입니다.
CREATE INDEX IF NOT EXISTS idx_price_date ON daily_price (trade_date);

-- 참고: "종목별 최근 종가 찾기"용 색인은 따로 만들지 않습니다.
-- 위의 PRIMARY KEY (code, trade_date) 가 이미 같은 역할을 하기 때문입니다
-- (Postgres 는 이 색인을 거꾸로도 읽을 수 있습니다).
-- 예전 버전에서 만들었던 중복 색인이 남아 있다면 지웁니다. 용량을 약 26% 아낍니다.
DROP INDEX IF EXISTS idx_price_code_date;

-- ─────────────────────────────────────────────────────────────
-- 3) 수집 진행 기록 표
--    3년치를 받다가 컴퓨터를 껐을 때, 어디까지 받았는지 알기 위한 표입니다.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_log (
    trade_date  DATE NOT NULL,
    kind        TEXT NOT NULL,             -- STOCK / ETF
    status      TEXT NOT NULL,             -- done(완료) / holiday(휴장) / failed(실패)
    row_count   INTEGER NOT NULL DEFAULT 0,
    message     TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date, kind)
);
"""


def main() -> None:
    print("=" * 60)
    print(" 데이터베이스에 표(테이블)를 만듭니다")
    print("=" * 60)

    with get_conn() as conn:
        run_sql(conn, SCHEMA_SQL)

        # 잘 만들어졌는지 확인해서 보여줍니다
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name,
                       (SELECT count(*) FROM information_schema.columns c
                         WHERE c.table_name = t.table_name
                           AND c.table_schema = 'public') AS col_count
                  FROM information_schema.tables t
                 WHERE t.table_schema = 'public'
                   AND t.table_name IN ('ticker', 'daily_price', 'ingest_log')
                 ORDER BY table_name;
                """
            )
            tables = cur.fetchall()

    print()
    for name, col_count in tables:
        print(f"  [OK] {name:<12} (칸 {col_count}개)")

    if len(tables) == 3:
        print("\n완료! 표 3개가 모두 준비되었습니다.")
    else:
        print("\n[!] 표가 3개보다 적습니다. 오류 메시지를 확인해 주세요.")


if __name__ == "__main__":
    main()
