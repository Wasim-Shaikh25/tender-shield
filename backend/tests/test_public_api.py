"""Public API key management tests (TS-292 / TS-306)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,auth,public_api"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "publicapi@x.com")


def test_create_list_revoke_api_keys(client):
    auth = _auth(client)

    r = client.post(
        "/api/public_api/keys",
        json={"name": "CI", "scopes": ["read", "write"]},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "CI"
    assert data["scopes"] == ["read", "write"]
    assert "plaintext_key" in data
    key_id = data["id"]

    r = client.get("/api/public_api/keys", headers=auth)
    assert r.status_code == 200
    keys = r.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["name"] == "CI"
    assert "plaintext_key" not in keys[0]

    r = client.delete(f"/api/public_api/keys/{key_id}", headers=auth)
    assert r.status_code == 200
    assert r.json()["revoked"] is True

    r = client.get("/api/public_api/keys", headers=auth)
    assert r.json()["keys"] == []


def test_authenticate_with_valid_api_key(client):
    auth = _auth(client)
    r = client.post(
        "/api/public_api/keys",
        json={"name": "Reader", "scopes": ["read"]},
        headers=auth,
    )
    plaintext = r.json()["plaintext_key"]

    # The public API currently only exposes /notices/{id}/request-signature as a
    # keyed endpoint. Calling it without required body fields still proves auth.
    r = client.post(
        "/api/public_api/notices/00000000-0000-0000-0000-000000000000/request-signature",
        json={},
        headers={"authorization": f"Apikey {plaintext}"},
    )
    # Missing fields produce 422, not 401, proving key auth passed.
    assert r.status_code == 422


def test_invalid_api_key_rejected(client):
    r = client.post(
        "/api/public_api/notices/00000000-0000-0000-0000-000000000000/request-signature",
        json={},
        headers={"authorization": "Apikey invalid"},
    )
    assert r.status_code == 401
