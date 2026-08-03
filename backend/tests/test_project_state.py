"""Project state dashboard tests (TS-353 / TS-354)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,boq,baseline,"
    "change,evidence,claims,outcomes,controltower,express,export,drawings,"
    "project_state"
)


@pytest.fixture
def client(tmp_path):
    application = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            storage_type="local",
            storage_dir=str(tmp_path / "storage"),
            rulepacks_dir=str(Path(__file__).resolve().parents[2] / "rulepacks"),
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "state@x.com")


def _create_opp(client, headers, title="T"):
    return client.post(
        "/api/ingestion/opportunities",
        json={"title": title, "jurisdiction": "IN"},
        headers=headers,
    ).json()["id"]


def test_state_draft_no_documents(client):
    headers = _auth(client)
    opp_id = _create_opp(client, headers)
    res = client.get(f"/api/project_state/opportunities/{opp_id}/state", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "draft"
    assert data["health"] == "healthy"
    assert data["next_action"]["label"] == "Upload tender documents"
    assert any(b["kind"] == "no_documents" for b in data["blockers"])


def test_state_ingested_after_document(client):
    headers = _auth(client)
    opp_id = _create_opp(client, headers)
    sample = (
        "The tender is for construction of a bridge. "
        "Submission deadline is 31 December 2025."
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.txt", "sample_text": sample},
        headers=headers,
    )
    res = client.get(f"/api/project_state/opportunities/{opp_id}/state", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "ingested"
    assert data["next_action"]["label"] == "Run risk and BOQ analysis"


def test_state_reviewing_with_unreviewed_findings(client):
    headers = _auth(client)
    opp_id = _create_opp(client, headers)
    # Seed a finding directly through the store.
    from app.core.contracts.findings import (
        Finding,
        FindingKind,
        FindingSource,
        ReviewStatus,
        Severity,
    )
    from app.modules.findings.store import FindingStore

    Session = client.app.state.ctx.registry.require("db.sessionmaker")
    db = Session()
    store = FindingStore(db)
    ws_id = client.get("/api/auth/workspaces", headers=headers).json()[0]["workspace_id"]
    store.replace_for_producer(
        ws_id,
        opp_id,
        "risk",
        [
            Finding(
                kind=FindingKind.RISK_CLAUSE,
                category="payment",
                severity=Severity.HIGH,
                title="Payment delay",
                detail="Net 60 instead of net 30",
                source=FindingSource.DETERMINISTIC_CHECK,
                review_status=ReviewStatus.PROPOSED,
            )
        ],
    )
    res = client.get(f"/api/project_state/opportunities/{opp_id}/state", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["state"] == "reviewing"
    assert data["health"] == "at_risk"
    assert data["unreviewed_finding_count"] == 1


def test_list_and_filter(client):
    headers = _auth(client)
    _create_opp(client, headers, "A")
    opp_b = _create_opp(client, headers, "B")
    sample = "Tender for a building."
    client.post(
        f"/api/ingestion/opportunities/{opp_b}/documents",
        json={"filename": "nit.txt", "sample_text": sample},
        headers=headers,
    )

    res = client.get("/api/project_state/opportunities", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["opportunities"]) == 2
    states = {o["state"] for o in data["opportunities"]}
    assert {"draft", "ingested"} == states

    res = client.get("/api/project_state/opportunities?status=draft", headers=headers)
    assert all(o["state"] == "draft" for o in res.json()["opportunities"])


def test_workspace_summaries(client):
    headers = _auth(client)
    _create_opp(client, headers)
    res = client.get("/api/project_state/workspaces/me/opportunities/state", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["workspaces"]) == 1
    assert data["workspaces"][0]["state_counts"]["draft"] == 1
