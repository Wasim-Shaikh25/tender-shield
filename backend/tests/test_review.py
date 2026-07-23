"""Review workbench: export gate + accept/reject flow with audit, through the
app (auth-gated, findings persisted by a risk run)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
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
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,review",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "r@x.com", "password": "hunter2hunter2", "org_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "r@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a bridge."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def test_gate_blocks_until_all_reviewed(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)

    gate = client.get(f"/api/review/opportunities/{opp_id}/gate", headers=headers).json()
    assert gate["total"] >= 1
    assert gate["pending"] == gate["total"]
    assert gate["export_allowed"] is False  # nothing reviewed yet

    queue = client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()
    for f in queue["findings"]:
        r = client.post(
            f"/api/review/findings/{f['id']}",
            json={"decision": "accepted"},
            headers=headers,
        )
        assert r.status_code == 200

    gate2 = client.get(f"/api/review/opportunities/{opp_id}/gate", headers=headers).json()
    assert gate2["pending"] == 0
    assert gate2["export_allowed"] is True


def test_review_writes_audit_trail(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    fid = client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ][0]["id"]
    client.post(
        f"/api/review/findings/{fid}",
        json={"decision": "rejected", "note": "not a risk here"},
        headers=headers,
    )
    audit = client.get(f"/api/review/opportunities/{opp_id}/audit", headers=headers).json()["audit"]
    assert any(a["action"] == "finding.rejected" for a in audit)


def test_bad_decision_and_missing_finding(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    fid = client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ][0]["id"]
    bad = client.post(
        f"/api/review/findings/{fid}", json={"decision": "banana"}, headers=headers
    )
    assert bad.status_code == 400
    missing = "00000000-0000-0000-0000-0000000000ff"
    gone = client.post(
        f"/api/review/findings/{missing}", json={"decision": "accepted"}, headers=headers
    )
    assert gone.status_code == 404
