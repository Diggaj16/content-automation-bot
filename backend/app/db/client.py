"""
Legacy Supabase client — retained only for scripts/migrate_from_supabase.py,
the one-time data migration script that reads from Supabase to seed the new
self-hosted Postgres database. Not used by the running application anymore.
"""
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
