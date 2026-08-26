"""
가져온 데이터를 데이터베이스에 '저장'하는 담당 파일.

핵심 개념: UPSERT
  같은 종목·같은 날짜 데이터를 두 번 저장해도 줄이 두 개 생기지 않고,
  기존 줄을 새 값으로 덮어씁니다. 그래서 수집기를 몇 번 돌려도 안전합니다.
"""

from __future__ import annotations

from datetime import date

from .db import bulk_upsert, fetch_all, run_sql

# ── 종목 목록 저장 ────────────────────────────────────────────
UPSERT_TICKER_SQL = """
INSERT INTO ticker (code, name, market, kind, is_active, first_seen, last_seen)
VALUES %s
ON CONFLICT (code) DO UPDATE SET
    name       = EXCLUDED.name,
    market     = EXCLUDED.market,
    kind       = EXCLUDED.kind,
    is_active  = TRUE,
    first_seen = LEAST(ticker.first_seen, EXCLUDED.first_seen),
    last_seen  = GREATEST(ticker.last_seen, EXCLUDED.last_seen),
    updated_at = now();
"""


def save_tickers(conn, tickers: list[dict], as_of: date) -> int:
    """종목 목록을 저장(갱신)합니다."""
    rows = [
        (t["code"], t["name"], t["market"], t["kind"], True, as_of, as_of)
        for t in tickers
    ]
    return bulk_upsert(conn, UPSERT_TICKER_SQL, rows)


def mark_delisted(conn, as_of: date) -> int:
    """
    오늘 목록에서 사라진 종목을 '상장폐지(is_active=FALSE)'로 표시합니다.
    데이터를 지우지는 않습니다 — 과거 시세는 그대로 남겨둡니다.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ticker
               SET is_active = FALSE, updated_at = now()
             WHERE is_active = TRUE
               AND (last_seen IS NULL OR last_seen < %s);
            """,
            (as_of,),
        )
        return cur.rowcount


# ── 일별 시세 저장 ────────────────────────────────────────────
UPSERT_PRICE_SQL = """
INSERT INTO daily_price (code, trade_date, close, change_pct, volume, market_cap)
VALUES %s
ON CONFLICT (code, trade_date) DO UPDATE SET
    close      = EXCLUDED.close,
    change_pct = COALESCE(EXCLUDED.change_pct, daily_price.change_pct),
    volume     = EXCLUDED.volume,
    market_cap = COALESCE(EXCLUDED.market_cap, daily_price.market_cap);
"""


def save_prices(conn, rows: list[tuple]) -> int:
    """일별 시세를 저장합니다."""
    return bulk_upsert(conn, UPSERT_PRICE_SQL, rows)


# ── 투자지표(PER/PBR/EPS/BPS/배당) 저장 ────────────────────────
# 시세와 같은 표(daily_price)에 들어가지만, 저장은 따로 합니다.
# 그래야 지표 수집이 실패해도 시세는 그대로 남고, 나중에 지표만
# 따로 채워 넣을 수도 있습니다.
UPSERT_FUNDAMENTAL_SQL = """
INSERT INTO daily_price (code, trade_date, per, pbr, eps, bps, div_yield, dps)
VALUES %s
ON CONFLICT (code, trade_date) DO UPDATE SET
    per       = EXCLUDED.per,
    pbr       = EXCLUDED.pbr,
    eps       = EXCLUDED.eps,
    bps       = EXCLUDED.bps,
    div_yield = EXCLUDED.div_yield,
    dps       = EXCLUDED.dps;
"""


def save_fundamentals(conn, rows: list[tuple]) -> int:
    """투자지표를 저장합니다. 시세가 이미 있으면 지표 칸만 덧씌웁니다."""
    return bulk_upsert(conn, UPSERT_FUNDAMENTAL_SQL, rows)


# ── 수집 진행 기록 ────────────────────────────────────────────
def log_ingest(conn, trade_date: date, kind: str, status: str,
               row_count: int = 0, message: str | None = None) -> None:
    """'이 날짜의 이 종류는 처리 끝'이라고 기록해 둡니다 (이어받기용)."""
    run_sql(
        conn,
        """
        INSERT INTO ingest_log (trade_date, kind, status, row_count, message, updated_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (trade_date, kind) DO UPDATE SET
            status     = EXCLUDED.status,
            row_count  = EXCLUDED.row_count,
            message    = EXCLUDED.message,
            updated_at = now();
        """,
        (trade_date, kind, status, row_count, message),
    )


def completed_dates(conn, kind: str) -> set[date]:
    """이미 처리가 끝난 날짜 목록 (실패한 날은 제외 → 다시 시도하게 됨)."""
    rows = fetch_all(
        conn,
        "SELECT trade_date FROM ingest_log WHERE kind = %s AND status IN ('done','holiday');",
        (kind,),
    )
    return {r[0] for r in rows}


# ── 등락률 보정 ──────────────────────────────────────────────
# 며칠 이내를 '바로 전 거래일'로 볼 것인지.
#
# 왜 14일인가:
#   국내 증시는 추석·설 연휴에 길게 쉽니다.
#   예) 2025년 추석은 10/3 개천절부터 10/9 한글날까지 이어져
#       10/2 다음 거래일이 10/10 이었습니다 (간격 8일).
#   이런 정상적인 연휴를 '데이터 구멍'으로 오해해서 멀쩡한 등락률을
#   지우는 일이 없도록 넉넉하게 14일로 둡니다.
#
#   이 장치의 진짜 목적은 '아직 과거 데이터를 다 못 받은 상태'에서
#   몇 달~몇 년 전 가격과 비교한 값이 하루 등락률 자리에 들어가는 것을
#   막는 것입니다.
MAX_GAP_DAYS = 14


# 한 번에 몇 종목씩 처리할지.
#
# 처음에 200개로 잡았다가 실패했습니다. 실제로 재보니 한 조각이
# 7초에서 63초까지 들쭉날쭉했고, 13번째 조각이 2분을 넘겨 끊겼습니다.
#
#     200/4,416개 종목   63초
#     800/4,416개 종목    8초
#   2,400/4,416개 종목   50초
#   2,600/4,416개 종목   2분 초과 → 실패
#
# 왜 들쭉날쭉한가: '종목 200개' 는 일감의 크기가 아닙니다. 3년 내내
# 거래된 종목은 800줄이지만 얼마 전 상장한 종목은 20줄입니다. 어느
# 200개를 잡느냐에 따라 훑는 양이 열 배씩 차이납니다.
#
# 그래서 50개로 줄였습니다. 가장 오래 걸렸던 조각도 1/4 이 되어
# 16초쯤이 됩니다. 조각이 늘어난 만큼 총 시간은 비슷합니다.
CHUNK = 50

# 한 문장을 몇 분까지 기다려 줄지.
#
# Supabase 는 기본 2분이 지나면 문장을 끊습니다. 화면에서 쓰는 조회라면
# 2분도 긴 시간이라 옳은 설정이지만, 이건 몇십 분 걸리는 정리 작업입니다.
# 조각 하나가 어쩌다 오래 걸린다고 작업 전체가 죽으면 곤란해서,
# 이 작업에서만 넉넉하게 늘려 둡니다. (조각을 작게 나눠 두었으므로
# 실제로 여기까지 갈 일은 거의 없습니다. 안전장치입니다)
STATEMENT_TIMEOUT = "10min"


def _price_codes(conn, only_missing: bool = False) -> list[str]:
    """
    시세 표에 들어 있는 종목 코드를 가져옵니다.

    종목 목록(ticker) 표를 쓰지 않는 이유:
      상장폐지된 종목은 목록에서 빠지지만 과거 시세는 그대로 남아 있습니다.
      실제로 목록에는 3,931개인데 시세 표에는 4,416개가 있었습니다.
      목록만 보고 돌리면 나머지 485개를 통째로 빠뜨리게 됩니다.

    only_missing 이면 등락률이 비어 있는 종목만 가져옵니다.
      채울 것이 없는 종목까지 훑는 것은 그냥 낭비입니다. 게다가 이 값이
      채워질수록 다음 실행은 저절로 빨라집니다.
    """
    where = "WHERE change_pct IS NULL " if only_missing else ""
    return [
        r[0]
        for r in fetch_all(
            conn, f"SELECT DISTINCT code FROM daily_price {where}ORDER BY code;"
        )
    ]


def _relax_timeout(conn) -> None:
    """이 연결에서만 문장 시간 제한을 늘립니다. (원래 설정은 건드리지 않습니다)"""
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}';")
    conn.commit()


def fill_missing_change_pct(conn, batch: int = CHUNK, progress=None) -> int:
    """
    등락률이 비어 있는 줄을, 바로 전 거래일 종가와 비교해 직접 계산해 채웁니다.
    (ETF 는 거래소가 등락률을 안 주기 때문에 필요합니다)

    ★ 중요 ★
    '바로 전 거래일' 이 14일 이상 떨어져 있으면 계산하지 않고 비워 둡니다.
    데이터를 아직 다 못 받아서 중간이 비어 있을 때, 몇 달~몇 년 전 가격과
    비교한 엉뚱한 값이 '하루 등락률' 자리에 들어가는 것을 막기 위해서입니다.
    나중에 빈 날짜가 채워지면 이 함수를 다시 돌려서 정상값을 넣습니다.

    ★ 왜 종목을 나눠서 처리하나요? ★
      전에는 한 문장으로 시세 표 전체(280만 줄)를 훑었습니다. 그런데
      Supabase 는 한 문장이 너무 오래 걸리면 중간에 끊습니다(기본 2분).
      3년치를 다 채운 마지막 순간에 이 때문에 실패했습니다.

          psycopg2.errors.QueryCanceled:
          canceling statement due to statement timeout

      계산은 종목 안에서만 이뤄지므로(앞뒤 거래일 비교), 종목을 몇백 개씩
      나눠서 처리해도 결과가 똑같습니다. 대신 한 문장이 짧아져 끊기지
      않고, 도중에 멈춰도 이미 채운 것은 남습니다.
    """
    _relax_timeout(conn)
    # 채울 것이 있는 종목만 봅니다. 4,416개 중 실제로 빈 곳이 있는 종목은
    # 훨씬 적고, 채워질수록 다음 실행은 더 빨라집니다.
    codes = _price_codes(conn, only_missing=True)
    if not codes:
        return 0

    total = 0
    for i in range(0, len(codes), batch):
        chunk = codes[i : i + batch]
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH calc AS (
                    SELECT code,
                           trade_date,
                           close,
                           LAG(close)      OVER (PARTITION BY code ORDER BY trade_date) AS prev_close,
                           LAG(trade_date) OVER (PARTITION BY code ORDER BY trade_date) AS prev_date
                      FROM daily_price
                     WHERE code = ANY(%s)
                )
                UPDATE daily_price d
                   SET change_pct = ROUND((c.close - c.prev_close)::numeric
                                          / c.prev_close * 100, 4)
                  FROM calc c
                 WHERE d.code = c.code
                   AND d.trade_date = c.trade_date
                   AND d.change_pct IS NULL
                   AND c.prev_close IS NOT NULL
                   AND c.prev_close > 0
                   AND c.prev_date IS NOT NULL
                   AND (c.trade_date - c.prev_date) <= %s;
                """,
                (chunk, MAX_GAP_DAYS),
            )
            total += cur.rowcount
        # 조각마다 저장합니다. 도중에 멈춰도 여기까지는 남습니다.
        conn.commit()
        if progress:
            progress(min(i + batch, len(codes)), len(codes), total)
    return total


def clear_bogus_change_pct(conn, batch: int = CHUNK, progress=None) -> int:
    """
    이미 잘못 채워진 등락률을 지웁니다.
    (직전 저장일이 14일 넘게 떨어져 있는데 값이 들어가 있는 경우)
    거래소가 직접 준 값인지 우리가 계산한 값인지 구분할 수 없으므로,
    간격이 벌어진 줄만 비우고 나중에 다시 계산되게 합니다.

    fill_missing_change_pct 와 같은 이유로 종목을 나눠서 처리합니다.
    (한 문장이 2분을 넘기면 Supabase 가 중간에 끊어버립니다)
    """
    _relax_timeout(conn)
    # 여기는 전체 종목을 봐야 합니다. 잘못된 값은 '비어 있지 않은' 줄에
    # 들어 있으므로, 비어 있는 종목만 보면 찾을 수가 없습니다.
    codes = _price_codes(conn)
    if not codes:
        return 0

    total = 0
    for i in range(0, len(codes), batch):
        chunk = codes[i : i + batch]
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH calc AS (
                    SELECT code,
                           trade_date,
                           LAG(trade_date) OVER (PARTITION BY code ORDER BY trade_date) AS prev_date
                      FROM daily_price
                     WHERE code = ANY(%s)
                )
                UPDATE daily_price d
                   SET change_pct = NULL
                  FROM calc c
                 WHERE d.code = c.code
                   AND d.trade_date = c.trade_date
                   AND d.change_pct IS NOT NULL
                   AND c.prev_date IS NOT NULL
                   AND (c.trade_date - c.prev_date) > %s;
                """,
                (chunk, MAX_GAP_DAYS),
            )
            total += cur.rowcount
        conn.commit()
        if progress:
            progress(min(i + batch, len(codes)), len(codes), total)
    return total


# ── 현황 요약 ────────────────────────────────────────────────
def summary(conn) -> dict:
    """지금 창고에 뭐가 얼마나 들어 있는지 요약합니다."""
    (ticker_cnt, active_cnt) = fetch_all(
        conn, "SELECT count(*), count(*) FILTER (WHERE is_active) FROM ticker;"
    )[0]
    (price_cnt, min_d, max_d) = fetch_all(
        conn, "SELECT count(*), min(trade_date), max(trade_date) FROM daily_price;"
    )[0]
    return {
        "ticker_total": ticker_cnt,
        "ticker_active": active_cnt,
        "price_rows": price_cnt,
        "first_date": min_d,
        "last_date": max_d,
    }
