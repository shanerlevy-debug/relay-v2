"""Smoke test for /api/health.

Runs without a live database — the route's DB check tolerates a down
Postgres and reports `db: "down"` rather than 5xx-ing.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from relay_api.main import app


def test_health_returns_200_and_version() -> None:
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "db" in body
    assert body["db"] in ("ok", "down")
