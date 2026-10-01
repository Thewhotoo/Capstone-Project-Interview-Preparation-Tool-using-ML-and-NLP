"""
Database setup — SQLite via Flask-SQLAlchemy, schema versioned with
Flask-Migrate (Alembic).

SQLite was chosen for this stage of the project: nothing to install, the
whole database is one file under `instance/`, and it comfortably handles
this app's write pattern (one row per answered question). Everything goes
through SQLAlchemy, so moving to PostgreSQL later is a change of
`CAP_DATABASE_URL`, not of code.

Everything the app stores on disk at runtime lives under `instance/`
(git-ignored): the database file, uploaded resumes, and the generated
Flask secret key.
"""

from __future__ import annotations

import os
import secrets
import sqlite3

from flask import Flask
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")
DEFAULT_DATABASE_URL = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
DEFAULT_UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")
_SECRET_KEY_FILE = os.path.join(INSTANCE_DIR, "secret_key")

db = SQLAlchemy()
migrate = Migrate()


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record):
    """SQLite ignores foreign keys unless asked per connection -- without
    this, ON DELETE CASCADE (account/session deletion) silently does
    nothing. WAL lets readers proceed while a request is writing."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _load_or_create_secret_key() -> str:
    """`CAP_SECRET_KEY` if set; otherwise a random key generated once and
    kept in `instance/secret_key`, so login sessions survive a restart."""
    from_env = os.environ.get("CAP_SECRET_KEY", "").strip()
    if from_env:
        return from_env
    if os.path.exists(_SECRET_KEY_FILE):
        with open(_SECRET_KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    key = secrets.token_hex(32)
    with open(_SECRET_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key)
    return key


def configure_database(
    app: Flask,
    *,
    database_url: str | None = None,
    upload_dir: str | None = None,
    auto_upgrade: bool = True,
) -> None:
    """Bind the database to `app`.

    `auto_upgrade` applies any pending migrations at startup, so a fresh
    clone (or a teammate pulling a schema change) needs no manual
    `flask db upgrade`. Tests pass `auto_upgrade=False` and an in-memory
    `database_url`, then call `db.create_all()` themselves.
    """
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        database_url or os.environ.get("CAP_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    app.config.setdefault("UPLOAD_DIR", upload_dir or os.environ.get("CAP_UPLOAD_DIR", DEFAULT_UPLOAD_DIR))
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_or_create_secret_key()
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # Imported for its side effect: registers every table on `db.metadata`
    # before migrations or create_all() look at it.
    import models  # noqa: F401

    db.init_app(app)
    # render_as_batch: SQLite can't ALTER most column properties in place;
    # batch mode makes Alembic recreate the table instead.
    migrate.init_app(app, db, directory=MIGRATIONS_DIR, render_as_batch=True)

    if auto_upgrade:
        with app.app_context():
            upgrade(directory=MIGRATIONS_DIR)
