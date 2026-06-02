from supabase import create_client, Client
from app.config import get_settings
from typing import Optional

_client: Optional[Client] = None


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
