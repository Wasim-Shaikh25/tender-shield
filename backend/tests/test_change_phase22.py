"""Change and delay analysis Phase 22 tests (TS-327–TS-328)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,integrations"


@pytest.fixture
def client():
    application = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            change_signal_polling_enabled=True,
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "change22@x.com")


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Delay OPP"}, headers=headers
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


def test_signal_polling_ingests_multiple_messages_ts327(client):
    """TS-327: poll multiple live signals and create change events."""
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    r = client.post(
        f"/api/change/opportunities/{opp_id}/signals/poll",
        json={
            "messages": [
                {
                    "signal_kind": "email",
                    "subject": "Delay notice",
                    "body": "There will be a delay due to late access to the site.",
                    "external_ref": "email-1",
                },
                {
                    "signal_kind": "site_instruction",
                    "body": "Proceed with the revised scope as per the variation order.",
                    "external_ref": "si-1",
                },
            ]
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["processed"] == 2
    assert len(body["results"]) == 2


def test_delay_analysis_uses_imported_schedule_ts328(client):
    """TS-328: delay analysis returns impacted activities from imported schedule."""
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    event = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Access delay",
            "reason": "delay",
            "trigger_date": "2026-08-01",
            "sources": [{"source_quote": "Late access to site"}],
        },
        headers=headers,
    ).json()

    csv = (
        "activity_id,name,start,finish,duration_days\n"
        "ACT01,Earthwork,2026-08-01,2026-08-05,5\n"
        "ACT02,Concrete,2026-08-06,2026-08-10,5\n"
    )
    up = client.post(
        f"/api/integrations/schedule/opportunities/{opp_id}/upload",
        files={"file": ("schedule.csv", csv.encode(), "text/csv")},
        headers=headers,
    )
    assert up.status_code == 200, up.text

    r = client.post(
        f"/api/change/opportunities/{opp_id}/delay-analysis",
        json={"event_id": event["id"], "delay_days": 5},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["impacted_count"] >= 1
    assert any(a["source_native_id"] == "ACT01" for a in body["impacted_activities"])
