"""PostgreSQL access layer.

Keeps the small API the routes were written against with sqlite3:
    conn = get_db_connection()
    row = conn.execute('SELECT ... WHERE id = ?', (x,)).fetchone()
    row['col']
    conn.commit(); conn.close()

`?` placeholders are translated to psycopg's `%s`. Dates and timestamps come back
as ISO strings and NUMERIC values as floats, so templates, JSON responses and
datetime.fromisoformat() keep working unchanged.
"""
import os
from datetime import date, datetime
from decimal import Decimal

import psycopg

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

DATABASE_URL = os.getenv(
    'DATABASE_URL', 'postgresql://tt_app:tt_app@localhost:5432/tt_network'
)


def _normalize(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat(sep=' ', timespec='seconds')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_factory(cursor):
    names = [c.name for c in cursor.description] if cursor.description else []

    def make_row(values):
        return {n: _normalize(v) for n, v in zip(names, values)}

    return make_row


class Connection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        cur = self._raw.cursor(row_factory=_row_factory)
        cur.execute(sql.replace('?', '%s'), params)
        return cur

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


class _Cursor:
    """Minimal stand-in for `conn.cursor()` users (cur.execute then cur.fetchall)."""

    def __init__(self, conn):
        self._conn = conn
        self._cur = None

    def execute(self, sql, params=None):
        self._cur = self._conn.execute(sql, params)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()


def get_db_connection():
    return Connection(psycopg.connect(DATABASE_URL))
