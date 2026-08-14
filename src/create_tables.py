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

-- 색인(index)은 책의 '찾아보기' 같은 것입니다. 조회는 빨라지지만 공간을 씁니다.
--
-- 이 표에는 PRIMARY KEY (code, trade_date) 색인 하나만 둡니다.
-- Neon 무료 플랜(512MB)에서 공간이 빠듯하기 때문에, 효과에 비해
-- 공간을 많이 쓰는 색인은 만들지 않습니다.
--
-- 아래 두 색인은 실측 후 제거했습니다.
--   idx_price_code_date : PRIMARY KEY 와 하는 일이 같아 완전히 중복 (200MB 절약)
--   idx_price_date      : 34MB 를 쓰는데 사용 횟수가 63회뿐이었고,
--                         없어도 해당 조회가 1초면 끝나 화면 체감차가 없었음
DROP INDEX IF EXISTS idx_price_code_date;
DROP INDEX IF EXISTS idx_price_date;

-- ─────────────────────────────────────────────────────────────
-- 3) 수집 진행 기록 표
--    3년치를 받다가 컴퓨터를 껐을 때, 어디까지 받았는지 알기 위한 표입니다.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_log (
    trade_date  DATE NOT NULL,
    kind        TEXT NOT NULL,             -- STOCK / ETF / FUNDAMENTAL
    status      TEXT NOT NULL,             -- done(완료) / holiday(휴장) / failed(실패)
    row_count   INTEGER NOT NULL DEFAULT 0,
    message     TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (trade_date, kind)
);

-- ─────────────────────────────────────────────────────────────
-- 4) 기존 표에 칸 추가 (이미 있으면 그냥 넘어갑니다)
-- ─────────────────────────────────────────────────────────────

-- 종목 표에 'DART 회사코드' 칸 추가
--   DART 는 종목코드(005930)가 아니라 자기들만의 8자리 회사코드로 조회합니다.
--   그 대응표를 여기에 저장해 두고 계속 재사용합니다.
ALTER TABLE ticker ADD COLUMN IF NOT EXISTS dart_corp_code TEXT;
CREATE INDEX IF NOT EXISTS idx_ticker_dart ON ticker (dart_corp_code);

-- 일별시세 표에 투자지표 칸 5개 추가 (pykrx 가 주는 값)
--   PER  주가수익비율   : 주가 ÷ 주당순이익. 낮을수록 이익 대비 주가가 싸다는 뜻
--   PBR  주가순자산비율 : 주가 ÷ 주당순자산. 1보다 낮으면 장부가치보다 싸다는 뜻
--   EPS  주당순이익     : 1주가 벌어들인 순이익 (원)
--   BPS  주당순자산     : 1주에 해당하는 자기자본 (원)
--   DIV  배당수익률     : 1년 배당금 ÷ 주가 × 100 (%)
--   DPS  주당배당금     : 1주당 배당금 (원)
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS per       NUMERIC(12, 2);
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS pbr       NUMERIC(12, 2);
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS eps       BIGINT;
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS bps       BIGINT;
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS div_yield NUMERIC(8, 2);
ALTER TABLE daily_price ADD COLUMN IF NOT EXISTS dps       BIGINT;

-- ─────────────────────────────────────────────────────────────
-- 5) 재무지표 표  (DART 전자공시에서 가져옵니다)
--    시세와 완전히 분리된 표입니다. 이쪽에 문제가 생겨도
--    시세 수집과 화면은 정상 동작합니다.
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financial (
    code            TEXT NOT NULL,      -- 종목코드
    fiscal_year     INTEGER NOT NULL,   -- 기준 연도 (예: 2025)
    fiscal_quarter  INTEGER NOT NULL,   -- 기준 분기 (1=1분기 2=반기 3=3분기 4=사업보고서)
    PRIMARY KEY (code, fiscal_year, fiscal_quarter),   -- ← 중복 방지 장치

    -- 계산해서 넣는 지표들 (계산식은 src/financial_collect.py 주석 참고)
    roe             NUMERIC(12, 2),     -- 자기자본이익률 (%)  높을수록 돈을 잘 버는 회사
    debt_ratio      NUMERIC(12, 2),     -- 부채비율 (%)        낮을수록 빚이 적은 회사
    op_margin       NUMERIC(12, 2),     -- 영업이익률 (%)      높을수록 장사를 잘하는 회사
    payout_ratio    NUMERIC(12, 2),     -- 배당성향 (%)        번 돈 중 배당으로 준 비율

    -- 위 지표를 계산할 때 쓴 원본 금액들 (단위: 원). 검산용으로 함께 저장합니다.
    revenue         BIGINT,             -- 매출액
    operating_profit BIGINT,            -- 영업이익
    net_income      BIGINT,             -- 당기순이익
    total_equity    BIGINT,             -- 자본총계 (자기자본)
    total_liabilities BIGINT,           -- 부채총계
    total_assets    BIGINT,             -- 자산총계
    dividend_total  BIGINT,             -- 현금배당금총액

    report_code     TEXT,               -- DART 보고서 코드 (11013/11012/11014/11011)
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fin_code      ON financial (code, fiscal_year DESC, fiscal_quarter DESC);
CREATE INDEX IF NOT EXISTS idx_fin_period    ON financial (fiscal_year DESC, fiscal_quarter DESC);

-- ─────────────────────────────────────────────────────────────
-- 6) DART 수집 진행 기록 (분기별 이어받기용)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dart_log (
    fiscal_year     INTEGER NOT NULL,
    fiscal_quarter  INTEGER NOT NULL,
    status          TEXT NOT NULL,      -- done / partial / failed
    company_count   INTEGER NOT NULL DEFAULT 0,
    api_calls       INTEGER NOT NULL DEFAULT 0,
    message         TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fiscal_year, fiscal_quarter)
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
                   AND t.table_name IN
                       ('ticker', 'daily_price', 'ingest_log', 'financial', 'dart_log')
                 ORDER BY table_name;
                """
            )
            tables = cur.fetchall()

    print()
    labels = {
        "ticker": "종목 목록",
        "daily_price": "일별 시세",
        "ingest_log": "시세 수집기록",
        "financial": "재무지표",
        "dart_log": "재무 수집기록",
    }
    for name, col_count in tables:
        print(f"  [OK] {name:<12} {labels.get(name, ''):<12} (칸 {col_count}개)")

    expected = 5
    if len(tables) == expected:
        print(f"\n완료! 표 {expected}개가 모두 준비되었습니다.")
    else:
        print(f"\n[!] 표가 {expected}개보다 적습니다. 오류 메시지를 확인해 주세요.")


if __name__ == "__main__":
    main()
