"""
Shared Postgres connection helper for the FastAPI routers.

Uses a small connection pool so each request doesn't open a brand-new
connection to Supabase. Reads DATABASE_URL from .env (same variable
load_to_postgres.py uses).
"""

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Missing DATABASE_URL. Add it to your .env file, e.g.:\n"
        "DATABASE_URL=postgresql://user:password@host:5432/dbname"
    )

# minconn=1, maxconn=5 is plenty for local dev / a small demo deployment.
_pool = pool.SimpleConnectionPool(1, 5, DATABASE_URL)


@contextmanager
def get_cursor():
    """
    Usage:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM dim_vessel")
            rows = cur.fetchall()
    Rows come back as dicts (RealDictCursor), so they serialize straight to
    JSON via FastAPI/Pydantic without extra conversion.
    """
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
