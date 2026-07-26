"""Analytics: admin-only internal accuracy dashboard."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import app.modules.analytics.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.auth.security as sec  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,drafting,analytics"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _owner(client):
    client.post(
        "/api/auth/signup",
        json={"email": "owner@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login",
        json={"email": "owner@x.com", "password": "hunter2hunter2"},
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _viewer_headers(client):
    keys: sec.KeyPair = client.app.state.ctx.registry.require("auth.keys")
    tok = sec.mint_access(
        keys,
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-0000000000aa",
        role="viewer",
        ttl=timedelta(minutes=5),
    )
    return {"authorization": f"Bearer {tok}"}


def _opp_with_findings(client, headers, title):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": title}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a bridge.\n"},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def test_accuracy_dashboard_admin_only(client):
    owner = _owner(client)
    opp1 = _opp_with_findings(client, owner, "Bridge")
    opp2 = _opp_with_findings(client, owner, "Road")

    f1 = client.get(f"/api/review/opportunities/{opp1}/queue", headers=owner).json()["findings"][0]
    client.post(f"/api/review/findings/{f1['id']}", json={"decision": "accepted"}, headers=owner)

    f2 = client.get(f"/api/review/opportunities/{opp2}/queue", headers=owner).json()["findings"][0]
    client.post(
        f"/api/review/findings/{f2['id']}", json={"decision": "false_positive"}, headers=owner
    )

    resp = client.get("/api/analytics/accuracy", headers=owner)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total_findings"] == 2
    assert body["summary"]["false_positive_count"] == 1
    assert 0 < body["summary"]["precision"] < 1
    assert body["summary"]["recall"] is None
    assert body["per_pattern"]
    assert body["per_source"]
    assert body["most_rejected"]
    assert any(r["rejections"] == 1 for r in body["most_rejected"])

    # viewer cannot access
    viewer = _viewer_headers(client)
    assert client.get("/api/analytics/accuracy", headers=viewer).status_code == 403


def test_accuracy_dashboard_empty(client):
    owner = _owner(client)
    resp = client.get("/api/analytics/accuracy", headers=owner)
    assert resp.status_code == 200
    assert resp.json()["summary"]["total_findings"] == 0
