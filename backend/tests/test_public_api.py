"""Public API tests: key management (TS-306) and signature validation (TS-339)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.public_api.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,public_api"
)


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "publicapi@x.com")


def _setup_owner(client):
    return auth_headers(client, "pub@example.com")


def _setup_owner_for_email(client, email):
    return auth_headers(client, email)


def test_create_list_revoke_api_keys(client):
    auth = _auth(client)

    r = client.post(
        "/api/public_api/keys",
        json={"name": "CI", "scopes": ["read", "write"]},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "CI"
    assert data["scopes"] == ["read", "write"]
    assert "plaintext_key" in data
    key_id = data["id"]

    r = client.get("/api/public_api/keys", headers=auth)
    assert r.status_code == 200
    keys = r.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["name"] == "CI"
    assert "plaintext_key" not in keys[0]

    r = client.delete(f"/api/public_api/keys/{key_id}", headers=auth)
    assert r.status_code == 200
    assert r.json()["revoked"] is True

    r = client.get("/api/public_api/keys", headers=auth)
    assert r.json()["keys"] == []


def test_authenticate_with_valid_api_key(client):
    auth = _auth(client)
    r = client.post(
        "/api/public_api/keys",
        json={"name": "Reader", "scopes": ["read"]},
        headers=auth,
    )
    plaintext = r.json()["plaintext_key"]

    # The public API currently only exposes /notices/{id}/request-signature as a
    # keyed endpoint. Calling it without required body fields still proves auth.
    r = client.post(
        "/api/public_api/notices/00000000-0000-0000-0000-000000000000/request-signature",
        json={},
        headers={"authorization": f"Apikey {plaintext}"},
    )
    # Missing fields produce 422, not 401, proving key auth passed.
    assert r.status_code == 422


def test_invalid_api_key_rejected(client):
    r = client.post(
        "/api/public_api/notices/00000000-0000-0000-0000-000000000000/request-signature",
        json={},
        headers={"authorization": "Apikey invalid"},
    )
    assert r.status_code == 401
def _opp_with_baseline(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Public API"}, headers=headers
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
    )
    return opp_id


def _create_event(client, opp_id, headers, *, notice_type: str | None = None):
    body = {
        "title": "Test event",
        "sources": [{"source_quote": "source text", "source_page": 1}],
    }
    if notice_type:
        body["notice_type"] = notice_type
    r = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json=body,
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _api_key(client, headers):
    r = client.post(
        "/api/public_api/keys",
        json={"name": "test", "scopes": ["read", "write"]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["plaintext_key"]


def _request_signature(client, api_key, notice_id, *, opp_id, change_event_id=None):
    payload = {"opportunity_id": opp_id, "recipient_email": "signer@example.com"}
    if change_event_id:
        payload["change_event_id"] = change_event_id
    return client.post(
        f"/api/public_api/notices/{notice_id}/request-signature",
        json=payload,
        headers={"authorization": f"ApiKey {api_key}"},
    )


def test_request_signature_valid_notice_and_event(client):
    headers = _setup_owner(client)
    opp_id = _opp_with_baseline(client, headers)
    notice_id = _create_event(client, opp_id, headers, notice_type="variation")
    event_id = _create_event(client, opp_id, headers, notice_type=None)
    api_key = _api_key(client, headers)

    r = _request_signature(client, api_key, notice_id, opp_id=opp_id, change_event_id=event_id)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "requested"


def test_request_signature_missing_ids_succeeds(client):
    headers = _setup_owner(client)
    opp_id = _opp_with_baseline(client, headers)
    notice_id = _create_event(client, opp_id, headers, notice_type="variation")
    api_key = _api_key(client, headers)

    r = _request_signature(client, api_key, notice_id, opp_id=opp_id)
    assert r.status_code == 200, r.text


def test_request_signature_invalid_notice(client):
    headers = _setup_owner(client)
    opp_id = _opp_with_baseline(client, headers)
    api_key = _api_key(client, headers)

    r = _request_signature(
        client, api_key, "00000000-0000-0000-0000-000000000000", opp_id=opp_id
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "no_such_notice"


def test_request_signature_non_notice_event(client):
    headers = _setup_owner(client)
    opp_id = _opp_with_baseline(client, headers)
    event_id = _create_event(client, opp_id, headers, notice_type=None)
    api_key = _api_key(client, headers)

    r = _request_signature(client, api_key, event_id, opp_id=opp_id)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "no_such_notice"


def test_request_signature_change_event_from_other_workspace(client):
    # Owner A creates an opportunity + event; owner B creates a separate workspace + opportunity.
    headers_a = _setup_owner(client)
    opp_a = _opp_with_baseline(client, headers_a)
    notice_id = _create_event(client, opp_a, headers_a, notice_type="variation")
    _create_event(client, opp_a, headers_a, notice_type=None)

    headers_b = _setup_owner_for_email(client, "other@example.com")
    opp_b = _opp_with_baseline(client, headers_b)
    event_b = _create_event(client, opp_b, headers_b, notice_type=None)

    api_key = _api_key(client, headers_a)

    # event_b belongs to workspace B but the request is authenticated as workspace A's key.
    r = _request_signature(
        client, api_key, notice_id, opp_id=opp_a, change_event_id=event_b
    )
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "no_such_change_event"


def _setup_owner_for_email(client, email):
    return auth_headers(client, email)
