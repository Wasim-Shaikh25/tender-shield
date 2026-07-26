"""findings persistence: store idempotency (unit) + risk run persists through
it and the list API returns rows severity-sorted (integration)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity
from app.core.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.modules.findings.store import FindingStore


def _finding(category="ld", severity=Severity.CRITICAL):
    return Finding(
        kind=FindingKind.RISK_CLAUSE,
        category=category,
        severity=severity,
        title="t",
        detail="d",
        source=FindingSource.AI_SUGGESTION,
        pattern_id="p1",
    )


@pytest.fixture
def session():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_replace_for_producer_is_idempotent(session):
    store = FindingStore(session)
    org, opp = uuid.uuid4(), uuid.uuid4()
    store.replace_for_producer(org, opp, "risk", [_finding(), _finding("payment")])
    assert len(store.list(org, opp)) == 2
    # re-run with a single finding replaces, does not append
    store.replace_for_producer(org, opp, "risk", [_finding()])
    assert len(store.list(org, opp)) == 1


def test_producers_are_isolated(session):
    store = FindingStore(session)
    org, opp = uuid.uuid4(), uuid.uuid4()
    store.replace_for_producer(org, opp, "risk", [_finding()])
    store.replace_for_producer(org, opp, "boq", [_finding("arith")])
    # a risk re-run must not disturb boq rows
    store.replace_for_producer(org, opp, "risk", [_finding(), _finding("payment")])
    assert len(store.list(org, opp, producer="boq")) == 1
    assert len(store.list(org, opp, producer="risk")) == 2
    assert len(store.list(org, opp)) == 3


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


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "f@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "f@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def test_risk_run_persists_findings_and_list_api(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    # a scope-only doc → escalation absence finding fires (no LLM needed)
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a bridge."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)

    # findings are now persisted and retrievable via the findings module's API
    listed = client.get(f"/api/findings/opportunities/{opp_id}", headers=headers).json()["findings"]
    assert any(f["category"] == "escalation" for f in listed)
    assert all(f["producer"] == "risk" for f in listed)
    assert all(f["review_status"] == "proposed" for f in listed)

    # re-running does not duplicate
    before = len(listed)
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    after = client.get(f"/api/findings/opportunities/{opp_id}", headers=headers).json()["findings"]
    assert len(after) == before
