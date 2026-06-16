"""
One-time data migration: copy every row from the hosted Supabase project into
the self-hosted Postgres database.

Reads via the Supabase REST client (service-role key — no direct Postgres
password needed) and writes via SQLAlchemy Core, preserving original ids and
timestamps. Tables are migrated in FK-dependency order. Idempotent per row:
existing primary keys are skipped (ON CONFLICT DO NOTHING).

Prereqs:
    - SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY set (source)
    - DATABASE_URL set + schema already created (run init_db.py first)

Run from backend/:
    python scripts/migrate_from_supabase.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import Base
from app.db.session import get_engine
import app.db.orm  # noqa: F401 — registers tables on Base.metadata
from app.db.client import get_supabase_client

# FK-safe order: parents before children
MIGRATION_ORDER = [
    "curated_sites",
    "raw_content",
    "ideas",
    "user_decision_summaries",
    "drafts",
    "published_posts",
    "content_analytics",
    "email_subscribers",
    "style_guide",
    "topic_performance_model",
    "brand_memory",
    "knowledge_base",
    "run_logs",
    "site_health_log",
    "cost_log",
]

_PAGE = 1000


def _fetch_all(supabase, table_name: str) -> list[dict]:
    """Page through every row of a Supabase table via the REST client."""
    rows: list[dict] = []
    start = 0
    while True:
        resp = (
            supabase.table(table_name)
            .select("*")
            .range(start, start + _PAGE - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < _PAGE:
            break
        start += _PAGE
    return rows


def main() -> None:
    supabase = get_supabase_client()
    engine = get_engine()
    metadata_tables = Base.metadata.tables

    grand_total = 0
    for table_name in MIGRATION_ORDER:
        table = metadata_tables[table_name]
        valid_cols = set(table.columns.keys())

        try:
            rows = _fetch_all(supabase, table_name)
        except Exception as exc:
            print(f"  SKIP {table_name}: source read failed — {str(exc)[:80]}")
            continue

        if not rows:
            print(f"  --   {table_name}: 0 rows")
            continue

        # Drop any keys not present in the target schema (defensive)
        cleaned = [{k: v for k, v in r.items() if k in valid_cols} for r in rows]

        inserted = 0
        with engine.begin() as conn:
            # Insert in chunks; skip rows whose PK already exists
            for i in range(0, len(cleaned), 500):
                chunk = cleaned[i : i + 500]
                stmt = pg_insert(table).values(chunk).on_conflict_do_nothing(index_elements=["id"])
                result = conn.execute(stmt)
                inserted += result.rowcount if result.rowcount and result.rowcount > 0 else 0

        grand_total += len(cleaned)
        print(f"  OK   {table_name}: {len(cleaned)} read, {inserted} inserted (rest already present)")

    print(f"\nMigration complete. {grand_total} source rows processed.")


if __name__ == "__main__":
    main()
