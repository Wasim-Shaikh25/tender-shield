"""Referral cross-tenant flow under REAL Postgres with FORCE RLS live (R-006
§B.7, TS-090). SQLite's `bind_workspace_context` is a documented no-op, so
these tests pass vacuously there and can't prove the referral flow actually
works — this is what caught two real bugs during development:

1. Resolving a referral code via a plain `Workspace.referral_code` query
   (`WorkspaceAdmin.find_by_referral_code`) silently found nothing: the
   signing-up referred user's session is bound to their OWN new workspace,
   not the referrer's, so RLS's compound predicate hides the referrer's
   `workspaces` row. Fixed by resolving through billing's own non-RLS
   `referral_codes` pointer table instead (same precedent as
   `payment_intents`/`refresh_tokens`/`password_resets`).
2. Even once found, crediting the referrer's workspace from within the
   referred workspace's webhook-processing transaction violated `credits`'
   `WITH CHECK` (a genuine cross-tenant write). Fixed by explicitly rebinding
   RLS context (`bind_workspace_context`) around that specific insert.

Mirrors test_rls_postgres.py's fixture pattern (full WORKSPACE_SCOPED_TABLES
RLS, workspaces/workspace_members compound predicates) but drives the flow
through the real FastAPI app + TestClient, since the bug lived in how
auth and billing cooperate across the module boundary, not in one query.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

import app.modules.auth.models as auth_models  # noqa: F401
import app.modules.billing.models as billing_models  # noqa: F401
from app.core.config import Settings
from app.core.db import (
    EXTRA_RLS_TABLES,
    WORKSPACE_SCOPED_TABLES,
    Base,
    rls_statements,
    workspace_members_rls_statements,
    workspaces_rls_statements,
)
from app.main import create_app
from app.modules.billing.providers.base import OrderHandle
from app.modules.billing.providers.razorpay import RazorpayProvider

pytestmark = pytest.mark.postgres

SECRET = "dev-razorpay-secret"
PG_URL = os.environ.get(
    "TS_TEST_DATABASE_URL",
    "postgresql+psycopg://tendershield:tendershield@localhost:5432/tendershield_rls",
)


def _drop_cross_table_policy_dependency(engine) -> None:
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT to_regclass('public.workspaces')")).scalar()
        if exists:
            conn.execute(text("DROP POLICY IF EXISTS workspace_isolation ON workspaces"))


@pytest.fixture
def pg_engine():
    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"PostgreSQL not reachable at {PG_URL}: {exc}")

    _drop_cross_table_policy_dependency(engine)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in sorted(WORKSPACE_SCOPED_TABLES):
            for stmt in rls_statements(table):
                conn.execute(text(stmt))
        for table, id_column in EXTRA_RLS_TABLES.items():
            for stmt in rls_statements(table, id_column=id_column):
                conn.execute(text(stmt))
        for stmt in workspaces_rls_statements():
            conn.execute(text(stmt))
        for stmt in workspace_members_rls_statements():
            conn.execute(text(stmt))
    yield engine
    _drop_cross_table_policy_dependency(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(pg_engine, monkeypatch) -> TestClient:
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
            enabled_modules="health,auth,billing",
            database_url=PG_URL,
            razorpay_key_id="rzp_test_fake",
            razorpay_key_secret="fake_secret",
            razorpay_webhook_secret=SECRET,
        )
    )
    return TestClient(app)


def _auth(client, email, referral_code=None):
    body = {"email": email, "password": "hunter2hunter2", "workspace_name": "Acme"}
    if referral_code:
        body["referral_code"] = referral_code
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    assert r.status_code == 200, r.text
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["workspace_id"]


def _sign(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _pay(client, headers, *, plan="pro", event_id="evt_1"):
    checkout = client.post(
        "/api/billing/checkout", json={"kind": "subscription", "plan": plan}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    intent = checkout.json()
    event_body = {
        "id": event_id,
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
    raw, sig = _sign(event_body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text
    return intent


def test_referral_signup_and_reward_survive_real_rls(client):
    """The referred user's signup transaction is bound to THEIR OWN new
    workspace, never the referrer's — a plain `Workspace.referral_code`
    lookup from inside that transaction is exactly the query RLS is designed
    to block. If this regresses to that approach, `referrals` stays empty
    and both balances stay 0, silently."""
    referrer_headers, referrer_ws = _auth(client, "referrer@co-a.com")
    code = client.get("/api/billing/referral", headers=referrer_headers).json()["code"]

    referred_headers, referred_ws = _auth(client, "referred@co-b.com", referral_code=code)
    assert referred_ws != referrer_ws

    _pay(client, referred_headers, event_id="evt_reward")

    referrer_credits = client.get("/api/billing/credits", headers=referrer_headers).json()
    referred_credits = client.get("/api/billing/credits", headers=referred_headers).json()
    assert referrer_credits["balance_minor"] == 250_000, referrer_credits
    assert referred_credits["balance_minor"] == 250_000, referred_credits

    # A second purchase (different plan, so it doesn't collide with the first
    # checkout's idempotency-bucket key) must not reward twice.
    _pay(client, referred_headers, plan="scale", event_id="evt_second")
    referrer_credits_after = client.get("/api/billing/credits", headers=referrer_headers).json()
    assert referrer_credits_after["balance_minor"] == 250_000, referrer_credits_after


def test_referral_credit_write_is_cross_tenant_and_needs_its_own_rls_binding(client):
    """Isolates bug #2 directly: even with the referrer correctly found, the
    webhook-processing transaction stays bound to the REFERRED workspace
    throughout (process_webhook binds once, to the intent's own workspace).
    Crediting the referrer's workspace from inside that binding is a
    genuine cross-tenant write; `_reward_referral_if_qualifying` must rebind
    before it or Postgres's WITH CHECK on `credits` rejects the insert and
    the whole webhook transaction would fail to apply."""
    referrer_headers, referrer_ws = _auth(client, "referrer2@co-a.com")
    code = client.get("/api/billing/referral", headers=referrer_headers).json()["code"]
    referred_headers, _ = _auth(client, "referred2@co-b.com", referral_code=code)

    result = _pay(client, referred_headers, event_id="evt_cross_tenant")
    assert result["amount_minor"] > 0

    referrer_credits = client.get("/api/billing/credits", headers=referrer_headers).json()
    assert referrer_credits["balance_minor"] == 250_000
    assert referrer_credits["entries"][0]["reason"] == "referral"
