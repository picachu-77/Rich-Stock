"""
데이터베이스(창고) 접속 담당 파일.

하는 일: 데이터베이스에 접속하는 통로를 열고 닫는 일을 대신해 줍니다.
        Postgres 면 어디든 됩니다 (Neon · Supabase 등). 연결 문자열만 바꾸면
        코드는 그대로 씁니다.
다른 파일들은 여기 있는 get_conn() 만 쓰면 됩니다.
"""

from contextlib import contextmanager

import psycopg2
from psycopg2.extras import execute_values

from .config import DB_BATCH_SIZE, get_database_url


@contextmanager
def get_conn():
    """
    데이터베이스에 접속한 뒤, 작업이 끝나면 자동으로 저장(commit)하고 연결을 닫습니다.
    중간에 오류가 나면 저장하지 않고 되돌립니다(rollback) — 데이터가 반쯤
    들어가서 망가지는 일을 막기 위해서입니다.

    사용 예:
        with get_conn() as conn:
            ...
    """
    conn = psycopg2.connect(get_database_url(), connect_timeout=20)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_sql(conn, sql: str, params=None):
    """SQL 한 문장을 실행합니다."""
    with conn.cursor() as cur:
        cur.execute(sql, params)


def fetch_all(conn, sql: str, params=None):
    """SQL 실행 결과를 목록으로 돌려줍니다."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(conn, sql: str, params=None):
    """SQL 실행 결과의 첫 줄만 돌려줍니다."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def bulk_upsert(conn, sql_template: str, rows) -> int:
    """
    여러 줄을 한 번에 저장합니다.

    'upsert' 란: 없으면 새로 넣고(insert), 이미 있으면 덮어쓰는(update) 방식.
    같은 날짜의 같은 종목을 두 번 수집해도 중복이 생기지 않는 이유가 이것입니다.
    """
    rows = list(rows)
    if not rows:
        return 0
    with conn.cursor() as cur:
        execute_values(cur, sql_template, rows, page_size=DB_BATCH_SIZE)
    return len(rows)


def test_connection() -> str:
    """접속이 잘 되는지 확인하고 데이터베이스 버전을 돌려줍니다."""
    with get_conn() as conn:
        (version,) = fetch_one(conn, "SELECT version();")
    return version
