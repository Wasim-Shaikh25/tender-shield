"""Integration module tests: dynamic connectors, sources, adapters, schedules."""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,claims,"
    "outcomes,integrations,boq,analytics,export"
)


@pytest.fixture
def client():
    application = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            live_connector_polling_enabled=True,
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "integrations@x.com")


def _opp(client, headers):
    r = client.post("/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_dynamic_connector_crud(client):
    auth = _auth(client)

    # Create
    body = {
        "name": "ERP Sandbox",
        "base_url": "https://erp.example.com/api",
        "auth_type": "bearer",
        "auth_config": {"token": "secret"},
        "headers": {"Accept": "application/json"},
        "pagination": {
            "type": "offset",
            "offset_param": "offset",
            "limit_param": "limit",
            "limit": 100,
        },
        "mappings": {
            "cost_lines": {
                "items": "data.items",
                "fields": {
                    "cost_code": "code",
                    "description": "name",
                    "committed_cost_minor": "value",
                    "currency": "currency",
                },
            }
        },
        "enabled": True,
    }
    r = client.post("/api/integrations/dynamic-connectors", json=body, headers=auth)
    assert r.status_code == 200, r.text
    config_id = r.json()["id"]

    # List
    r = client.get("/api/integrations/dynamic-connectors", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["connectors"]) == 1
    assert r.json()["connectors"][0]["auth_config"]["token"] == "***"

    # Get
    r = client.get(f"/api/integrations/dynamic-connectors/{config_id}", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "ERP Sandbox"
    assert data["auth_config"]["token"] == "***"

    # Update
    r = client.put(
        f"/api/integrations/dynamic-connectors/{config_id}",
        json={**body, "name": "ERP Prod"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "ERP Prod"

    # Delete
    r = client.delete(f"/api/integrations/dynamic-connectors/{config_id}", headers=auth)
    assert r.status_code == 200
    r = client.get("/api/integrations/dynamic-connectors", headers=auth)
    assert r.json()["connectors"] == []


def test_dynamic_connector_test_endpoint(client):
    auth = _auth(client)
    body = {
        "name": "ERP Sandbox",
        "base_url": "https://erp.example.com/api/v1/costs",
        "auth_type": "bearer",
        "auth_config": {"token": "secret"},
        "headers": {},
        "pagination": {},
        "mappings": {},
        "enabled": True,
    }
    r = client.post("/api/integrations/dynamic-connectors", json=body, headers=auth)
    config_id = r.json()["id"]

    with mock.patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value.status_code = 200
        instance.get.return_value.json.return_value = {"status": "ok"}
        instance.get.return_value.text = '{"status":"ok"}'

        r = client.post(f"/api/integrations/dynamic-connectors/{config_id}/test", headers=auth)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "ok"
        assert data["http_status"] == 200


def test_dynamic_connector_poll_persists_cost_lines(client):
    auth = _auth(client)
    body = {
        "name": "ERP Poll",
        "base_url": "https://erp.example.com/api/v1/costs",
        "auth_type": "none",
        "auth_config": {},
        "headers": {},
        "pagination": {"type": "none"},
        "mappings": {
            "cost_lines": {
                "items": "items",
                "fields": {
                    "cost_code": "code",
                    "description": "name",
                    "committed_cost_minor": "value",
                    "currency": "currency",
                },
            }
        },
        "enabled": True,
    }
    r = client.post("/api/integrations/dynamic-connectors", json=body, headers=auth)
    config_id = r.json()["id"]

    with mock.patch("httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.get.return_value.status_code = 200
        instance.get.return_value.json.return_value = {
            "items": [
                {"code": "A.01", "name": "Earthwork", "value": 1500000, "currency": "INR"},
            ]
        }

        r = client.post(f"/api/integrations/dynamic-connectors/{config_id}/poll", headers=auth)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "completed"
        assert data["result"]["cost_lines"][0]["cost_code"] == "A.01"


def test_integration_source_and_adapters(client):
    auth = _auth(client)
    opp_id = _opp(client, auth)

    # List adapters
    r = client.get("/api/integrations/adapters", headers=auth)
    assert r.status_code == 200, r.text
    adapters = r.json()["adapters"]
    assert any(a["kind"] == "erp" for a in adapters)

    # Create source
    r = client.post(
        "/api/integrations/sources",
        json={"adapter_kind": "erp", "name": "ERP JSON", "opportunity_id": opp_id, "config": {}},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    # List sources
    r = client.get("/api/integrations/sources", headers=auth)
    assert r.status_code == 200
    sources = r.json()["sources"]
    assert any(s["id"] == source_id for s in sources)

    # Import payload
    r = client.post(
        f"/api/integrations/sources/{source_id}/import",
        json={"payload": {"text": "sample"}},
        headers=auth,
    )
    assert r.status_code == 200, r.text


def test_dynamic_connector_404(client):
    auth = _auth(client)
    r = client.get(
        "/api/integrations/dynamic-connectors/00000000-0000-0000-0000-000000000000",
        headers=auth,
    )
    assert r.status_code == 404
