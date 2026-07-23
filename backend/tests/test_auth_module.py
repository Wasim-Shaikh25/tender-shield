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


def _signup(client, email="a@example.com"):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "org_name": "Acme Infra"},
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
        json={"email": "a@example.com", "password": "hunter2hunter2", "org_name": "Other"},
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
        keys, user_id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-0000000000aa", role="viewer", ttl=timedelta(minutes=5),
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
    assert {"auth.keys", "auth.current_principal", "auth.require"} <= set(caps)
