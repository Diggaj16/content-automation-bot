"""
FastAPI dependency-injection helpers.
Centralised so tests can override individual deps cleanly via
app.dependency_overrides[original_dep] = lambda: mock_value.
"""
from fastapi import Request
from supabase import Client

from app.config import Settings, get_settings as _get_settings
from app.db.client import get_supabase_client


def get_settings() -> Settings:
    return _get_settings()


def get_supabase() -> Client:
    return get_supabase_client()


def get_arq_pool(request: Request):
    """Returns the arq pool stored in app.state, or None if Redis is unavailable."""
    return getattr(request.app.state, "arq_pool", None)
