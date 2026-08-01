"""Change module scaffold (TS-244)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "change@x.com")


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Site Block A"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": "[p1]\nClause 12 — Variations require 14 days notice.\n",
        },
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def _accept_all(client, headers, opp_id):
    for finding in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{finding['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )


def _freeze(client, headers, opp_id):
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender"},
        headers=headers,
    )


def test_change_module_boots_disabled():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,review,baseline",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    assert not app.state.ctx.registry.has("change.service_factory")


def test_manual_event_requires_baseline(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    blocked = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Extra excavation",
            "sources": [{"source_quote": "depth increased to 3m", "source_page": 4}],
        },
        headers=headers,
    )
    assert blocked.status_code == 404
    assert blocked.json()["detail"] == "no_baseline"


def test_manual_event_lifecycle(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    created = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Revised pile depth",
            "reason": "drawing_revision",
            "confidence_band": "high",
            "notice_type": "variation",
            "sources": [
                {
                    "source_kind": "manual",
                    "source_quote": "pile depth increased from 12m to 15m",
                    "source_page": 12,
                }
            ],
        },
        headers=headers,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "candidate"
    assert body["baseline_id"]
    assert len(body["sources"]) == 1
    event_id = body["id"]

    listed = client.get(f"/api/change/opportunities/{opp_id}/events", headers=headers)
    assert listed.status_code == 200
    assert any(e["id"] == event_id for e in listed.json()["events"])

    detail = client.get(f"/api/change/events/{event_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["latest_confirmation"] is None

    confirmed = client.post(
        f"/api/change/events/{event_id}/confirmations",
        json={"outcome": "changed", "note": "Confirmed on site walk"},
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["outcome"] == "changed"

    after = client.get(f"/api/change/events/{event_id}", headers=headers).json()
    assert after["status"] == "confirmed"
    assert after["latest_confirmation"]["outcome"] == "changed"


def test_baseline_diff_emits_candidate_with_quote(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    revised = "[p1]\nClause 12 — Variations require 28 days notice.\n"
    result = client.post(
        f"/api/change/opportunities/{opp_id}/diff",
        json={"text": revised},
        headers=headers,
    )
    assert result.status_code == 200
    body = result.json()
    assert body["created"] >= 1
    assert body["events"]
    event = body["events"][0]
    assert event["status"] == "candidate"
    assert event["sources"][0]["source_kind"] == "baseline_diff"
    assert event["sources"][0]["source_quote"]


def test_signal_ingestion_creates_candidate(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    first = client.post(
        f"/api/change/opportunities/{opp_id}/signals",
        json={
            "signal_kind": "site_instruction",
            "text": "Site instruction SI-9: proceed with the variation to widen the access road.",
            "external_ref": "SI-9",
        },
        headers=headers,
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["created"] is True
    assert payload["event"]["reason"] == "instruction"
    assert payload["event"]["sources"][0]["source_quote"]

    second = client.post(
        f"/api/change/opportunities/{opp_id}/signals",
        json={
            "signal_kind": "site_instruction",
            "text": "Site instruction SI-9: proceed with the variation to widen the access road.",
            "external_ref": "SI-9",
        },
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["created"] is False
