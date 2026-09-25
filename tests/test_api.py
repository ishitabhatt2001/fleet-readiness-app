"""
Basic smoke tests. Run with:
    pip install httpx pytest
    pytest
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_vessels():
    resp = client.get("/vessels/")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_readiness():
    resp = client.get("/maintenance/readiness")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_query_stub():
    resp = client.post("/query/", json={"question": "Which vessels need maintenance?"})
    assert resp.status_code == 200
    assert "answer" in resp.json()
