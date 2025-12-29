from contextlib import contextmanager
import psycopg
from .settings import psycopg_dsn

@contextmanager
def db_conn():
    conn = psycopg.connect(psycopg_dsn())
    try:
        yield conn
    finally:
        conn.close()
