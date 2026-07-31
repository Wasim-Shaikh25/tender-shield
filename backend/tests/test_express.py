"""express module scaffold tests (TS-208)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.express.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,express",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_express_status(client):
    body = client.get("/api/express").json()
    assert body["status"] == "scaffold"


def test_create_and_fetch_session(client):
    ws = str(uuid.uuid4())
    created = client.post(
        "/api/express/sessions",
        json={
            "email": "visitor@example.com",
            "tier": "snapshot",
            "acknowledgment": {"version": "v1", "accepted": True},
            "workspace_id": ws,
        },
    )
    assert created.status_code == 200
    token = created.json()["token"]
    assert len(token) > 20

    fetched = client.get(f"/api/express/sessions/{token}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "visitor@example.com"
