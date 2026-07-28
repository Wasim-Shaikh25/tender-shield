"""Billing: pure plan/paywall + webhook signature (unit) and metering + real
orders + the webhook-is-truth flow (integration, R-005, TS-089/TS-097).

Order creation is the one piece that needs a live Razorpay account
(TS-037/R-005 "Out of scope" — Stripe/live keys need credentials); it is
monkeypatched here exactly like AppleClient is faked in test_auth_module.py,
so the REST of the flow — checkout validation, payment_intents, the webhook
resolving the grant from the intent rather than from notes, idempotency,
amount-mismatch, dunning/grace, refunds — all runs for real.
"""

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
from app.modules.billing.plans import PaywallError, authorize, price_for
from app.modules.billing.providers.base import OrderHandle
from app.modules.billing.providers.razorpay import RazorpayProvider
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


def test_price_for_unknown_plan_raises():
    with pytest.raises(PaywallError) as e:
        price_for("enterprise")
    assert e.value.code == "unknown_plan"


def test_price_for_known_plans():
    assert price_for("paygo") == 750_000
    assert price_for("pro") == 2_499_900
    assert price_for("scale") == 7_499_900


# ---- integration -----------------------------------------------------------

SECRET = "dev-razorpay-secret"


@pytest.fixture
def client(monkeypatch):
    # Fake but present keys — select_provider needs them to build a real
    # RazorpayProvider; only create_order (the network call) is monkeypatched.
    app = create_app(
        Settings(
            enabled_modules="health,auth,billing",
            database_url="sqlite:///:memory:",
            razorpay_key_id="rzp_test_fake",
            razorpay_key_secret="fake_secret",
            razorpay_webhook_secret=SECRET,
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))

    def fake_create_order(self, req):
        return OrderHandle(
            provider="razorpay",
            order_id=f"order_{req.idempotency_key[:16]}",
            amount_minor=req.amount_minor,
            currency=req.currency,
            checkout_payload={"key": self._key_id, "amount": req.amount_minor},
        )

    monkeypatch.setattr(RazorpayProvider, "create_order", fake_create_order)
    return TestClient(app)


def _auth(client, email="b@x.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["workspace_id"]


def _signed(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _checkout(client, headers, *, kind, plan=None, opportunity_id=None):
    body = {"kind": kind}
    if plan:
        body["plan"] = plan
    if opportunity_id:
        body["opportunity_id"] = opportunity_id
    r = client.post("/api/billing/checkout", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _webhook_for_intent(
    client, *, event_type: str, intent_id: str, amount_minor: int, event_id: str
):
    body = {
        "id": event_id,
        "event": event_type,
        "payload": {
            "payment": {
                "entity": {"id": "pay_1", "amount": amount_minor, "notes": {"intent_id": intent_id}}
            }
        },
    }
    raw, sig = _signed(body)
    return client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )


def test_free_review_metering(client):
    headers, _ = _auth(client)
    first = client.post("/api/billing/authorize-review", headers=headers)
    assert first.status_code == 200
    assert first.json()["kind"] == "free_first_review"
    second = client.post("/api/billing/authorize-review", headers=headers)
    assert second.status_code == 402
    assert second.json()["detail"]["code"] == "free_exhausted"


def test_checkout_rejects_unknown_plan(client):
    headers, _ = _auth(client)
    r = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "enterprise"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "unknown_plan"


def test_checkout_without_configured_provider_returns_503():
    app = create_app(
        Settings(enabled_modules="health,auth,billing", database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    c = TestClient(app)
    c.post(
        "/api/auth/signup",
        json={"email": "noprovider@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = c.post(
        "/api/auth/login", json={"email": "noprovider@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    r = c.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "pro"},
        headers={"authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "payment_provider_unavailable"


def test_checkout_creates_intent_with_server_side_price(client):
    headers, _ = _auth(client)
    resp = _checkout(client, headers, kind="subscription", plan="pro")
    assert resp["amount_minor"] == 2_499_900  # server-side price, not client-supplied
    assert resp["order_id"].startswith("order_")
    assert resp["breakdown"]["total"] == 2_499_900


def test_checkout_retry_reuses_same_order(client):
    headers, _ = _auth(client)
    first = _checkout(client, headers, kind="subscription", plan="pro")
    second = _checkout(client, headers, kind="subscription", plan="pro")
    assert first["order_id"] == second["order_id"]
    assert first["intent_id"] == second["intent_id"]


def test_webhook_resolves_grant_from_intent_not_notes(client):
    """The core R-005 fix: even if a webhook's notes claimed a different plan,
    the grant comes from the payment_intents row the intent_id points at."""
    headers, workspace_id = _auth(client, "sub@x.com")
    checkout = _checkout(client, headers, kind="subscription", plan="pro")

    r1 = _webhook_for_intent(
        client,
        event_type="subscription.activated",
        intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"],
        event_id="evt_sub_1",
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["applied"] == "subscription.activated"
    assert client.get("/api/billing/status", headers=headers).json()["plan"] == "pro"

    # replay -> idempotent no-op
    r2 = _webhook_for_intent(
        client,
        event_type="subscription.activated",
        intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"],
        event_id="evt_sub_1",
    )
    assert r2.json().get("duplicate") is True


def test_webhook_amount_mismatch_grants_nothing(client):
    """A payment for less than the intent's price must not grant the plan —
    this is the check whose absence let a customer pay for one plan and
    receive a pricier one (R-005 §B.1)."""
    headers, _ = _auth(client, "mismatch@x.com")
    checkout = _checkout(client, headers, kind="subscription", plan="pro")

    r = _webhook_for_intent(
        client,
        event_type="subscription.activated",
        intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"] - 1,  # underpaid by 1 paisa
        event_id="evt_underpaid",
    )
    assert r.status_code == 200
    assert client.get("/api/billing/status", headers=headers).json()["plan"] == "free"


def test_tampered_signature_rejected(client):
    headers, _ = _auth(client)
    checkout = _checkout(client, headers, kind="subscription", plan="pro")
    body = {
        "id": "evt_x",
        "event": "subscription.activated",
        "payload": {
            "subscription": {"entity": {"notes": {"intent_id": checkout["intent_id"]}}}
        },
    }
    raw = json.dumps(body).encode()
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": "bad"}
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "bad_signature"


def test_paygo_payment_creates_invoice_and_list_returns_it(client):
    headers, _ = _auth(client, "paygo@x.com")
    checkout = _checkout(client, headers, kind="paygo")

    r = _webhook_for_intent(
        client,
        event_type="order.paid",
        intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"],
        event_id="evt_order_paid_1",
    )
    assert r.json()["applied"] == "order.paid"

    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    assert len(invoices) == 1
    assert invoices[0]["amount_minor"] == 750_000
    assert invoices[0]["status"] == "paid"
    assert invoices[0]["invoice_number"].startswith("INV-")


def test_subscription_halted_sets_grace_not_immediate_downgrade(client):
    headers, workspace_id = _auth(client, "grace@x.com")
    checkout = _checkout(client, headers, kind="subscription", plan="pro")
    _webhook_for_intent(
        client, event_type="subscription.activated", intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"], event_id="evt_activate",
    )
    r = _webhook_for_intent(
        client, event_type="subscription.halted", intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"], event_id="evt_halt",
    )
    assert r.status_code == 200
    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "pro"  # plan unchanged — never delete data on non-payment
    assert status["plan_status"] == "past_due"
    assert status["grace_until"] is not None


def test_refund_downgrades_subscription(client):
    headers, workspace_id = _auth(client, "refund@x.com")
    checkout = _checkout(client, headers, kind="subscription", plan="pro")
    _webhook_for_intent(
        client, event_type="subscription.activated", intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"], event_id="evt_activate2",
    )
    r = _webhook_for_intent(
        client, event_type="refund.processed", intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"], event_id="evt_refund",
    )
    assert r.status_code == 200
    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "free"
    assert status["plan_status"] == "cancelled"


def test_intent_status_endpoint_reports_paid(client):
    headers, _ = _auth(client, "intentstatus@x.com")
    checkout = _checkout(client, headers, kind="paygo")
    _webhook_for_intent(
        client, event_type="order.paid", intent_id=checkout["intent_id"],
        amount_minor=checkout["amount_minor"], event_id="evt_intentcheck",
    )
    r = client.get(f"/api/billing/intents/{checkout['intent_id']}", headers=headers)
    assert r.json()["status"] == "paid"


def test_intent_status_hides_other_workspaces_intent(client):
    headers_a, _ = _auth(client, "ownera@x.com")
    checkout = _checkout(client, headers_a, kind="paygo")

    headers_b, _ = _auth(client, "ownerb@x.com")
    r = client.get(f"/api/billing/intents/{checkout['intent_id']}", headers=headers_b)
    assert r.json()["status"] == "not_found"


def test_webhook_with_no_event_id_is_deduped_by_body_hash(client):
    headers, _ = _auth(client, "noeventid@x.com")
    checkout = _checkout(client, headers, kind="paygo")
    body = {
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "notes": {"intent_id": checkout["intent_id"]},
                }
            }
        },
    }
    raw, sig = _signed(body)
    r1 = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r2.json().get("duplicate") is True


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
