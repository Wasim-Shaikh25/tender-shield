"""express module tests (TS-208/209/210)."""


import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.express.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app

_GCC_SAMPLE = """
[p1]
Notice Inviting Tender
Last date of submission: 15 August 2026
Clause 5 — Scope. Build a bridge on a firm price basis and no escalation shall be payable.
"""


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,auth,rulepacks,ingestion,findings,risk,express",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_express_status(client):
    body = client.get("/api/express").json()
    assert body["status"] == "ready"
    assert body["max_upload_bytes"] > 0


def test_create_session_requires_acknowledgment(client):
    denied = client.post(
        "/api/express/sessions",
        json={"email": "visitor@example.com", "tier": "snapshot", "acknowledgment": {}},
    )
    assert denied.status_code == 422


def test_create_upload_and_fetch_session(client):
    created = client.post(
        "/api/express/sessions",
        json={
            "email": "visitor@example.com",
            "tier": "snapshot",
            "acknowledgment": {"accepted": True, "text_version": "express-unreviewed-v1"},
        },
    )
    assert created.status_code == 200
    token = created.json()["token"]
    assert len(token) > 20

    uploaded = client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("gcc.txt", _GCC_SAMPLE.encode(), "text/plain")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["sha256"]

    fetched = client.get(f"/api/express/sessions/{token}")
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "uploaded"


def test_teaser_renders_without_auth(client):
    token = client.post(
        "/api/express/sessions",
        json={
            "email": "teaser@example.com",
            "tier": "risk",
            "acknowledgment": {"accepted": True},
        },
    ).json()["token"]
    client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("gcc.txt", _GCC_SAMPLE.encode(), "text/plain")},
    )
    teaser = client.get(f"/api/express/sessions/{token}/teaser")
    assert teaser.status_code == 200
    body = teaser.json()
    assert body["state"] == "teaser_ready"
    assert body["teaser"]["missing_documents"]["expected"]
    assert body["teaser"]["sample_findings"] is not None
    assert len(body["teaser"]["deadlines"]) >= 1


def test_upload_rejects_oversized_payload(client):
    created = client.post(
        "/api/express/sessions",
        json={
            "email": "big@example.com",
            "tier": "snapshot",
            "acknowledgment": {"accepted": True},
        },
    ).json()
    token = created["token"]
    huge = b"x" * (26 * 1024 * 1024)
    resp = client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("big.bin", huge, "application/octet-stream")},
    )
    assert resp.status_code == 413
