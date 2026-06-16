from supabase import create_client, Client
from app.config import get_settings
from functools import lru_cache
from typing import Optional

_client: Optional[Client] = None


@lru_cache(maxsize=128)
def table_has_column(table: str, column: str) -> bool:
    """
    Return True if `table.column` exists in the live database.

    Used to keep writes compatible with databases where an optional migration
    (e.g. 005's target_persona / compliance_status) has not been applied yet.
    Result is cached per (table, column); restart the process to re-probe after
    applying a migration.
    """
    try:
        get_supabase_client().table(table).select(column).limit(1).execute()
        return True
    except Exception:
        return False


def get_supabase_client() -> Client:
    """
    Returns a singleton Supabase client using the service role key.
    Service role bypasses Row Level Security — correct for backend agents.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client


def reset_client() -> None:
    """Force a new client on next call. Clears stale connections and is used in tests."""
    global _client
    _client = None


def get_supabase_client_fresh() -> Client:
    """Force a fresh client (drops stale httpx connection pool). Use after connection errors."""
    reset_client()
    return get_supabase_client()
