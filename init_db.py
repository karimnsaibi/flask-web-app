"""Create (or reset) the PostgreSQL schema, the BI views and the Power BI reader role.

    docker compose up -d
    python init_db.py          # drops and recreates everything
    python seed_data.py        # fills it with demo data
"""
import os
from pathlib import Path

import psycopg
from psycopg import sql

from db import DATABASE_URL

SQL_DIR = Path(__file__).resolve().parent / 'sql'
POWERBI_ROLE = 'powerbi_reader'


def init_db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute((SQL_DIR / 'schema.sql').read_text(encoding='utf-8'))
        conn.execute((SQL_DIR / 'bi_views.sql').read_text(encoding='utf-8'))
        print('Schema and BI views created.')

        pw = os.getenv('POWERBI_PASSWORD')
        if not pw:
            print('POWERBI_PASSWORD not set: skipped the read-only Power BI role.')
            return
        exists = conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (POWERBI_ROLE,)).fetchone()
        verb = 'ALTER' if exists else 'CREATE'
        conn.execute(sql.SQL(verb + ' ROLE {} LOGIN PASSWORD {}').format(
            sql.Identifier(POWERBI_ROLE), sql.Literal(pw)))
        db_name = conn.execute('SELECT current_database()').fetchone()[0]
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
            sql.Identifier(db_name), sql.Identifier(POWERBI_ROLE)))
        # The views run with the owner's rights, so the reader only needs the bi schema.
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA bi TO {}').format(sql.Identifier(POWERBI_ROLE)))
        conn.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA bi TO {}').format(sql.Identifier(POWERBI_ROLE)))
        print(f"Read-only role '{POWERBI_ROLE}' ready (bi schema only).")


if __name__ == '__main__':
    init_db()
