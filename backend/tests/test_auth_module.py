"""Integration tests for the auth module through the app + HTTP layer."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401 — register auth tables on Base.metadata
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec


def _make_client(**settings_kwargs) -> TestClient:
    application = create_app(
        Settings(
            enabled_modules="health,auth",
            database_url="sqlite:///:memory:",
            **settings_kwargs,
        )
    )
    engine = application.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    return TestClient(application)


@pytest.fixture
def client() -> TestClient:
    # dev_echo_tokens=True so tests that need to drive the reset/invitation
    # flow end-to-end can read the token straight from the response, matching
    # local dev. The production default (False) is exercised explicitly by
    # test_forgot_password_default_does_not_echo_token below (R-002 §A).
    return _make_client(dev_echo_tokens=True)


def _signup(client, email="a@example.com"):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "workspace_name": "Acme Infra"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_signup_login_me_flow(client):
    _signup(client)
    r = client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "hunter2hunter2"}
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
        json={"email": "a@example.com", "password": "hunter2hunter2", "workspace_name": "Other"},
    )
    assert r.status_code == 409


def test_bad_password_rejected(client):
    _signup(client)
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope"})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    _signup(client)
    tokens = client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "hunter2hunter2"}
    ).json()
    r0 = tokens["refresh_token"]

    rotated = client.post("/api/auth/refresh", json={"refresh_token": r0})
    assert rotated.status_code == 200
    r1 = rotated.json()["refresh_token"]
    assert r1 != r0

    # replay the already-used r0 → reuse detected, whole family revoked
    reuse = client.post("/api/auth/refresh", json={"refresh_token": r0})
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == "reuse_detected"

    # r1 belonged to the same family → now revoked/invalid
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401


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
    caps = client.get("/api/health").json()["capabilities"]
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
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
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
        json={"token": token, "new_password": "newpass123"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # old password no longer works
    assert client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "hunter2hunter2"}
    ).status_code == 401

    # new password works
    r = client.post(
        "/api/auth/login", json={"email": "reset@example.com", "password": "newpass123"}
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
        json={"token": token, "new_password": "newpass123"},
    ).status_code == 200

    # reuse fails
    r = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "anotherpass123"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_reset_token"


# ---- R-002 §A: reset/invitation tokens are dev-only (TS-085) --------------


def test_forgot_password_default_does_not_echo_token():
    # Default settings (dev_echo_tokens=False) — the production posture.
    prod_like = _make_client()
    prod_like.post(
        "/api/auth/signup",
        json={"email": "noecho@example.com", "password": "hunter2hunter2"},
    )
    r = prod_like.post("/api/auth/forgot-password", json={"email": "noecho@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert "token" not in r.json()


def test_settings_refuse_echo_tokens_in_production():
    with pytest.raises(ValueError, match="TS_DEV_ECHO_TOKENS"):
        Settings(env="production", dev_echo_tokens=True)


def test_new_reset_invalidates_prior_outstanding_reset(client):
    _signup(client, "tworesets@example.com")
    first = client.post(
        "/api/auth/forgot-password", json={"email": "tworesets@example.com"}
    ).json()["token"]
    # issuing a second reset invalidates the first, unused one
    client.post("/api/auth/forgot-password", json={"email": "tworesets@example.com"})

    r = client.post(
        "/api/auth/reset-password",
        json={"token": first, "new_password": "newpass123"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_reset_token"


def test_password_reset_revokes_existing_sessions(client):
    _signup(client, "revoke@example.com")
    tokens = _login(client, "revoke@example.com")
    refresh_token = tokens["refresh_token"]

    reset_token = client.post(
        "/api/auth/forgot-password", json={"email": "revoke@example.com"}
    ).json()["token"]
    client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
    )

    r = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


# ---- R-001 §A: workspace/project membership authorization (TS-084) --------


def test_member_list_is_workspace_scoped(client):
    a = _signup(client, "a-owner@example.com")
    _signup(client, "b-owner@example.com")
    a_owner = _login(client, "a-owner@example.com")

    # A's owner cannot read B's member list by guessing B's workspace id
    b_workspace_id = _signup(client, "probe@example.com")["workspace_id"]
    r = client.get(
        f"/api/auth/workspaces/{b_workspace_id}/members",
        headers={"authorization": f"Bearer {a_owner['access_token']}"},
    )
    assert r.status_code == 404

    # but can read its own
    r = client.get(
        f"/api/auth/workspaces/{a['workspace_id']}/members",
        headers={"authorization": f"Bearer {a_owner['access_token']}"},
    )
    assert r.status_code == 200


def test_cannot_escalate_into_another_workspace(client):
    _signup(client, "attacker@example.com")
    attacker = _login(client, "attacker@example.com")
    victim_workspace_id = _signup(client, "victim@example.com")["workspace_id"]

    r = client.post(
        f"/api/auth/workspaces/{victim_workspace_id}/members",
        json={"email": "attacker@example.com", "role": "owner"},
        headers={"authorization": f"Bearer {attacker['access_token']}"},
    )
    assert r.status_code == 404

    # confirm no membership was created
    r = client.get(
        "/api/auth/workspaces", headers={"authorization": f"Bearer {attacker['access_token']}"}
    )
    assert len(r.json()) == 1


def test_project_members_scoped_to_project_workspace(client):
    _signup(client, "p-owner@example.com")
    owner = _login(client, "p-owner@example.com")
    project = client.post(
        f"/api/auth/workspaces/{owner['workspace_id']}/projects",
        json={"name": "Bridge Tender"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    ).json()

    _signup(client, "outsider@example.com")
    outsider = _login(client, "outsider@example.com")
    r = client.get(
        f"/api/auth/projects/{project['project_id']}/members",
        headers={"authorization": f"Bearer {outsider['access_token']}"},
    )
    assert r.status_code == 404


def test_last_owner_cannot_be_demoted(client):
    signup = _signup(client, "sole-owner@example.com")
    owner = _login(client, "sole-owner@example.com")
    r = client.post(
        f"/api/auth/workspaces/{signup['workspace_id']}/members",
        json={"email": "sole-owner@example.com", "role": "viewer"},
        headers={"authorization": f"Bearer {owner['access_token']}"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "last_owner"


# ---- R-002 §C: rate limiting + per-account lockout (TS-094) ---------------


def test_login_rate_limited_per_ip(client):
    # Different accounts each attempt, so this exercises the IP-wide limiter
    # rather than the per-account lockout (LOGIN_LIMIT=20 > lockout threshold
    # of 10, specifically so the two don't collide within one test client).
    for i in range(20):
        _signup(client, f"rl{i}@example.com")
        r = client.post(
            "/api/auth/login", json={"email": f"rl{i}@example.com", "password": "wrong"}
        )
        assert r.status_code == 401
    r = client.post(
        "/api/auth/login", json={"email": "rl0@example.com", "password": "wrong"}
    )
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_signup_rate_limited(client):
    for i in range(20):
        client.post(
            "/api/auth/signup",
            json={"email": f"spam{i}@example.com", "password": "hunter2hunter2"},
        )
    r = client.post(
        "/api/auth/signup",
        json={"email": "onemore@example.com", "password": "hunter2hunter2"},
    )
    assert r.status_code == 429


def test_account_locks_after_repeated_failures():
    # Fresh, unshared limiter: this test alone makes 11 login calls against
    # one account plus a successful one, comfortably under the 10/5min IP
    # limit only if isolated from other tests' login traffic.
    c = _make_client(dev_echo_tokens=True)
    c.post(
        "/api/auth/signup",
        json={"email": "lockout@example.com", "password": "correct-horse-battery"},
    )
    for _ in range(10):
        r = c.post(
            "/api/auth/login",
            json={"email": "lockout@example.com", "password": "wrong"},
        )
        assert r.status_code == 401

    # 10 failures reached the lockout threshold — even the correct password
    # is now rejected until the backoff window elapses.
    r = c.post(
        "/api/auth/login",
        json={"email": "lockout@example.com", "password": "correct-horse-battery"},
    )
    assert r.status_code == 423
    assert r.json()["detail"] == "account_locked"


def test_successful_login_resets_failed_counter(client):
    _signup(client, "resetcounter@example.com")
    for _ in range(3):
        r = client.post(
            "/api/auth/login",
            json={"email": "resetcounter@example.com", "password": "wrong"},
        )
        assert r.status_code == 401
    r = client.post(
        "/api/auth/login",
        json={"email": "resetcounter@example.com", "password": "hunter2hunter2"},
    )
    assert r.status_code == 200
