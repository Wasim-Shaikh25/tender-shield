"""Coupons, discounts, credits, referrals, trials, pilot comps (R-006,
TS-090). Before this, `grep -rni "coupon|discount|promo|referral|trial"`
across the product returned zero hits — there was no way to give anyone a
discount, credit a referral, or comp a pilot account.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.billing.coupons import CouponError, CouponView, discount_for, validate
from app.modules.billing.providers.base import OrderHandle
from app.modules.billing.providers.razorpay import RazorpayProvider

SECRET = "dev-razorpay-secret"
_FULL_MODULES = "health,auth,billing"


def _coupon(**overrides) -> CouponView:
    defaults = dict(
        code="PILOT25",
        kind="percent",
        value=25,
        currency=None,
        applies_to={},
        max_redemptions=None,
        max_per_workspace=1,
        redeemed_count=0,
        valid_from=None,
        valid_until=None,
        active=True,
    )
    defaults.update(overrides)
    return CouponView(**defaults)


# ---- pure -------------------------------------------------------------


def test_discount_for_percent_no_float():
    assert discount_for(_coupon(kind="percent", value=25), 2_499_900) == 624_975


def test_discount_for_percent_never_exceeds_list_price():
    assert discount_for(_coupon(kind="percent", value=100), 1_000) == 1_000


def test_discount_for_fixed_capped_at_list_price():
    assert discount_for(_coupon(kind="fixed", value=999_999, currency="INR"), 500) == 500


def test_discount_for_free_reviews_is_zero_price_reduction():
    assert discount_for(_coupon(kind="free_reviews", value=3), 2_499_900) == 0


def test_validate_rejects_fixed_currency_mismatch():
    with pytest.raises(CouponError) as e:
        validate(
            _coupon(kind="fixed", value=500, currency="INR"),
            plan="pro",
            kind="subscription",
            currency="GBP",
            now=datetime.now(UTC),
            workspace_redemptions=0,
            is_first_purchase=True,
        )
    assert e.value.code == "coupon_currency_mismatch"


def test_validate_rejects_at_max_redemptions():
    with pytest.raises(CouponError) as e:
        validate(
            _coupon(max_redemptions=5, redeemed_count=5),
            plan="pro",
            kind="subscription",
            currency="INR",
            now=datetime.now(UTC),
            workspace_redemptions=0,
            is_first_purchase=True,
        )
    assert e.value.code == "coupon_exhausted"


def test_validate_rejects_at_max_per_workspace():
    with pytest.raises(CouponError) as e:
        validate(
            _coupon(max_per_workspace=1),
            plan="pro",
            kind="subscription",
            currency="INR",
            now=datetime.now(UTC),
            workspace_redemptions=1,
            is_first_purchase=True,
        )
    assert e.value.code == "coupon_already_used"


def test_validate_rejects_wrong_plan():
    with pytest.raises(CouponError) as e:
        validate(
            _coupon(applies_to={"plans": ["scale"]}),
            plan="pro",
            kind="subscription",
            currency="INR",
            now=datetime.now(UTC),
            workspace_redemptions=0,
            is_first_purchase=True,
        )
    assert e.value.code == "coupon_not_applicable"


def test_validate_rejects_expired():
    with pytest.raises(CouponError) as e:
        validate(
            _coupon(valid_until=datetime.now(UTC) - timedelta(days=1)),
            plan="pro",
            kind="subscription",
            currency="INR",
            now=datetime.now(UTC),
            workspace_redemptions=0,
            is_first_purchase=True,
        )
    assert e.value.code == "coupon_expired"


def test_validate_case_insensitive_code_is_a_service_concern():
    # CouponView.code is whatever the caller passes; the .upper() lookup
    # happens in BillingService, not here (kept out of this pure module so
    # validate() doesn't need to know about storage/lookup at all).
    assert _coupon(code="pilot25").code == "pilot25"


# ---- integration --------------------------------------------------------


@pytest.fixture
def client(monkeypatch) -> TestClient:
    def fake_create_order(self, req):
        return OrderHandle(
            provider="razorpay",
            order_id=f"order_{req.idempotency_key[:16]}",
            amount_minor=req.amount_minor,
            currency=req.currency,
            checkout_payload={"key": self._key_id, "amount": req.amount_minor},
        )

    monkeypatch.setattr(RazorpayProvider, "create_order", fake_create_order)
    app = create_app(
        Settings(
            enabled_modules=_FULL_MODULES,
            database_url="sqlite:///:memory:",
            razorpay_key_id="rzp_test_fake",
            razorpay_key_secret="fake_secret",
            razorpay_webhook_secret=SECRET,
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client, email, referral_code=None):
    body = {"email": email, "password": "hunter2hunter2", "workspace_name": "Acme"}
    if referral_code:
        body["referral_code"] = referral_code
    client.post("/api/auth/signup", json=body)
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["workspace_id"]


def _superadmin(client, email="root@x.com"):
    headers, workspace_id = _auth(client, email)
    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.auth.models import User

    with factory() as s:
        user = s.scalar(select(User).where(User.email == email))
        user.is_superadmin = True
        s.commit()
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, workspace_id


def _sign(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _pay(client, headers, *, kind="subscription", plan="pro", coupon_code=None, event_id="evt_1"):
    body = {"kind": kind, "plan": plan}
    if coupon_code:
        body["coupon_code"] = coupon_code
    checkout = client.post("/api/billing/checkout", json=body, headers=headers)
    assert checkout.status_code == 200, checkout.text
    intent = checkout.json()
    event_body = {
        "id": event_id,
        "event": "subscription.activated" if kind == "subscription" else "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "amount": intent["amount_minor"],
                    "notes": {"intent_id": intent["intent_id"]},
                }
            }
        },
    }
    raw, sig = _sign(event_body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text
    return intent


def test_admin_create_coupon_requires_superadmin(client):
    headers, _ = _auth(client, "notsuperadmin@x.com")
    r = client.post(
        "/api/billing/admin/coupons",
        json={"code": "PILOT25", "kind": "percent", "value": 25},
        headers=headers,
    )
    assert r.status_code == 403


def test_coupon_reduces_checkout_amount_and_gst(client):
    admin_headers, _ = _superadmin(client)
    admin_headers2 = admin_headers  # same superadmin account acts as admin of its own workspace too
    r = client.post(
        "/api/billing/admin/coupons",
        json={"code": "PILOT25", "kind": "percent", "value": 25},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    headers, _ = _auth(client, "customer@x.com")
    quote = client.post(
        "/api/billing/coupons/validate",
        json={"code": "pilot25", "plan": "pro", "kind": "subscription"},
        headers=headers,
    ).json()
    assert quote["valid"] is True
    assert quote["discount_minor"] == 624_975  # 25% of 2_499_900
    assert quote["total_minor"] == 2_499_900 - 624_975

    checkout = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "pro", "coupon_code": "pilot25"},
        headers=headers,
    ).json()
    assert checkout["amount_minor"] == 2_499_900 - 624_975
    assert checkout["breakdown"]["discount"] == 624_975
    del admin_headers2  # unused, kept for readability of the fixture name above


def test_coupon_validate_writes_no_redemption(client):
    admin_headers, _ = _superadmin(client)
    client.post(
        "/api/billing/admin/coupons",
        json={"code": "PILOT25", "kind": "percent", "value": 25},
        headers=admin_headers,
    )
    headers, workspace_id = _auth(client, "quoteonly@x.com")
    client.post(
        "/api/billing/coupons/validate",
        json={"code": "PILOT25", "plan": "pro", "kind": "subscription"},
        headers=headers,
    )

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.billing.models import CouponRedemption

    with factory() as s:
        rows = s.scalars(select(CouponRedemption)).all()
        assert len(rows) == 0


def test_coupon_redeemed_exactly_once_even_with_duplicate_webhook(client):
    """Two DIFFERENT event ids for the SAME intent — the outer WebhookEvent
    dedup (keyed on event_id) can't catch this; it's CouponRedemption's own
    unique constraint on payment_intent_id that must (R-006 §A5). This is
    exactly what Razorpay's own retry/multi-event behavior can produce."""
    admin_headers, _ = _superadmin(client)
    client.post(
        "/api/billing/admin/coupons",
        json={"code": "PILOT25", "kind": "percent", "value": 25},
        headers=admin_headers,
    )
    headers, workspace_id = _auth(client, "redeemtwice@x.com")
    checkout = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "pro", "coupon_code": "PILOT25"},
        headers=headers,
    ).json()

    def _send(event_id):
        body = {
            "id": event_id,
            "event": "subscription.activated",
            "payload": {
                "payment": {
                    "entity": {
                        "amount": checkout["amount_minor"],
                        "notes": {"intent_id": checkout["intent_id"]},
                    }
                }
            },
        }
        raw, sig = _sign(body)
        return client.post(
            "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
        )

    assert _send("evt_dup_1").status_code == 200
    assert _send("evt_dup_2").status_code == 200  # different event id -> not caught by WebhookEvent

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.billing.models import Coupon, CouponRedemption

    with factory() as s:
        redemptions = s.scalars(select(CouponRedemption)).all()
        assert len(redemptions) == 1
        coupon = s.scalar(select(Coupon).where(Coupon.code == "PILOT25"))
        assert coupon.redeemed_count == 1


def test_coupon_max_per_workspace_blocks_a_second_checkout(client):
    admin_headers, _ = _superadmin(client)
    client.post(
        "/api/billing/admin/coupons",
        json={"code": "ONCEEACH", "kind": "percent", "value": 10, "max_per_workspace": 1},
        headers=admin_headers,
    )
    headers, workspace_id = _auth(client, "onceeach@x.com")
    _pay(client, headers, coupon_code="ONCEEACH", event_id="evt_once_1")

    r = client.post(
        "/api/billing/checkout",
        json={"kind": "subscription", "plan": "scale", "coupon_code": "ONCEEACH"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "coupon_already_used"


def test_credit_reduces_checkout_amount_and_is_consumed_on_payment(client):
    admin_headers, _ = _superadmin(client)
    headers, workspace_id = _auth(client, "creditcustomer@x.com")
    grant = client.post(
        "/api/billing/admin/credits",
        json={"workspace_id": workspace_id, "amount_minor": 100_000, "reason": "goodwill"},
        headers=admin_headers,
    )
    assert grant.status_code == 200, grant.text

    before = client.get("/api/billing/credits", headers=headers).json()
    assert before["balance_minor"] == 100_000

    checkout = client.post(
        "/api/billing/checkout", json={"kind": "subscription", "plan": "pro"}, headers=headers
    ).json()
    assert checkout["breakdown"]["credit_applied"] == 100_000
    assert checkout["amount_minor"] == 2_499_900 - 100_000

    _pay_from_checkout(client, checkout)

    after = client.get("/api/billing/credits", headers=headers).json()
    assert after["balance_minor"] == 0  # consumed on payment success


def _pay_from_checkout(client, checkout, event_id="evt_credit"):
    body = {
        "id": event_id,
        "event": "subscription.activated",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "notes": {"intent_id": checkout["intent_id"]},
                }
            }
        },
    }
    raw, sig = _sign(body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text


def test_referral_signup_and_reward_on_first_paid_purchase(client):
    referrer_headers, referrer_ws = _auth(client, "referrer@company-a.com")
    code = client.get("/api/billing/referral", headers=referrer_headers).json()["code"]

    referred_headers, referred_ws = _auth(client, "referred@company-b.com", referral_code=code)

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.billing.models import Referral

    with factory() as s:
        referral = s.scalar(select(Referral))
        assert referral is not None
        assert referral.status == "signed_up"

    _pay(client, referred_headers, event_id="evt_referral_reward")

    referrer_credits = client.get("/api/billing/credits", headers=referrer_headers).json()
    referred_credits = client.get("/api/billing/credits", headers=referred_headers).json()
    assert referrer_credits["balance_minor"] == 250_000
    assert referred_credits["balance_minor"] == 250_000

    with factory() as s:
        referral = s.scalar(select(Referral))
        assert referral.status == "rewarded"

    # A second purchase must not reward again.
    _pay(client, referred_headers, plan="scale", event_id="evt_referral_second")
    referrer_credits_after = client.get("/api/billing/credits", headers=referrer_headers).json()
    assert referrer_credits_after["balance_minor"] == 250_000


def test_self_referral_same_domain_is_blocked(client):
    referrer_headers, _ = _auth(client, "owner@samecorp.com")
    code = client.get("/api/billing/referral", headers=referrer_headers).json()["code"]
    _auth(client, "owner2@samecorp.com", referral_code=code)

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.billing.models import Referral

    with factory() as s:
        assert s.scalar(select(Referral)) is None


def test_referral_code_is_stable_across_calls(client):
    headers, _ = _auth(client, "stablecode@x.com")
    first = client.get("/api/billing/referral", headers=headers).json()["code"]
    second = client.get("/api/billing/referral", headers=headers).json()["code"]
    assert first == second


def test_trial_grants_pro_entitlements_and_is_one_time(client):
    headers, workspace_id = _auth(client, "trialuser@x.com")
    r = client.post("/api/billing/trial/start", json={"days": 14}, headers=headers)
    assert r.status_code == 200, r.text

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "pro"
    assert status["plan_status"] == "trialing"
    assert status["reviews_included"] == 10

    r2 = client.post("/api/billing/trial/start", json={"days": 14}, headers=headers)
    assert r2.status_code == 400
    assert r2.json()["detail"] == "trial_already_used"


def test_expired_trial_reverts_to_free_entitlements(client):
    headers, workspace_id = _auth(client, "expiredtrial@x.com")
    client.post("/api/billing/trial/start", json={"days": 14}, headers=headers)

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.auth.models import Workspace

    with factory() as s:
        ws = s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
        ws.trial_ends_at = datetime.now(UTC) - timedelta(days=1)
        s.commit()

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "free"
    assert status["plan_status"] == "active"


def test_comp_workspace_grants_paid_plan_and_expires_lazily(client):
    admin_headers, _ = _superadmin(client)
    headers, workspace_id = _auth(client, "compcustomer@x.com")

    r = client.post(
        "/api/billing/admin/comp",
        json={
            "workspace_id": workspace_id,
            "plan": "scale",
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "scale"
    assert status["reviews_included"] == 40

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from sqlalchemy import select

    from app.modules.auth.models import Workspace

    with factory() as s:
        ws = s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
        ws.comp_expires_at = datetime.now(UTC) - timedelta(days=1)
        s.commit()

    status_after = client.get("/api/billing/status", headers=headers).json()
    assert status_after["plan"] == "free"
