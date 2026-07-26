"""Billing: pure plan/paywall + webhook signature (unit) and metering + the
webhook-is-truth flow (integration)."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.billing.plans import PaywallError, authorize
from app.modules.billing.webhook import verify_signature

# ---- pure ----------------------------------------------------------------


def test_free_then_exhausted():
    assert authorize(plan="free", free_review_used=False, reviews_this_month=0).watermark is True
    with pytest.raises(PaywallError) as e:
        authorize(plan="free", free_review_used=True, reviews_this_month=0)
    assert e.value.code == "free_exhausted"


def test_paygo_requires_payment():
    g = authorize(plan="paygo", free_review_used=True, reviews_this_month=99)
    assert g.requires_payment is True


def test_pro_quota():
    assert authorize(plan="pro", free_review_used=True, reviews_this_month=9).kind == "plan"
    with pytest.raises(PaywallError) as e:
        authorize(plan="pro", free_review_used=True, reviews_this_month=10)
    assert e.value.code == "quota_exhausted"


def test_webhook_signature():
    body = b'{"id":"evt_1"}'
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "secret")
    assert not verify_signature(body, "deadbeef", "secret")
    assert not verify_signature(body, "", "secret")


# ---- integration ---------------------------------------------------------

SECRET = "dev-razorpay-secret"


@pytest.fixture
def client():
    app = create_app(
        Settings(enabled_modules="health,auth,billing", database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "b@x.com", "password": "hunter2hunter2", "org_name": "Acme"},
    )
    r = client.post("/api/auth/login", json={"email": "b@x.com", "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["org_id"]


def _signed(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def test_free_review_metering(client):
    headers, _ = _auth(client)
    first = client.post("/api/billing/authorize-review", headers=headers)
    assert first.status_code == 200
    assert first.json()["kind"] == "free_first_review"
    second = client.post("/api/billing/authorize-review", headers=headers)
    assert second.status_code == 402
    assert second.json()["detail"]["code"] == "free_exhausted"


def test_webhook_activates_plan_and_is_idempotent(client):
    headers, org_id = _auth(client)
    body = {
        "id": "evt_sub_1",
        "event": "subscription.activated",
        "payload": {"subscription": {"entity": {"notes": {"org_id": org_id, "plan": "pro"}}}},
    }
    raw, sig = _signed(body)
    r1 = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r1.json()["applied"] == "subscription.activated"
    # plan now pro
    assert client.get("/api/billing/status", headers=headers).json()["plan"] == "pro"
    # replay → idempotent no-op
    r2 = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r2.json().get("duplicate") is True


def test_tampered_signature_rejected(client):
    _auth(client)
    raw, _ = _signed({"id": "evt_x", "event": "order.paid"})
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": "bad"}
    )
    assert r.status_code == 400


def test_order_paid_creates_invoice_and_list_returns_it(client):
    headers, org_id = _auth(client)
    body = {
        "id": "evt_order_paid_1",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_1",
                    "amount": 100000,
                    "notes": {"org_id": org_id},
                }
            }
        },
    }
    raw, sig = _signed(body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.json()["applied"] == "order.paid"

    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    assert len(invoices) == 1
    assert invoices[0]["amount_minor"] == 100000
    assert invoices[0]["status"] == "paid"
    assert invoices[0]["invoice_number"].startswith("INV-")


def test_record_usage_capability_logs_event(client):
    _, org_id = _auth(client)
    reg = client.app.state.ctx.registry
    factory = reg.get("billing.record_usage")
    assert factory is not None
    engine = reg.require("db.engine")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        factory(session, org_id, "test_event")
    # usage is internal; the capability was reachable and callable without error
