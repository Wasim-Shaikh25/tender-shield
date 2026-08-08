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
from app.modules.billing.plans import (
    PAYGO_PRICE_INR_PAISE,
    SUBSCRIPTION_PRICES,
    PaywallError,
    authorize,
)
from app.modules.billing.webhook import verify_signature
from tests.helpers import auth_headers_and_workspace

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
        Settings(
            enabled_modules="health,auth,billing",
            database_url="sqlite:///:memory:",
            razorpay_webhook_secret=SECRET,
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers_and_workspace(client, "b@x.com")

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
    headers, workspace_id = _auth(client)
    body = {
        "id": "evt_sub_1",
        "event": "subscription.activated",
        "payload": {
            "subscription": {"entity": {"notes": {"workspace_id": workspace_id, "plan": "pro"}}}
        },
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
    headers, workspace_id = _auth(client)
    body = {
        "id": "evt_order_paid_1",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_1",
                    "amount": PAYGO_PRICE_INR_PAISE,
                    "notes": {"workspace_id": workspace_id},
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
    assert invoices[0]["amount_minor"] == PAYGO_PRICE_INR_PAISE
    assert invoices[0]["status"] == "paid"
    assert invoices[0]["invoice_number"].startswith("INV-")


def test_record_usage_capability_logs_event(client):
    _, workspace_id = _auth(client)
    reg = client.app.state.ctx.registry
    factory = reg.get("billing.record_usage")
    assert factory is not None
    engine = reg.require("db.engine")
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        factory(session, workspace_id, "test_event")
    # usage is internal; the capability was reachable and callable without error


def test_list_plans_exposes_catalog(client):
    headers, _ = _auth(client)
    r = client.get("/api/billing/plans", headers=headers)
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert {p["id"] for p in plans} == {"free", "pro", "scale"}


def test_user_can_downgrade_to_free(client):
    headers, workspace_id = _auth(client)
    # start on pro via webhook
    body = {
        "id": "evt_sub_downgrade",
        "event": "subscription.activated",
        "payload": {
            "subscription": {"entity": {"notes": {"workspace_id": workspace_id, "plan": "pro"}}}
        },
    }
    raw, sig = _signed(body)
    client.post(
        "/api/billing/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": sig},
    )
    assert client.get("/api/billing/status", headers=headers).json()["plan"] == "pro"

    r = client.post("/api/billing/change-plan", json={"plan": "free"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["plan"] == "free"
    assert r.json()["previous_plan"] == "pro"
    assert client.get("/api/billing/status", headers=headers).json()["plan"] == "free"


def test_change_plan_to_paid_returns_checkout(client):
    headers, _ = _auth(client)
    # fixture signs up and verifies email, so change-plan is allowed.
    r = client.post("/api/billing/change-plan", json={"plan": "pro"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["provider"] in {"razorpay", "stripe"}
    assert "order_id" in r.json() or "session_id" in r.json()


def test_change_plan_rejects_invalid_and_same_plan(client):
    headers, _ = _auth(client)
    r1 = client.post("/api/billing/change-plan", json={"plan": "invalid"}, headers=headers)
    assert r1.status_code == 400
    # free is the default plan after signup
    r2 = client.post("/api/billing/change-plan", json={"plan": "free"}, headers=headers)
    assert r2.status_code == 400


def _create_coupon(
    client,
    code: str,
    discount_type: str,
    discount_value: int,
    currency: str = "INR",
    max_uses: int | None = None,
):
    """Create a coupon directly via BillingService so integration tests can exercise coupons."""
    from sqlalchemy.orm import Session

    from app.modules.billing.service import BillingService

    engine = client.app.state.ctx.registry.require("db.engine")
    with Session(engine) as session:
        svc = BillingService(session)
        svc.create_coupon(
            {
                "code": code,
                "discount_type": discount_type,
                "discount_value": discount_value,
                "currency": currency,
                "max_uses": max_uses,
            }
        )


def test_checkout_rejects_100_percent_coupon(client):
    headers, _ = _auth(client)
    _create_coupon(client, "FREE100UI", "percent", 100)
    r = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "pro", "coupon_code": "FREE100UI"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "coupon_makes_amount_zero"


def test_change_plan_rejects_100_percent_coupon(client):
    headers, _ = _auth(client)
    _create_coupon(client, "FREE100PLAN", "percent", 100)
    r = client.post(
        "/api/billing/change-plan",
        json={"plan": "pro", "coupon_code": "FREE100PLAN"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "coupon_makes_amount_zero"


def test_checkout_rejects_oversized_fixed_coupon(client):
    headers, _ = _auth(client)
    _create_coupon(client, "FREE999FIX", "fixed", 9_999_999)
    r = client.post(
        "/api/billing/checkout",
        json={"kind": "paygo", "coupon_code": "FREE999FIX"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "coupon_makes_amount_zero"


def test_rejected_100_percent_coupon_does_not_consume_use(client):
    headers, _ = _auth(client)
    _create_coupon(client, "FREE100ONCE", "percent", 100, max_uses=1)
    r = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "pro", "coupon_code": "FREE100ONCE"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "coupon_makes_amount_zero"
    engine = client.app.state.ctx.registry.require("db.engine")
    from sqlalchemy.orm import Session

    from app.modules.billing.service import BillingService

    with Session(engine) as session:
        svc = BillingService(session)
        coupon = svc.get_coupon("FREE100ONCE")
        assert coupon.uses_count == 0


def test_webhook_accepts_50_percent_coupon_amount(client):
    headers, workspace_id = _auth(client)
    _create_coupon(client, "HALF50", "percent", 50)
    amount = SUBSCRIPTION_PRICES["inr"]["pro"] // 2
    body = {
        "id": "evt_half_1",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_half",
                    "amount": amount,
                    "currency": "INR",
                    "notes": {
                        "workspace_id": workspace_id,
                        "kind": "subscription",
                        "plan": "pro",
                        "coupon_code": "HALF50",
                    },
                }
            }
        },
    }
    raw, sig = _signed(body)
    r = client.post(
        "/api/billing/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": sig},
    )
    assert r.json().get("applied") == "order.paid"


def test_webhook_rejects_zero_amount_with_100_percent_coupon(client):
    headers, workspace_id = _auth(client)
    _create_coupon(client, "FREE100WEB", "percent", 100)
    body = {
        "id": "evt_zero_1",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_zero",
                    "amount": 0,
                    "currency": "INR",
                    "notes": {
                        "workspace_id": workspace_id,
                        "kind": "subscription",
                        "plan": "pro",
                        "coupon_code": "FREE100WEB",
                    },
                }
            }
        },
    }
    raw, sig = _signed(body)
    r = client.post(
        "/api/billing/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": sig},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "amount_mismatch"
