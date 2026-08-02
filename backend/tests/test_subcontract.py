"""Subcontract control tests (TS-288 / TS-289 / TS-304)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,standards,baseline,change,"
    "subcontract"
)


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "subcontract@x.com")


def _opp(client, headers):
    r = client.post("/api/ingestion/opportunities", json={"title": "Tower"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_subcontract_crud_and_analysis(client):
    auth = _auth(client)
    opp_id = _opp(client, auth)

    # Create
    r = client.post(
        f"/api/subcontract/opportunities/{opp_id}/subcontracts",
        json={
            "subcontractor_name": "Steel Bros",
            "reference": "SUB-001",
            "contract_value_minor": 50000000,
            "currency": "INR",
            "scope": "Structural steel",
            "notice_buffer_days": 7,
            "postal_buffer_days": 2,
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    sub_id = r.json()["id"]

    # List
    r = client.get(f"/api/subcontract/opportunities/{opp_id}/subcontracts", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["subcontracts"]) == 1

    # Get
    r = client.get(f"/api/subcontract/subcontracts/{sub_id}", headers=auth)
    assert r.status_code == 200
    assert r.json()["subcontractor_name"] == "Steel Bros"

    # Add clause
    r = client.post(
        f"/api/subcontract/subcontracts/{sub_id}/clauses",
        json={
            "title": "Indemnity",
            "source_quote": "Clause 12.1",
            "present": True,
            "status": "checked",
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text

    # Add scope item
    r = client.post(
        f"/api/subcontract/subcontracts/{sub_id}/scope-items",
        json={"item_text": "Anti-termite treatment", "covered": False, "source_event_id": None},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    scope_id = r.json()["id"]

    # Add payment event
    r = client.post(
        f"/api/subcontract/subcontracts/{sub_id}/payment-events",
        json={
            "kind": "invoice",
            "due_date": "2026-08-10",
            "amount_minor": 1000000,
            "certified_amount_minor": 800000,
            "currency": "INR",
            "status": "pending",
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text

    # Scope gaps
    r = client.get(f"/api/subcontract/subcontracts/{sub_id}/scope-gaps", headers=auth)
    assert r.status_code == 200, r.text
    gaps = r.json()
    assert len(gaps["gaps"]) == 1
    assert gaps["gaps"][0]["item_text"] == "Anti-termite treatment"

    # Mark covered by adding a covered scope item
    r = client.post(
        f"/api/subcontract/subcontracts/{sub_id}/scope-items",
        json={"item_text": "Anti-termite treatment", "covered": True, "source_event_id": scope_id},
        headers=auth,
    )
    assert r.status_code == 200

    r = client.get(f"/api/subcontract/subcontracts/{sub_id}/scope-gaps", headers=auth)
    result = r.json()
    assert len(result["gaps"]) == 1
    assert len(result["covered"]) == 1

    # Notice calendar
    r = client.get(f"/api/subcontract/subcontracts/{sub_id}/notice-calendar", headers=auth)
    assert r.status_code == 200, r.text
    assert "calendar" in r.json()

    # Payment exposure
    r = client.get(f"/api/subcontract/subcontracts/{sub_id}/payment-exposure", headers=auth)
    assert r.status_code == 200, r.text
    exp = r.json()
    assert exp["total_certified_minor"] == 800000
    assert exp["pending_minor"] == 800000
