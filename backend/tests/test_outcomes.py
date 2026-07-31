"""outcomes module tests (TS-215)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.outcomes.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,findings,risk,outcomes,marketdata"


@pytest.fixture
def client():
    app = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_record_and_read_bid_outcome(client):
    headers = auth_headers(client, f"out-{uuid.uuid4().hex[:8]}@example.com")
    opp = str(uuid.uuid4())

    recorded = client.post(
        f"/api/outcomes/opportunities/{opp}",
        headers=headers,
        json={"result": "lost", "quoted_value_minor": 5_000_000, "currency": "INR"},
    )
    assert recorded.status_code == 200
    assert recorded.json()["result"] == "lost"

    read = client.get(f"/api/outcomes/opportunities/{opp}", headers=headers)
    assert read.status_code == 200
    assert read.json()["outcome"]["result"] == "lost"
    assert read.json()["outcome"]["quoted_value_minor"] == 5_000_000


def test_mark_finding_materialized(client):
    headers = auth_headers(client, f"mat-{uuid.uuid4().hex[:8]}@example.com")
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Outcomes tender"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — LD at 0.5% per week."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    finding_id = client.get(
        f"/api/findings/opportunities/{opp_id}", headers=headers
    ).json()["findings"][0]["id"]

    resp = client.post(
        f"/api/outcomes/findings/{finding_id}/materialized",
        headers=headers,
        json={
            "opportunity_id": opp_id,
            "materialized": True,
            "impact_amount_minor": 250_000,
            "currency": "INR",
            "narrative": "LD invoked at practical completion",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["materialized"] is True

    read = client.get(f"/api/outcomes/opportunities/{opp_id}", headers=headers).json()
    assert len(read["materializations"]) == 1


def test_outcomes_isolated_between_workspaces(client):
    headers_a = auth_headers(client, f"wa-{uuid.uuid4().hex[:8]}@example.com")
    headers_b = auth_headers(client, f"wb-{uuid.uuid4().hex[:8]}@example.com")
    opp = str(uuid.uuid4())

    client.post(
        f"/api/outcomes/opportunities/{opp}",
        headers=headers_a,
        json={"result": "won"},
    )
    read_b = client.get(f"/api/outcomes/opportunities/{opp}", headers=headers_b)
    assert read_b.status_code == 200
    assert read_b.json()["outcome"] is None
