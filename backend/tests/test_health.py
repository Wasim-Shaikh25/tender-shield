"""Health / module-discovery endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


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
    r = client.get("/api/health/details")
    assert r.status_code == 200
    names = {m["name"] for m in r.json()["modules"]}
    assert "health" in names
    assert "auth" in names
    assert "findings" in names


def test_health_details_lists_capabilities(client):
    r = client.get("/api/health/details")
    caps = r.json()["capabilities"]
    assert "findings.store_factory" in caps
    assert "auth.authenticate" in caps
