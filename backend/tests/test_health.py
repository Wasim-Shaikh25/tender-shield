"""Health / module-discovery endpoint."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec


def _superadmin_headers(client):
    keys = client.app.state.ctx.registry.require("auth.keys")
    token = sec.mint_access(
        keys,
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-0000000000aa",
        role="viewer",
        is_superadmin=True,
        ttl=timedelta(minutes=5),
    )
    return {"authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_health_returns_ok_and_version(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_details_list_modules(client):
    r = client.get("/api/health/details", headers=_superadmin_headers(client))
    assert r.status_code == 200
    names = {m["name"] for m in r.json()["modules"]}
    assert "health" in names
    assert "auth" in names
    assert "findings" in names


def test_health_details_lists_capabilities(client):
    r = client.get("/api/health/details", headers=_superadmin_headers(client))
    caps = r.json()["capabilities"]
    assert "findings.store_factory" in caps
    assert "auth.authenticate" in caps


def test_health_live_returns_ok(client):
    r = client.get("/api/health/live")
    assert r.status_code == 200
    assert r.text == "ok"


def test_health_ready_returns_ok(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["dependencies"]["database"]["status"] == "ok"
    assert data["dependencies"]["redis"]["status"] == "skipped"
    assert data["dependencies"]["storage"]["status"] == "ok"
    assert data["dependencies"]["celery"]["status"] == "ok"


def test_health_metrics_returns_prometheus_text(client):
    # Trigger a request so the middleware records it.
    client.get("/api/health")
    r = client.get("/api/health/metrics")
    assert r.status_code == 200
    text = r.text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text
