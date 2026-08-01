"""Integration tests for notice engine (TS-251–TS-253)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,drafting"
)


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "notice@x.com")


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Site Block A"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\nClause 12 — Variations require 14 days notice from the event.\n"
            ),
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


def _confirmed_event(client, headers, opp_id):
    created = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Revised pile depth",
            "reason": "drawing_revision",
            "notice_type": "variation",
            "trigger_date": "2026-08-01",
            "sources": [
                {
                    "source_quote": "pile depth increased from 12m to 15m",
                    "source_page": 12,
                }
            ],
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    event_id = created.json()["id"]
    client.post(
        f"/api/change/events/{event_id}/confirmations",
        json={"outcome": "changed"},
        headers=headers,
    ).raise_for_status()
    return event_id


def test_notice_deadline_requires_confirmation(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    event_id = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Pending change",
            "sources": [{"source_quote": "extra steel required", "source_page": 2}],
        },
        headers=headers,
    ).json()["id"]

    blocked = client.get(f"/api/change/events/{event_id}/notice-deadline", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "notice_deadline_requires_confirmation"


def test_notice_deadline_computed_for_confirmed_event(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)
    event_id = _confirmed_event(client, headers, opp_id)

    deadline = client.get(f"/api/change/events/{event_id}/notice-deadline", headers=headers)
    assert deadline.status_code == 200, deadline.text
    body = deadline.json()
    assert body.get("deadline_unknown") is False
    assert body["notice_deadline"] == "2026-08-15"
    assert body["trigger_date"] == "2026-08-01"
    assert body["required_content"]

    detail = client.get(f"/api/change/events/{event_id}", headers=headers).json()
    assert detail["notice_deadline"] == "2026-08-15"
    assert detail["notice_deadline_detail"]["notice_deadline"] == "2026-08-15"


def test_notice_draft_requires_confirmation(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)

    event_id = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Unconfirmed",
            "sources": [{"source_quote": "scope may change", "source_page": 1}],
        },
        headers=headers,
    ).json()["id"]

    blocked = client.post(f"/api/change/events/{event_id}/notice-draft", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "notice_draft_requires_confirmation"


def test_notice_draft_creates_validated_artifact(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id)
    _freeze(client, headers, opp_id)
    event_id = _confirmed_event(client, headers, opp_id)

    draft = client.post(f"/api/change/events/{event_id}/notice-draft", headers=headers)
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["kind"] == "variation_notice"
    assert body["status"] == "draft"

    artifact = client.get(f"/api/drafting/artifacts/{body['artifact_id']}", headers=headers)
    assert artifact.status_code == 200
    assert artifact.json()["body"]["kind"] == "variation_notice"
    assert artifact.json()["body"]["items"][0]["quote"]
