"""Cross-reference search and clause change detection (TS-053 + TS-051)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,crossref",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "cr@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "cr@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _opp_with_docs(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay the contractor "
                "within 30 days of the running account bill.\n"
                "[p2]\n"
                "Clause 2 - Scope. The contractor shall build a bridge.\n"
            ),
        },
        headers=headers,
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "scc.pdf",
            "sample_text": (
                "[p1]\nClause A - Payment terms. Interest at 12% per annum on delayed payments.\n"
            ),
        },
        headers=headers,
    )
    return opp_id


def test_cross_reference_search(client):
    headers = _auth(client)
    opp_id = _opp_with_docs(client, headers)

    resp = client.get(f"/api/crossref/opportunities/{opp_id}?q=payment&limit=10", headers=headers)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 2
    texts = " ".join(r["text"].lower() for r in results)
    assert "payment" in texts


def test_change_detection_by_supersedes(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Road"}, headers=headers
    ).json()["id"]

    old = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay within 30 days.\n"
                "[p2]\n"
                "Clause 2 - Scope. Build a road.\n"
            ),
        },
        headers=headers,
    ).json()

    new = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc_v2.pdf",
            "supersedes": old["id"],
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay within 45 days.\n"
                "[p2]\n"
                "Clause 3 - LD. Liquidated damages at 0.5% per week.\n"
            ),
        },
        headers=headers,
    ).json()

    diff = client.post(
        f"/api/crossref/opportunities/{opp_id}/diff?document_id={new['id']}",
        headers=headers,
    ).json()
    assert "added" in diff and "removed" in diff and "changed" in diff
    assert any("45 days" in c["new"]["text"] for c in diff["changed"])
    assert any(c.get("heading") and "Scope" in c["heading"] for c in diff["removed"])
