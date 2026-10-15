"""
Which database the tests run against.

By default every test uses an in-memory SQLite database. Set
`CAP_TEST_DATABASE_URL` to a PostgreSQL URL to run the same tests on
PostgreSQL, e.g.

    CAP_TEST_DATABASE_URL=postgresql+psycopg://cap:cap@localhost:5432/cap_test

Two separate PostgreSQL databases are used, so the two kinds of test can't
drop each other's tables when pytest runs them in one process:
  - APP_DATABASE_URL  (`cap_test`): the real app.py, migrated once per run
    (`_app_test_setup.py`);
  - UNIT_DATABASE_URL (`cap_test_unit`): tests that build their own Flask app
    and create / drop all tables around every test (`test_accounts.py`).
Both are created if missing and emptied at the start of a run.

Not a test module itself (no `test_` prefix).
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

_CONFIGURED = os.environ.get("CAP_TEST_DATABASE_URL", "").strip()
IS_POSTGRES = _CONFIGURED.startswith("postgresql")

if IS_POSTGRES:
    _base = make_url(_CONFIGURED)
    APP_DATABASE_URL = _base.render_as_string(hide_password=False)
    UNIT_DATABASE_URL = _base.set(database=f"{_base.database}_unit").render_as_string(hide_password=False)
else:
    APP_DATABASE_URL = UNIT_DATABASE_URL = "sqlite://"


def _reset_postgres_database(url: str) -> None:
    """Create the database if it doesn't exist, then empty it (drop and
    recreate the public schema) so every run starts clean."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"),
                              {"n": target.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()

    engine = create_engine(target, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


if IS_POSTGRES:
    _reset_postgres_database(APP_DATABASE_URL)
    _reset_postgres_database(UNIT_DATABASE_URL)
