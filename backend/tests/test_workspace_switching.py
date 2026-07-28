"""Workspace switching (R-011, TS-100). Before this, a user who belonged to
several workspaces landed in an arbitrary one at login — an unordered
`WorkspaceMember` query meant the SAME user could land somewhere different
between logins — and had no way to reach any workspace but the one baked
into their current token.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth.models import User
from app.modules.auth.security import KeyPair, generate_keypair
from app.modules.auth.service import AuthService


def _make_client() -> TestClient:
    application = create_app(
        Settings(enabled_modules="health,auth", database_url="sqlite:///:memory:")
    )
    engine = application.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    return TestClient(application)


@pytest.fixture
def client() -> TestClient:
    return _make_client()


def _signup(client, email, workspace_name):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "workspace_name": workspace_name},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    assert r.status_code == 200, r.text
    return r.json()


def _headers(tokens):
    return {"authorization": f"Bearer {tokens['access_token']}"}


def test_login_resolves_the_same_workspace_deterministically(client):
    """A1: a user in three workspaces logs in twice and lands in the same
    workspace both times — before the fix, an unordered query meant this
    could flip between logins for the exact same user."""
    signup = _signup(client, "multi@example.com", "Workspace A")
    tokens = _login(client, "multi@example.com")
    for name in ("Workspace B", "Workspace C"):
        client.post("/api/auth/workspaces", json={"name": name}, headers=_headers(tokens))

    first = _login(client, "multi@example.com")
    second = _login(client, "multi@example.com")
    assert first["workspace_id"] == second["workspace_id"] == signup["workspace_id"]


def test_switch_workspace_returns_tokens_scoped_to_the_new_workspace(client):
    """A2: the switched token's workspace claim is B and role is the
    caller's role in B (not carried over from A)."""
    _signup(client, "owner2@example.com", "Workspace A")
    tokens = _login(client, "owner2@example.com")
    b = client.post(
        "/api/auth/workspaces", json={"name": "Workspace B"}, headers=_headers(tokens)
    ).json()

    switched = client.post(
        f"/api/auth/workspaces/{b['workspace_id']}/switch",
        json={"refresh_token": tokens["refresh_token"]},
        headers=_headers(tokens),
    )
    assert switched.status_code == 200, switched.text
    body = switched.json()
    assert body["workspace_id"] == b["workspace_id"]
    assert body["role"] == "owner"  # creator of B is its owner too

    me = client.get("/api/auth/me", headers=_headers(body))
    assert me.json()["workspace_id"] == b["workspace_id"]

    # A subsequent LOGIN (not just /me on the still-live token) must also
    # land in B: switching set last_workspace_id, and B is NOT the oldest
    # membership (A was created first at signup) — so this only passes if
    # login's deterministic resolution actually reads last_workspace_id
    # rather than falling back to an unordered/oldest-membership pick.
    relogin = _login(client, "owner2@example.com")
    assert relogin["workspace_id"] == b["workspace_id"]


def test_switch_to_a_workspace_the_user_is_not_a_member_of_returns_404(client):
    """A3."""
    _signup(client, "solo@example.com", "Workspace A")
    tokens = _login(client, "solo@example.com")
    _signup(client, "other@example.com", "Workspace X")
    other_tokens = _login(client, "other@example.com")

    r = client.post(
        f"/api/auth/workspaces/{other_tokens['workspace_id']}/switch",
        json={"refresh_token": tokens["refresh_token"]},
        headers=_headers(tokens),
    )
    assert r.status_code == 404, r.text


def test_switching_retires_the_previous_refresh_family(client):
    """A5: the pre-switch refresh token returns 401 afterwards."""
    _signup(client, "retire@example.com", "Workspace A")
    tokens = _login(client, "retire@example.com")
    b = client.post(
        "/api/auth/workspaces", json={"name": "Workspace B"}, headers=_headers(tokens)
    ).json()

    client.post(
        f"/api/auth/workspaces/{b['workspace_id']}/switch",
        json={"refresh_token": tokens["refresh_token"]},
        headers=_headers(tokens),
    )

    stale_refresh = client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert stale_refresh.status_code == 401, stale_refresh.text


def test_role_is_per_workspace_after_switching(client):
    """A6: owner in A, viewer in B — cannot create a project (admin-gated)
    in B after switching there."""
    _signup(client, "roleA@example.com", "Workspace A")
    owner_tokens = _login(client, "roleA@example.com")
    viewer_signup = _signup(client, "roleB@example.com", "Workspace B")
    viewer_tokens = _login(client, "roleB@example.com")

    # Make roleA@example.com a viewer in Workspace B.
    client.post(
        f"/api/auth/workspaces/{viewer_signup['workspace_id']}/members",
        json={"email": "roleA@example.com", "role": "viewer"},
        headers=_headers(viewer_tokens),
    )

    switched = client.post(
        f"/api/auth/workspaces/{viewer_signup['workspace_id']}/switch",
        json={"refresh_token": owner_tokens["refresh_token"]},
        headers=_headers(owner_tokens),
    ).json()
    assert switched["role"] == "viewer"

    r = client.post(
        f"/api/auth/workspaces/{viewer_signup['workspace_id']}/projects",
        json={"name": "Should be blocked"},
        headers=_headers(switched),
    )
    assert r.status_code == 403, r.text


def test_list_workspaces_reports_plan_and_is_current(client):
    _signup(client, "listws@example.com", "Workspace A")
    tokens = _login(client, "listws@example.com")
    b = client.post(
        "/api/auth/workspaces", json={"name": "Workspace B"}, headers=_headers(tokens)
    ).json()

    rows = client.get("/api/auth/workspaces", headers=_headers(tokens)).json()
    assert len(rows) == 2
    current = [r for r in rows if r["is_current"]]
    assert len(current) == 1
    assert current[0]["workspace_id"] == tokens["workspace_id"]
    assert all("plan" in r for r in rows)

    switched = client.post(
        f"/api/auth/workspaces/{b['workspace_id']}/switch",
        json={"refresh_token": tokens["refresh_token"]},
        headers=_headers(tokens),
    ).json()
    rows_after = client.get("/api/auth/workspaces", headers=_headers(switched)).json()
    current_after = [r for r in rows_after if r["is_current"]]
    assert current_after[0]["workspace_id"] == b["workspace_id"]


# ---- service-level: a signup-free path to a zero-membership user --------
# /signup always creates a workspace, so a genuinely membership-less user
# (R-011 §B.6's target state) can't be produced through the HTTP API alone —
# exercised directly against AuthService instead.


@pytest.fixture
def service_session():
    application = _make_client().app
    factory = application.state.ctx.registry.require("db.sessionmaker")
    session = factory()
    yield session
    session.close()


def test_zero_membership_user_gets_a_workspace_less_token_not_a_dead_end(service_session):
    """A7: a user with zero memberships logs in and receives a workspace-less
    token instead of AuthError("no_workspace") — the frontend routes this to
    /workspaces/new rather than a dead end."""
    keys: KeyPair = generate_keypair()
    svc = AuthService(service_session, keys)
    user = User(email="orphan@example.com", password_hash=None)
    service_session.add(user)
    service_session.flush()
    # sec.verify_password would reject a None hash, so set a real one via the
    # service's own hashing to keep this test exercising login(), not a
    # bypass of it.
    from app.modules.auth import security as sec

    user.password_hash = sec.hash_password("hunter2hunter2")
    service_session.commit()

    result = svc.login("orphan@example.com", "hunter2hunter2")
    assert result["workspace_id"] == AuthService._NO_WORKSPACE
    assert result["role"] == "owner"
