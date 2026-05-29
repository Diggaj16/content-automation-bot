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
