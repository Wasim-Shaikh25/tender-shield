"""Integration tests for the auth module through the app + HTTP layer."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401 — register auth tables on Base.metadata
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec


@pytest.fixture
def client() -> TestClient:
    application = create_app(
        Settings(enabled_modules="health,auth", database_url="sqlite:///:memory:")
    )
    engine = application.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    return TestClient(application)


TEST_PASSWORD = "Hunter2!Hunter2"


def _signup(client, email="a@example.com"):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": TEST_PASSWORD, "workspace_name": "Acme Infra"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_signup_login_me_flow(client):
    _signup(client)
    r = client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": TEST_PASSWORD}
    )
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["role"] == "owner"
    me = client.get("/api/auth/me", headers={"authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


def test_duplicate_email_rejected(client):
    _signup(client)
    r = client.post(
        "/api/auth/signup",
        json={"email": "a@example.com", "password": TEST_PASSWORD, "workspace_name": "Other"},
    )
    assert r.status_code == 409


def test_bad_password_rejected(client):
    _signup(client)
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope"})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    _signup(client)
    client.post("/api/auth/login", json={"email": "a@example.com", "password": TEST_PASSWORD})
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


def test_apple_callback_not_configured(client):
    r = client.post("/api/auth/apple/callback", json={"id_token": "x"})
    assert r.status_code == 503
    assert r.json()["detail"] == "apple_not_configured"


def test_apple_callback_creates_user_and_issues_tokens(client, monkeypatch):
    from app.modules.auth import apple

    client.app.state.ctx.settings.apple_services_id = "test.app"

    def fake_init(self, settings):
        self.settings = settings

    def fake_is_configured(self):
        return True

    def fake_verify_id_token(self, id_token: str):
        return {
            "sub": "apple_001",
            "email": "apple@example.com",
            "email_verified": True,
        }

    monkeypatch.setattr(apple.AppleClient, "__init__", fake_init)
    monkeypatch.setattr(apple.AppleClient, "is_configured", fake_is_configured)
    monkeypatch.setattr(apple.AppleClient, "verify_id_token", fake_verify_id_token)

    r = client.post(
        "/api/auth/apple/callback",
        json={"id_token": "x", "user": '{"name": {"firstName": "Test", "lastName": "User"}}'},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


def _login(client, email="a@example.com"):
    r = client.post("/api/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_and_list_workspaces(client):
    _signup(client)
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
    _signup(client, "owner@example.com")
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
    _signup(client, "admin@example.com")
    user = _login(client, "admin@example.com")
    r = client.get(
        "/api/auth/admin/users",
        headers={"authorization": f"Bearer {user['access_token']}"},
    )
    assert r.status_code == 403, r.text


def test_invitation_flow(client):
    _signup(client, "owner2@example.com")
    owner = _login(client, "owner2@example.com")
    _signup(client, "invited@example.com")
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
    _signup(client, "reset@example.com")

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

    # new password works
    r = client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "NewPass123!"}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


def test_reset_password_rejects_expired_or_reused_token(client):
    _signup(client, "reset2@example.com")
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
