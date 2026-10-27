"""
Copy all app data from one database to another, for example from the local
SQLite file to PostgreSQL (production mode / Docker): accounts, profiles,
profile photos, resumes, interview sessions and their turns, plus the uploaded
resume files. IDs are kept, so everything stays linked.

    python copy_database.py --from sqlite:///instance/app.db --from-uploads instance/uploads
        [--to postgresql+psycopg://...] [--to-uploads DIR] [--replace]

`--to` / `--to-uploads` default to CAP_DATABASE_URL / CAP_UPLOAD_DIR, so inside
the Docker app container only the source is needed (README, "Production mode
with Docker"). The target schema is brought up to date first. The target must be
empty unless `--replace` is given, which first deletes everything in it.

Live interview state (Redis) is not copied: interviews still in progress in the
source show as they are in its database.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from sqlalchemy import String, create_engine, delete, func, insert, select, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database import DEFAULT_UPLOAD_DIR  # noqa: E402
from models import InterviewSession, Resume, SessionTurn, StudentProfile, User  # noqa: E402

# Parents before children (foreign keys).
MODELS = (User, StudentProfile, Resume, InterviewSession, SessionTurn)


def _upgrade_schema(url: str, upload_dir: str) -> None:
    """Create / migrate the target's tables with the app's own migrations."""
    from flask import Flask

    from account_routes import init_accounts

    init_accounts(Flask(__name__), database_url=url, upload_dir=upload_dir)


def _fit(table, row: dict) -> dict:
    # SQLite never enforced VARCHAR lengths; PostgreSQL does (see models.py).
    for column in table.columns:
        value = row.get(column.name)
        if isinstance(column.type, String) and column.type.length and isinstance(value, str):
            row[column.name] = value[: column.type.length]
    if table.name == Resume.__tablename__ and row.get("file_path"):
        row["file_path"] = row["file_path"].replace("\\", "/")
    return row


def copy_database(source_url: str, target_url: str, source_uploads: str | None,
                  target_uploads: str, replace: bool) -> dict[str, int]:
    _upgrade_schema(target_url, target_uploads)
    source, target = create_engine(source_url), create_engine(target_url)
    counts = {}
    with source.connect() as src, target.begin() as dst:
        existing = sum(dst.execute(select(func.count()).select_from(m.__table__)).scalar() for m in MODELS)
        if existing and not replace:
            raise SystemExit(f"The target already has {existing} rows. Use --replace to delete them first.")
        for model in reversed(MODELS):
            dst.execute(delete(model.__table__))
        for model in MODELS:
            table = model.__table__
            rows = [_fit(table, dict(r._mapping)) for r in src.execute(select(table).order_by(table.c.id))]
            if rows:
                dst.execute(insert(table), rows)
            counts[table.name] = len(rows)
            if target.dialect.name == "postgresql":   # next new row continues after the copied ids
                dst.execute(text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                                 f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"))

    resumes_dir = os.path.join(target_uploads, "resumes")
    if replace:
        shutil.rmtree(resumes_dir, ignore_errors=True)
    copied = 0
    if source_uploads:
        with source.connect() as src:
            for (path,) in src.execute(select(Resume.__table__.c.file_path)):
                parts = path.replace("\\", "/").split("/")
                src_file = os.path.join(source_uploads, *parts)
                if os.path.exists(src_file):
                    dst_file = os.path.join(target_uploads, *parts)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    copied += 1
                else:
                    print(f"warning: resume file missing in the source: {path}")
    counts["resume files"] = copied
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("--from", dest="source", required=True, help="source database URL")
    parser.add_argument("--from-uploads", help="source upload folder (holds resumes/)")
    parser.add_argument("--to", dest="target", default=os.environ.get("CAP_DATABASE_URL"),
                        help="target database URL (default: CAP_DATABASE_URL)")
    parser.add_argument("--to-uploads", default=os.environ.get("CAP_UPLOAD_DIR", DEFAULT_UPLOAD_DIR),
                        help="target upload folder (default: CAP_UPLOAD_DIR)")
    parser.add_argument("--replace", action="store_true", help="delete everything in the target first")
    args = parser.parse_args()
    if not args.target:
        parser.error("--to is required when CAP_DATABASE_URL is not set")
    if args.source == args.target:
        parser.error("source and target are the same database")
    counts = copy_database(args.source, args.target, args.from_uploads, args.to_uploads, args.replace)
    for name, n in counts.items():
        print(f"{name}: {n}")


if __name__ == "__main__":
    main()
