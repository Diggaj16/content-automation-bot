"""
One-shot schema bootstrap for a brand new database — SQLAlchemy models only.

Creates the pgvector extension, then creates every table/index defined in
app.db.orm. Idempotent for a missing table, but it does NOT apply incremental
changes to a table that already exists with an older shape — it has no
concept of migrations, just "create what's not there yet".

Superseded by Alembic (see backend/alembic/) for anything beyond a fresh DB:
    alembic upgrade head

Kept around as a quick way to stand up a throwaway/local DB without touching
alembic_version bookkeeping. If you use this on a fresh DB, run
`alembic stamp head` afterward so Alembic knows it's already current.

Run from backend/ (or inside a container) with DATABASE_URL set:
    python scripts/init_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.db.base import Base
from app.db.session import get_engine
import app.db.orm  # noqa: F401 — registers all models on Base.metadata


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    table_names = sorted(Base.metadata.tables.keys())
    print(f"Schema initialized. {len(table_names)} tables:")
    for t in table_names:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
