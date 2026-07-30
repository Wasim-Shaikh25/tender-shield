"""Integration tests for the auth module through the app + HTTP layer."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.modules.auth.models  # noqa: F401 — register auth tables on Base.metadata
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec
from app.modules.auth.models import User


@pytest.fixture
def client() -> TestClient:
    application = create_app(
        Settings(enabled_modules="health,auth", database_url="sqlite:///:memory:")
    )
    engine = application.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    return TestClient(application)


TEST_PASSWORD = "Hunter2!Hunter2"


def _signup(client, email="a@example.com", phone=None):
    phone = phone or f"+91{hash(email) % 10000000000:010d}"
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "phone": phone,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
            "org_name": "Acme Infra Pvt Ltd",
            "city": "Mumbai",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _verify_account(client, email="a@example.com"):
    """Verify email and mobile using the dev/test tokens returned by signup.

    If the account already exists (e.g. a previous _signup call in the same test),
    mark it verified directly in the test DB so _login stays idempotent.
    """
    engine = client.app.state.ctx.registry.require("db.engine")
    with Session(engine) as s:
        user = s.scalar(select(User).where(User.email == email))
        if user and user.email_verified and user.mobile_verified:
            return
    signup_resp = _signup(client, email)
    assert signup_resp.get("status") == "verification_required"
    if "email_verification_token" in signup_resp:
        r = client.post(
            "/api/auth/verify-email",
            json={"token": signup_resp["email_verification_token"]},
        )
        assert r.status_code == 200, r.text
    if "mobile_verification_token" in signup_resp:
        r = client.post(
            "/api/auth/verify-mobile",
            json={"token": signup_resp["mobile_verification_token"]},
        )
        assert r.status_code == 200, r.text


def _login(client, email="a@example.com", password=TEST_PASSWORD):
    _verify_account(client, email)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    challenge = r.json()
    assert challenge["mfa_required"]
    r = client.post(
        "/api/auth/mfa/challenge",
        json={"mfa_token": challenge["mfa_token"], "code": challenge["mfa_code"]},
    )
    assert r.status_code == 200, r.text
    tokens = r.json()
    # Login no longer creates a workspace. Create one automatically for tests that
    # expect an active workspace.
    r = client.post(
        "/api/auth/workspaces",
        json={"name": "Acme Infra"},
        headers={"authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text
    workspace_id = r.json()["workspace_id"]
    r = client.post(
        f"/api/auth/workspaces/{workspace_id}/switch",
        headers={"authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_signup_login_me_flow(client):
    tokens = _login(client)
    assert tokens["role"] == "owner"
    me = client.get("/api/auth/me", headers={"authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "owner"
    assert me.json()["email_verified"] is True
    assert me.json()["mobile_verified"] is True


def test_duplicate_email_rejected(client):
    _verify_account(client)
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "a@example.com",
            "phone": "+919999999999",
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
            "org_name": "Other",
            "city": "Delhi",
        },
    )
    assert r.status_code == 409


def test_password_mismatch_rejected(client):
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "a@example.com",
            "phone": "+919999999999",
            "password": TEST_PASSWORD,
            "confirm_password": "Different123!",
            "org_name": "Acme",
            "city": "Delhi",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "password_mismatch"


def test_bad_password_rejected(client):
    _signup(client)
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope"})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    _login(client)
    r0 = client.cookies.get("refresh_token")
    assert r0

    rotated = client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    r1 = client.cookies.get("refresh_token")
    assert r1 != r0

    # replay the already-used r0 → reuse detected, whole family revoked
    client.cookies.set("refresh_token", r0)
    reuse = client.post("/api/auth/refresh")
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == "reuse_detected"

    # r1 belonged to the same family → now revoked/invalid
    client.cookies.set("refresh_token", r1)
    assert client.post("/api/auth/refresh").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_rbac_viewer_cannot_add_member(client):
    _signup(client)
    keys: sec.KeyPair = client.app.state.ctx.registry.require("auth.keys")
    viewer = sec.mint_access(
        keys,
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-0000000000aa",
        role="viewer",
        ttl=timedelta(minutes=5),
    )
    r = client.post(
        "/api/auth/members",
        json={"email": "b@example.com", "role": "estimator"},
        headers={"authorization": f"Bearer {viewer}"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "insufficient_role"


def test_capabilities_published(client):
    caps = client.get("/api/health/details").json()["capabilities"]
    assert {"auth.keys", "auth.authenticate", "auth.check_role"} <= set(caps)


def test_create_and_list_workspaces(client):
    token = _login(client)["access_token"]
    r = client.post(
        "/api/auth/workspaces",
        json={"name": "Second Workspace"},
        headers={"authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    r = client.get("/api/auth/workspaces", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2


def test_create_project_and_share_with_member(client):
    owner = _login(client, "owner@example.com")
    # add member to workspace
    _signup(client, "member@example.com")
    r = client.post(
        "/api/auth/members",
        json={"email": "member@example.com", "role": "viewer"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    # create project
    r = client.post(
        "/api/auth/workspaces/{}/projects".format(owner["workspace_id"]),
        json={"name": "Bridge Tender", "status": "tendering"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    project_id = r.json()["project_id"]
    r = client.get(
        "/api/auth/workspaces/{}/projects".format(owner["workspace_id"]),
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1
    # add project member
    r = client.post(
        f"/api/auth/projects/{project_id}/members",
        json={"email": "member@example.com", "role": "reviewer"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    r = client.get(
        f"/api/auth/projects/{project_id}/members",
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    assert any(m["email"] == "member@example.com" for m in r.json())


def test_superadmin_endpoints(client):
    user = _login(client, "admin@example.com")
    r = client.get(
        "/api/auth/admin/users",
        headers={"authorization": f"Bearer {user['access_token']}"},
    )
    assert r.status_code == 403, r.text


def test_invitation_flow(client):
    owner = _login(client, "owner2@example.com")
    workspace_id = owner["workspace_id"]

    r = client.post(
        "/api/auth/invitations",
        json={"email": "invited@example.com", "role": "reviewer"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]

    invitee = _login(client, "invited@example.com")
    r = client.post(
        f"/api/auth/invitations/{token}/accept",
        headers={"authorization": f"Bearer {invitee['access_token']}"},
    )
    assert r.status_code == 200, r.text

    r = client.get(
        f"/api/auth/workspaces/{workspace_id}/members",
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 200, r.text
    assert any(m["email"] == "invited@example.com" and m["role"] == "reviewer" for m in r.json())


def test_forgot_password_and_reset(client):
    _verify_account(client, "reset@example.com")

    # unknown email still returns ok to avoid email enumeration
    r = client.post("/api/auth/forgot-password", json={"email": "missing@example.com"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "token" not in r.json()

    r = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    token = r.json()["token"]

    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "NewPass123!"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # old password no longer works
    assert client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": TEST_PASSWORD}
    ).status_code == 401

    # new password works after going through the OTP challenge
    tokens = _login(client, "reset@example.com", "NewPass123!")
    assert tokens["role"] == "owner"


def test_reset_password_rejects_expired_or_reused_token(client):
    _verify_account(client, "reset2@example.com")
    r = client.post("/api/auth/forgot-password", json={"email": "reset2@example.com"})
    token = r.json()["token"]

    # first reset consumes token
    assert client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "NewPass123!"},
    ).status_code == 200

    # reuse fails
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass123!"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_reset_token"
