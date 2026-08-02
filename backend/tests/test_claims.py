"""Claims module integration tests (TS-258–TS-270)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.claims.models  # noqa: F401
import app.modules.evidence.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.outcomes.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,evidence,claims,outcomes"
)


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "claims@x.com")


def _setup_project(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Claims site"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": "[p1]\nClause 12 — Variations require 28 days notice.\n",
        },
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    for finding in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{finding['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender"},
        headers=headers,
    ).raise_for_status()
    event = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Revised pile depth",
            "reason": "drawing_revision",
            "sources": [
                {"source_quote": "extra pile depth required", "source_page": 4}
            ],
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/change/events/{event['id']}/confirmations",
        json={"outcome": "changed"},
        headers=headers,
    ).raise_for_status()
    return opp_id, event["id"], event["baseline_id"]


def test_create_claim_requires_type_and_title(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    created = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={"claim_type": "variation", "title": "Extra depth"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["claim_type"] == "variation"
    assert body["status"] == "draft"
    assert body["change_event_id"] is None
    assert body["baseline_id"] is None

    linked = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Linked extra depth",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["change_event_id"] == event_id
    assert linked.json()["baseline_id"] == baseline_id


def test_quantum_is_deterministic(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Quantum test",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    line = client.post(
        f"/api/claims/claims/{claim['id']}/quantum/line-items",
        json={
            "description": "Additional RCC pile",
            "quantity": "3.50",
            "unit": "m3",
            "rate_minor": 50000,
            "daywork_days": 2,
            "daywork_rate_minor": 10000,
        },
        headers=headers,
    )
    assert line.status_code == 200, line.text
    payload = client.get(
        f"/api/claims/claims/{claim['id']}/quantum", headers=headers
    ).json()
    assert payload["measured_total_minor"] == 175000
    assert payload["daywork_total_minor"] == 20000
    assert payload["total_minor"] == 195000
    assert payload["line_items"][0]["total_minor"] == 195000


def test_delay_register_records_facts_not_entitlement(client):
    headers = _auth(client)
    opp_id, _, _ = _setup_project(client, headers)
    added = client.post(
        f"/api/claims/opportunities/{opp_id}/delay-register",
        json={
            "event_date": "2026-01-15",
            "description": "Rain stoppage",
            "delay_days": 3,
            "programme_activity": "earthwork",
            "source_quote": "rain stopped work",
            "source_page": 2,
        },
        headers=headers,
    )
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["delay_days"] == 3
    assert body["programme_activity"] == "earthwork"
    assert "entitlement" not in body

    listed = client.get(
        f"/api/claims/opportunities/{opp_id}/delay-register", headers=headers
    )
    assert listed.status_code == 200
    assert len(listed.json()["events"]) == 1


def test_chain_integrity_and_submission(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    orphan = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={"claim_type": "variation", "title": "Orphan claim"},
        headers=headers,
    ).json()
    integrity = client.get(
        f"/api/claims/claims/{orphan['id']}/chain-integrity", headers=headers
    ).json()
    assert integrity["status"] == "chain_broken"
    assert integrity["missing_link"] == "change_event"

    submit = client.post(
        f"/api/claims/claims/{orphan['id']}/submit", headers=headers
    )
    assert submit.status_code == 409
    assert submit.json()["detail"]["code"] == "chain_broken"

    linked = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Linked claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()
    integrity = client.get(
        f"/api/claims/claims/{linked['id']}/chain-integrity", headers=headers
    ).json()
    assert integrity["status"] == "intact"

    submit = client.post(
        f"/api/claims/claims/{linked['id']}/submit", headers=headers
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "submitted"


def test_checklist_present_flags_after_evidence(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Checklist claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    checklist = {
        i["item_type"]: i
        for i in client.get(
            f"/api/claims/claims/{claim['id']}/checklist", headers=headers
        ).json()["items"]
    }
    assert all(i["required"] for i in checklist.values())
    assert checklist["baseline"]["present"]
    assert not checklist["instruction"]["present"]
    assert not checklist["photos"]["present"]
    assert not checklist["labour"]["present"]
    assert not checklist["plant"]["present"]
    assert not checklist["material"]["present"]

    # Attach evidence to the linked change event.
    for record_type in ["site_instruction", "photograph", "drawing_revision"]:
        client.post(
            f"/api/change/events/{event_id}/evidence",
            json={"record_type": record_type, "title": record_type},
            headers=headers,
        ).raise_for_status()

    # Add a measured-work line item to satisfy quantum.
    client.post(
        f"/api/claims/claims/{claim['id']}/quantum/line-items",
        json={
            "description": "Extra concrete",
            "quantity": "1",
            "unit": "m3",
            "rate_minor": 10000,
        },
        headers=headers,
    ).raise_for_status()

    # Add a delay event to satisfy delay/schedule.
    client.post(
        f"/api/claims/opportunities/{opp_id}/delay-register",
        json={
            "event_date": "2026-01-15",
            "description": "Rain",
            "delay_days": 1,
            "claim_id": claim["id"],
        },
        headers=headers,
    ).raise_for_status()

    # Add a minutes/approval record.
    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "meeting_minutes", "title": "Approval minutes"},
        headers=headers,
    ).raise_for_status()

    checklist = {
        i["item_type"]: i
        for i in client.get(
            f"/api/claims/claims/{claim['id']}/checklist", headers=headers
        ).json()["items"]
    }
    assert checklist["instruction"]["present"]
    assert checklist["baseline"]["present"]
    assert checklist["revised_scope"]["present"]
    assert checklist["photos"]["present"]
    assert checklist["quantum"]["present"]
    assert checklist["delay"]["present"]
    assert checklist["schedule"]["present"]
    assert checklist["correspondence"]["present"]
    assert checklist["approvals"]["present"]
    # labour/plant/material have no matching evidence record type yet (TS-270).
    assert not checklist["labour"]["present"]
    assert not checklist["plant"]["present"]
    assert not checklist["material"]["present"]


def test_chronology_is_cited_and_sorted(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Chronology claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "photograph", "title": "Site photo"},
        headers=headers,
    ).raise_for_status()

    entries = client.get(
        f"/api/claims/claims/{claim['id']}/chronology", headers=headers
    ).json()["entries"]
    assert len(entries) >= 2
    kinds = {e["entry_type"] for e in entries}
    assert "event" in kinds
    assert "evidence" in kinds
    # Every entry should expose source ids and custody chain for evidence.
    for e in entries:
        assert "source_id" in e
        assert "source_quote" in e
        assert "document_id" in e


def test_draft_generation_and_approval(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Draft claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    draft = client.post(
        f"/api/claims/claims/{claim['id']}/drafts/full_pack",
        headers=headers,
    )
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["draft_kind"] == "full_pack"
    assert body["status"] == "draft"
    assert "chronology" in body["body"]
    assert "quantum" in body["body"]
    assert "checklist" in body["body"]

    approved = client.post(
        f"/api/claims/drafts/{body['id']}/approve", headers=headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_negotiation_settlement_timeline(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Settlement claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    client.post(
        f"/api/claims/claims/{claim['id']}/submit", headers=headers
    ).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/responses",
        json={
            "response_kind": "counter_proposal",
            "received_at": "2026-02-01",
            "responder": "employer engineer",
            "due_at": "2026-02-15",
        },
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/negotiations",
        json={"offered_amount_minor": 150000, "counter_amount_minor": 120000},
        headers=headers,
    ).raise_for_status()
    settlement = client.post(
        f"/api/claims/claims/{claim['id']}/settlement",
        json={"outcome": "negotiated", "settled_amount_minor": 125000},
        headers=headers,
    )
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()["outcome"] == "negotiated"

    claim_detail = client.get(
        f"/api/claims/claims/{claim['id']}", headers=headers
    ).json()
    assert claim_detail["status"] == "settled"
    assert claim_detail["recovered_amount_minor"] == 125000

    timeline = client.get(
        f"/api/claims/claims/{claim['id']}/timeline", headers=headers
    ).json()
    assert len(timeline["responses"]) == 1
    assert len(timeline["negotiations"]) == 1
    assert timeline["settlement"]["outcome"] == "negotiated"


def test_conflict_detection_flags_opposing_parties(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    contractor = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Contractor claim",
            "claimant_party": "contractor",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()
    employer = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Employer counter-claim",
            "claimant_party": "employer",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()
    check = client.get(
        f"/api/claims/claims/{contractor['id']}/conflicts", headers=headers
    ).json()
    assert check["conflict_detected"] is True
    assert any(c["claim_id"] == employer["id"] for c in check["opposing_claims"])


def test_cycle_metrics_and_notice_timeliness(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    # Compute notice deadline so we can verify timeliness math.
    client.get(
        f"/api/change/events/{event_id}/notice-deadline", headers=headers
    ).raise_for_status()

    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Metric claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{claim['id']}/responses",
        json={
            "response_kind": "counter_proposal",
            "received_at": "2026-02-01",
            "responder": "employer",
            "due_at": "2026-02-15",
        },
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/submit", headers=headers
    ).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/settlement",
        json={"outcome": "negotiated", "settled_amount_minor": 90000},
        headers=headers,
    ).raise_for_status()

    metrics = client.get(
        f"/api/claims/opportunities/{opp_id}/claim-metrics", headers=headers
    ).json()
    assert "status_counts" in metrics
    assert metrics["status_counts"].get("settled") == 1
    assert metrics["averages"]["draft_to_submit_days"] >= 0
    assert "notice_timeliness" in metrics
    assert metrics["recovered_total_minor"] == 90000


def test_margin_protected_includes_recovered_claim_value(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "North star claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()
    client.post(f"/api/claims/claims/{claim['id']}/submit", headers=headers).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/settlement",
        json={"outcome": "approved", "settled_amount_minor": 75000},
        headers=headers,
    ).raise_for_status()

    margin = client.get(
        "/api/outcomes/metrics/margin-protected", headers=headers
    ).json()
    assert margin["claim_recoveries_minor"] == 75000
    assert margin["total_margin_protected_minor"] >= 75000


def test_site_evidence_record_types_satisfy_checklist(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)
    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Site evidence claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
        },
        headers=headers,
    ).json()

    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={
            "record_type": "geotagged_photo",
            "title": "Site photo with GPS",
            "metadata": {"geolocation": {"lat": 12.97, "lng": 77.59}},
        },
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "labour", "title": "Labour record"},
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "plant", "title": "Plant record"},
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "material", "title": "Material record"},
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "daywork", "title": "Daywork record"},
        headers=headers,
    ).raise_for_status()

    checklist = {
        i["item_type"]: i
        for i in client.get(
            f"/api/claims/claims/{claim['id']}/checklist", headers=headers
        ).json()["items"]
    }
    assert checklist["photos"]["present"]
    assert checklist["labour"]["present"]
    assert checklist["plant"]["present"]
    assert checklist["material"]["present"]
    assert checklist["quantum"]["present"]
