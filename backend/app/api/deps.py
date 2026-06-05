"""
FastAPI dependency-injection helpers.
Centralised so tests can override individual deps cleanly via
app.dependency_overrides[original_dep] = lambda: mock_value.
"""
from fastapi import Depends, Header, HTTPException, Request
from supabase import Client
from typing import Optional

from app.config import Settings, get_settings as _get_settings
from app.db.client import get_supabase_client
import hmac
import secrets

def get_settings() -> Settings:
    return _get_settings()


def get_supabase() -> Client:
    return get_supabase_client()


def get_arq_pool(request: Request):
    """Returns the arq pool stored in app.state, or None if Redis is unavailable."""
    return getattr(request.app.state, "arq_pool", None)


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Optional API key guard. Enforced only when API_KEY is set in environment.
    Set API_KEY=<secret> to require X-Api-Key: <secret> on all requests.
    Leave unset for local development (all requests allowed).
    """
    if settings.api_key is None:
        return  # no key configured — dev mode, allow all
    if not hmac.compare_digest(x_api_key or "", settings.api_key or ""):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
