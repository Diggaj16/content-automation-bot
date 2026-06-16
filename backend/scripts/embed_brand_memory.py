"""
Backfill embeddings for brand_memory rows that have none.

brand_memory rows are seeded (seed.py) and appended by the publishing flow
WITHOUT embeddings. The match_brand_memory RPC does a vector similarity search,
so rows with a NULL embedding can never be retrieved — brand context is silently
empty until this backfill runs.

Run from backend/ with venv active (or inside the api container):
    python scripts/embed_brand_memory.py

Idempotent: only rows with a NULL/empty embedding are processed.
Uses the same embedding client as the live agents (Gemini 768-dim, local fallback),
so query and document vectors stay dimension-compatible.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.db.client import get_supabase_client
from app.agents.embedding.client import make_embed_client


def main() -> None:
    settings = get_settings()
    db = get_supabase_client()
    client = make_embed_client(
        google_api_key=settings.google_api_key,
        local_model=settings.local_embedding_model,
    )

    rows = db.table("brand_memory").select("id,content,embedding").execute().data or []
    pending = [r for r in rows if not r.get("embedding") and (r.get("content") or "").strip()]
    print(f"brand_memory: {len(rows)} total, {len(pending)} need embedding")

    if not pending:
        print("Nothing to backfill. Done.")
        return

    # Batch-embed all pending contents in one call (document vectors, for_query=False)
    texts = [r["content"] for r in pending]
    vectors = client.embed(texts, for_query=False)

    updated = 0
    for row, vec in zip(pending, vectors):
        if not vec:
            print(f"  SKIP {row['id']}: embedding returned empty")
            continue
        try:
            db.table("brand_memory").update({"embedding": vec}).eq("id", row["id"]).execute()
            updated += 1
            print(f"  OK   {row['id']}  ({len(vec)}-dim)  {row['content'][:50]!r}")
        except Exception as exc:
            print(f"  FAIL {row['id']}: {exc}")

    print(f"\nBackfill complete. {updated}/{len(pending)} rows embedded.")


if __name__ == "__main__":
    main()
