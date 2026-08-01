"""Integration tests for email inbox ingestion (TS-247)."""

import hashlib
import hmac
import json

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

WEBHOOK_SECRET = "change-inbox-test-secret"
MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change"


@pytest.fixture
def client():
    application = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            change_email_webhook_secret=WEBHOOK_SECRET,
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "email-inbox@x.com")


def _freeze_project(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Email site"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 12 — Works.\n"},
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
    return opp_id


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_register_inbox_requires_baseline(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "No baseline"}, headers=headers
    ).json()["id"]
    blocked = client.post(
        f"/api/change/opportunities/{opp_id}/inbox/email", headers=headers
    )
    assert blocked.status_code == 404
    assert blocked.json()["detail"] == "no_baseline"


def test_inbound_email_webhook_creates_candidate(client):
    headers = _auth(client)
    opp_id = _freeze_project(client, headers)

    registered = client.post(
        f"/api/change/opportunities/{opp_id}/inbox/email", headers=headers
    )
    assert registered.status_code == 200, registered.text
    token = registered.json()["address_token"]

    payload = {
        "address_token": token,
        "message_id": "<msg-001@mail.example>",
        "from": "engineer@employer.com",
        "subject": "Variation to pile depth",
        "body_plain": "Please proceed with the variation to widen the access road.",
    }
    raw = json.dumps(payload).encode()
    first = client.post(
        "/api/change/webhooks/inbound-email",
        content=raw,
        headers={"X-Change-Inbox-Signature": _sign(raw)},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["duplicate"] is False
    assert body["ingest"]["created"] is True
    assert body["ingest"]["event"]["sources"][0]["source_kind"] == "email"

    second = client.post(
        "/api/change/webhooks/inbound-email",
        content=raw,
        headers={"X-Change-Inbox-Signature": _sign(raw)},
    )
    assert second.status_code == 200
    assert second.json()["duplicate"] is True


def test_inbound_email_rejects_bad_signature(client):
    headers = _auth(client)
    opp_id = _freeze_project(client, headers)
    token = client.post(
        f"/api/change/opportunities/{opp_id}/inbox/email", headers=headers
    ).json()["address_token"]
    raw = json.dumps(
        {
            "address_token": token,
            "message_id": "<msg-002@mail.example>",
            "body_plain": "Variation instruction received.",
        }
    ).encode()
    rejected = client.post(
        "/api/change/webhooks/inbound-email",
        content=raw,
        headers={"X-Change-Inbox-Signature": "invalid"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "bad_signature"
