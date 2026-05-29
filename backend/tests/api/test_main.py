# tests/api/test_main.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.main import app, create_app


def test_create_app_returns_fastapi_instance():
    assert isinstance(app, FastAPI)


def test_app_title():
    assert app.title == "Content Automation API"


def test_unknown_path_returns_404():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/nonexistent-path-xyz")
    assert resp.status_code == 404


def test_lifespan_sets_arq_pool_attribute():
    """Lifespan must always set arq_pool attribute (None when Redis unavailable)."""
    from app.api.main import create_app
    _app = create_app()
    with TestClient(_app) as client:
        # Redis is not available in CI — arq_pool will be None
        # but the attribute MUST exist on app.state
        assert hasattr(client.app.state, "arq_pool")
