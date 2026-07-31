"""express module tests (TS-208/209/210/211/212)."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.express.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.express.prices import tier_price_minor

_GCC_SAMPLE = """
[p1]
Notice Inviting Tender
Last date of submission: 15 August 2026
Clause 5 — Scope. Build a bridge on a firm price basis and no escalation shall be payable.
"""

WEBHOOK_SECRET = "dev-razorpay-secret"


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,auth,rulepacks,ingestion,findings,risk,billing,express",
            database_url="sqlite:///:memory:",
            razorpay_webhook_secret=WEBHOOK_SECRET,
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_express_status(client):
    body = client.get("/api/express").json()
    assert body["status"] == "ready"
    assert body["max_upload_bytes"] > 0


def test_create_session_requires_acknowledgment(client):
    denied = client.post(
        "/api/express/sessions",
        json={"email": "visitor@example.com", "tier": "snapshot", "acknowledgment": {}},
    )
    assert denied.status_code == 422


def test_create_upload_and_fetch_session(client):
    created = client.post(
        "/api/express/sessions",
        json={
            "email": "visitor@example.com",
            "tier": "snapshot",
            "acknowledgment": {"accepted": True, "text_version": "express-unreviewed-v1"},
        },
    )
    assert created.status_code == 200
    token = created.json()["token"]
    assert len(token) > 20

    uploaded = client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("gcc.txt", _GCC_SAMPLE.encode(), "text/plain")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["sha256"]

    fetched = client.get(f"/api/express/sessions/{token}")
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "uploaded"


def test_teaser_renders_without_auth(client):
    token = client.post(
        "/api/express/sessions",
        json={
            "email": "teaser@example.com",
            "tier": "risk",
            "acknowledgment": {"accepted": True},
        },
    ).json()["token"]
    client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("gcc.txt", _GCC_SAMPLE.encode(), "text/plain")},
    )
    teaser = client.get(f"/api/express/sessions/{token}/teaser")
    assert teaser.status_code == 200
    body = teaser.json()
    assert body["state"] == "teaser_ready"
    assert body["teaser"]["missing_documents"]["expected"]
    assert body["teaser"]["sample_findings"] is not None
    assert len(body["teaser"]["deadlines"]) >= 1


def test_upload_rejects_oversized_payload(client):
    created = client.post(
        "/api/express/sessions",
        json={
            "email": "big@example.com",
            "tier": "snapshot",
            "acknowledgment": {"accepted": True},
        },
    ).json()
    token = created["token"]
    huge = b"x" * (26 * 1024 * 1024)
    resp = client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("big.bin", huge, "application/octet-stream")},
    )
    assert resp.status_code == 413


def _express_session(client):
    token = client.post(
        "/api/express/sessions",
        json={
            "email": "buyer@example.com",
            "tier": "snapshot",
            "acknowledgment": {"accepted": True},
        },
    ).json()["token"]
    client.post(
        f"/api/express/sessions/{token}/documents",
        files={"file": ("gcc.txt", _GCC_SAMPLE.encode(), "text/plain")},
    )
    client.get(f"/api/express/sessions/{token}/teaser")
    return token


def _signed_webhook(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def test_checkout_rejects_client_amount_mismatch(client):
    token = _express_session(client)
    bad = client.post(
        f"/api/express/sessions/{token}/checkout",
        json={"country": "IN", "amount_minor": 1},
    )
    assert bad.status_code == 400


def test_checkout_uses_server_owned_price(client):
    token = _express_session(client)
    checkout = client.post(
        f"/api/express/sessions/{token}/checkout",
        json={"country": "IN"},
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert body["amount_minor"] == tier_price_minor("snapshot", country="IN")
    assert "activation happens via the signed webhook" in body["note"]


def test_report_locked_until_webhook(client):
    token = _express_session(client)
    checkout = client.post(
        f"/api/express/sessions/{token}/checkout",
        json={"country": "IN"},
    ).json()
    order_id = checkout["checkout"]["order_id"]

    locked = client.get(f"/api/express/sessions/{token}/report")
    assert locked.status_code == 402

    body = {
        "id": "evt_express_1",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "currency": "INR",
                    "order_id": order_id,
                    "notes": {
                        "kind": "express",
                        "express_token": token,
                        "tier": "snapshot",
                        "amount_minor": checkout["amount_minor"],
                    },
                }
            }
        },
    }
    raw, sig = _signed_webhook(body)
    wh = client.post(
        "/api/billing/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": sig},
    )
    assert wh.status_code == 200
    assert wh.json()["ok"] is True

    report = client.get(f"/api/express/sessions/{token}/report")
    assert report.status_code == 200
    assert report.json()["report"]["variant"] == "unreviewed"
    assert report.json()["report"]["finding_count"] >= 0
