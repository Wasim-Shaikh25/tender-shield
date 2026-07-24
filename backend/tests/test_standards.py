"""Org custom notice standards (TS-047): CRUD + role gating through the app."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.standards.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules="health,auth,standards", database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client, email="s@x.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "org_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": email, "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def test_get_defaults_to_empty_then_set_and_readback(client):
    headers = _auth(client)
    empty = client.get("/api/standards/notice", headers=headers).json()
    assert empty == {"mode": "prevail", "categories": []}

    body = {
        "mode": "side_by_side",
        "categories": [
            {
                "key": "handover",
                "label": "Site handover notice",
                "typical_days": 7,
                "expected": True,
                "keywords": ["handover", "possession"],
            }
        ],
    }
    put = client.put("/api/standards/notice", json=body, headers=headers)
    assert put.status_code == 200
    got = client.get("/api/standards/notice", headers=headers).json()
    assert got["mode"] == "side_by_side"
    assert got["categories"][0]["key"] == "handover"


def test_bad_mode_and_duplicate_keys_rejected(client):
    headers = _auth(client)
    bad = client.put(
        "/api/standards/notice", json={"mode": "nonsense", "categories": []}, headers=headers
    )
    assert bad.status_code == 400
    dup = client.put(
        "/api/standards/notice",
        json={
            "mode": "prevail",
            "categories": [
                {"key": "x", "label": "X"},
                {"key": "x", "label": "X2"},
            ],
        },
        headers=headers,
    )
    assert dup.status_code == 409


def test_clear_removes_the_standard(client):
    headers = _auth(client)
    client.put(
        "/api/standards/notice",
        json={"mode": "prevail", "categories": [{"key": "x", "label": "X"}]},
        headers=headers,
    )
    client.delete("/api/standards/notice", headers=headers)
    assert client.get("/api/standards/notice", headers=headers).json()["categories"] == []
