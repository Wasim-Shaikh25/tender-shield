"""Plan entitlements: seats, top-ups, billing-anniversary periods (R-009,
TS-098). Before this, PLAN_LIMITS declared seats/quotas that nothing read —
a workspace could add unlimited members regardless of its plan, top-ups were
unsellable (authorize()'s has_topups parameter had no caller), and quota
reset on the calendar month rather than the billing anniversary.
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
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.billing.entitlements import add_month, resolve_entitlements
from app.modules.billing.plans import PLAN_LIMITS
from app.modules.billing.providers.base import OrderHandle
from app.modules.billing.providers.razorpay import RazorpayProvider

SECRET = "dev-razorpay-secret"

_FULL_MODULES = "health,rulepacks,auth,billing,ingestion,risk,findings,review"


# ---- pure --------------------------------------------------------------


def test_add_month_handles_month_end_rollover():
    """R-009 A9: a period starting 31 Jan ends 28 Feb (or 29 in a leap year),
    never 3 Mar."""
    assert add_month(datetime(2026, 1, 31, tzinfo=UTC)) == datetime(2026, 2, 28, tzinfo=UTC)
    assert add_month(datetime(2028, 1, 31, tzinfo=UTC)) == datetime(2028, 2, 29, tzinfo=UTC)  # leap
    assert add_month(datetime(2026, 12, 15, tzinfo=UTC)) == datetime(2027, 1, 15, tzinfo=UTC)
    assert add_month(datetime(2026, 3, 31, tzinfo=UTC)) == datetime(2026, 4, 30, tzinfo=UTC)


def test_add_month_never_skips_to_the_third_of_the_next_month():
    start = datetime(2026, 1, 31, tzinfo=UTC)
    end = add_month(start)
    assert end.month == 2
    assert end.day in (28, 29)


def test_resolve_entitlements_reviews_and_seats_remaining():
    e = resolve_entitlements(
        plan="pro",
        plan_status="active",
        seats_included=10,
        reviews_included=10,
        reviews_used=8,
        reviews_topup=1,
        seats_used=7,
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert e.reviews_remaining == 3  # 10 + 1 - 8
    assert e.seats_remaining == 3  # 10 - 7
    assert e.is_entitled is True
    assert e.watermark_exports is False


def test_resolve_entitlements_unmetered_plan_has_no_reviews_included():
    e = resolve_entitlements(
        plan="paygo",
        plan_status="active",
        seats_included=3,
        reviews_included=None,
        reviews_used=50,
        reviews_topup=0,
        seats_used=1,
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert e.reviews_remaining is None


# ---- integration ---------------------------------------------------------


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


def _auth(client, email):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["workspace_id"]


def _sign(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _set_plan(client, headers, workspace_id, plan):
    checkout = client.post(
        "/api/billing/checkout", json={"kind": "subscription", "plan": plan}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    intent = checkout.json()
    body = {
        "id": f"evt_activate_{workspace_id}_{plan}",
        "event": "subscription.activated",
        "payload": {
            "payment": {
                "entity": {
                    "amount": intent["amount_minor"],
                    "notes": {"intent_id": intent["intent_id"]},
                }
            }
        },
    }
    raw, sig = _sign(body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text


# ---- A1: seat limit enforced, pending invitations count -------------------


def test_third_member_on_free_workspace_is_blocked(client):
    """Free plan has 2 seats (PLAN_LIMITS). Owner is member #1."""
    owner_headers, workspace_id = _auth(client, "owner@x.com")
    _auth(client, "u1@x.com")
    _auth(client, "u2@x.com")

    r1 = client.post(
        f"/api/auth/workspaces/{workspace_id}/members",
        json={"email": "u1@x.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert r1.status_code == 200, r1.text  # owner + u1 = 2/2, at capacity

    r2 = client.post(
        f"/api/auth/workspaces/{workspace_id}/members",
        json={"email": "u2@x.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert r2.status_code == 402
    assert r2.json()["detail"]["code"] == "seat_limit_reached"


def test_pending_invitation_counts_toward_seat_limit(client):
    owner_headers, workspace_id = _auth(client, "owner2@x.com")
    _auth(client, "u3@x.com")

    # Owner (1/2) + a pending invitation (2/2) -> at capacity.
    inv = client.post(
        "/api/auth/invitations",
        json={"email": "invitee@x.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert inv.status_code == 200, inv.text

    r = client.post(
        f"/api/auth/workspaces/{workspace_id}/members",
        json={"email": "u3@x.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "seat_limit_reached"


def test_billing_disabled_seat_limit_is_absent():
    app = create_app(Settings(enabled_modules="health,auth", database_url="sqlite:///:memory:"))
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    c = TestClient(app)
    owner_headers, workspace_id = _auth(c, "nobilling@x.com")
    _auth(c, "u1@x.com")
    _auth(c, "u2@x.com")
    for email in ("u1@x.com", "u2@x.com"):
        r = c.post(
            f"/api/auth/workspaces/{workspace_id}/members",
            json={"email": email, "role": "viewer"},
            headers=owner_headers,
        )
        assert r.status_code == 200, r.text  # no limit — billing absent (spec core B2)


# ---- A3/A4: top-ups credit the current period and expire with it ---------


def test_pro_quota_exhausted_then_topup_allows_one_more_review(client):
    headers, workspace_id = _auth(client, "topup@x.com")
    _set_plan(client, headers, workspace_id, "pro")

    for i in range(10):
        opp = client.post(
            "/api/ingestion/opportunities", json={"title": f"Opp {i}"}, headers=headers
        ).json()["id"]
        r = client.post(f"/api/risk/opportunities/{opp}/run", headers=headers)
        assert r.status_code == 200, r.text

    opp_11 = client.post(
        "/api/ingestion/opportunities", json={"title": "Opp 11"}, headers=headers
    ).json()["id"]
    blocked = client.post(f"/api/risk/opportunities/{opp_11}/run", headers=headers)
    assert blocked.status_code == 402
    assert blocked.json()["detail"]["code"] == "quota_exhausted"

    checkout = client.post(
        "/api/billing/checkout", json={"kind": "topup"}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    intent = checkout.json()
    body = {
        "id": "evt_topup",
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "amount": intent["amount_minor"],
                    "notes": {"intent_id": intent["intent_id"]},
                }
            }
        },
    }
    raw, sig = _sign(body)
    wh = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert wh.status_code == 200, wh.text

    r = client.post(f"/api/risk/opportunities/{opp_11}/run", headers=headers)
    assert r.status_code == 200, r.text

    # workspace.plan is untouched by a top-up (it's not a plan election)
    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "pro"


def test_topup_does_not_carry_into_a_later_period(client):
    """R-009 A4: unused top-ups expire with the period they were bought in."""
    headers, workspace_id = _auth(client, "topupexpiry@x.com")
    _set_plan(client, headers, workspace_id, "pro")

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from app.modules.billing.models import UsageEvent

    now = datetime.now(UTC)
    with factory() as s:
        # A top-up granted well before the CURRENT calendar-month period
        # (the workspace has no subscription period bounds set in this
        # synthetic payload, so it falls back to calendar month).
        s.add(
            UsageEvent(
                workspace_id=uuid.UUID(workspace_id),
                event="review_topup_granted",
                ref_id=uuid.uuid4(),
                created_at=now.replace(day=1) - timedelta(days=40),
            )
        )
        s.commit()

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["reviews_topup"] == 0  # last period's top-up doesn't count now


# ---- A5: downgrade blocked when it would leave seats over the new limit --


def test_downgrade_blocked_with_too_many_members(client):
    headers, workspace_id = _auth(client, "downgrade@x.com")
    _set_plan(client, headers, workspace_id, "scale")  # 25 seats

    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    from app.core.db import bind_workspace_context
    from app.modules.auth.models import User, WorkspaceMember

    with factory() as s:
        bind_workspace_context(s, workspace_id)
        for i in range(14):  # + the owner already there = 15 total
            user = User(email=f"member{i}@x.com", password_hash="x")
            s.add(user)
            s.flush()
            s.add(
                WorkspaceMember(
                    workspace_id=uuid.UUID(workspace_id), user_id=user.id, role="viewer"
                )
            )
        s.commit()

    r = client.post(
        "/api/billing/checkout", json={"kind": "subscription", "plan": "pro"}, headers=headers
    )  # pro has 10 seats; workspace has 15 members
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "seats_exceed_new_plan"
    assert r.json()["detail"]["seats_over"] == 5


# ---- A7: past_due retains access inside grace, blocked outside it --------


def _set_past_due(client, workspace_id, *, grace_until):
    reg = client.app.state.ctx.registry
    factory = reg.require("db.sessionmaker")
    workspace_factory = reg.require("auth.workspace_factory")
    with factory() as s:
        workspace_factory(s).set_plan_status(workspace_id, "past_due", grace_until=grace_until)
        s.commit()


def test_past_due_inside_grace_still_runs_reviews(client):
    headers, workspace_id = _auth(client, "gracein@x.com")
    _set_plan(client, headers, workspace_id, "pro")
    _set_past_due(client, workspace_id, grace_until=datetime.now(UTC) + timedelta(days=3))

    opp = client.post(
        "/api/ingestion/opportunities", json={"title": "Still going"}, headers=headers
    ).json()["id"]
    r = client.post(f"/api/risk/opportunities/{opp}/run", headers=headers)
    assert r.status_code == 200, r.text


def test_past_due_outside_grace_blocks_reviews(client):
    headers, workspace_id = _auth(client, "graceout@x.com")
    _set_plan(client, headers, workspace_id, "pro")
    _set_past_due(client, workspace_id, grace_until=datetime.now(UTC) - timedelta(days=1))

    opp = client.post(
        "/api/ingestion/opportunities", json={"title": "Overdue"}, headers=headers
    ).json()["id"]
    r = client.post(f"/api/risk/opportunities/{opp}/run", headers=headers)
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "payment_overdue"


# ---- A2: billing-anniversary period, not calendar month -------------------


def test_subscription_period_follows_provider_bounds_not_calendar_month(client):
    headers, workspace_id = _auth(client, "anniversary@x.com")
    checkout = client.post(
        "/api/billing/checkout", json={"kind": "subscription", "plan": "pro"}, headers=headers
    ).json()
    period_start = datetime(2026, 1, 28, tzinfo=UTC)
    period_end = datetime(2026, 2, 28, tzinfo=UTC)
    body = {
        "id": "evt_anniversary",
        "event": "subscription.activated",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "notes": {"intent_id": checkout["intent_id"]},
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_123",
                    "current_start": int(period_start.timestamp()),
                    "current_end": int(period_end.timestamp()),
                }
            },
        },
    }
    raw, sig = _sign(body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["period_end"] == period_end.isoformat()


def test_reviews_included_reported_for_metered_plans():
    assert PLAN_LIMITS["pro"]["reviews_month"] == 10
    assert PLAN_LIMITS["scale"]["reviews_month"] == 40
