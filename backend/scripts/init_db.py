"""
Initialize the Postgres schema from the SQLAlchemy models.

Creates the pgvector extension, then creates every table/index defined in
app.db.orm. Idempotent — existing tables are left untouched (create_all only
creates what's missing).

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
