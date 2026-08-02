"""Integration module tests: dynamic connectors, sources, adapters, schedules."""

from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.integrations.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.integrations.connectors.dynamic import DynamicConnectorError, validate_url
from app.modules.integrations.service import IntegrationsError, IntegrationsService
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


@pytest.fixture
def service(client):
    app = client.app
    Session = app.state.ctx.registry.require("db.sessionmaker")
    with Session() as session:
        yield IntegrationsService(session)


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
class TestValidateUrl:
    """Unit tests for dynamic connector SSRF URL validation."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://1.1.1.1/",
            "https://8.8.8.8/",
            "https://example.com/api/v1",
            "http://public-sandbox.example.org:8080/",
        ],
    )
    def test_accepts_public_addresses(self, url: str):
        validate_url(url)  # does not raise

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "https://localhost/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "file:///etc/passwd",
            "ftp://ftp.example.com/",
            "gopher://gopher.example.com/",
            "http://user:pass@example.com/",
            "",
            "not-a-url",
        ],
    )
    def test_rejects_unsafe_urls(self, url: str):
        with pytest.raises(DynamicConnectorError):
            validate_url(url)


class TestDynamicConnectorService:
    """Service-level tests for dynamic connector CRUD."""

    def test_create_dynamic_connector_rejects_private_url(self, service: IntegrationsService):
        # A workspace/user id are required but not used beyond scoping.
        import uuid

        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        with pytest.raises(IntegrationsError) as exc_info:
            service.create_dynamic_connector(
                workspace_id,
                user_id,
                {"name": "bad", "base_url": "http://169.254.169.254/"},
            )
        assert exc_info.value.code == "invalid_url"

    def test_update_dynamic_connector_rejects_private_url(self, service: IntegrationsService):
        import uuid

        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        row = service.create_dynamic_connector(
            workspace_id,
            user_id,
            {"name": "good", "base_url": "https://1.1.1.1/"},
        )
        with pytest.raises(IntegrationsError) as exc_info:
            service.update_dynamic_connector(
                workspace_id,
                row["id"],
                {"base_url": "http://127.0.0.1/"},
            )
        assert exc_info.value.code == "invalid_url"

    def test_update_dynamic_connector_partial_without_url_is_allowed(
        self, service: IntegrationsService
    ):
        import uuid

        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        row = service.create_dynamic_connector(
            workspace_id,
            user_id,
            {"name": "good", "base_url": "https://1.1.1.1/"},
        )
        updated = service.update_dynamic_connector(workspace_id, row["id"], {"name": "renamed"})
        assert updated["name"] == "renamed"


class TestDynamicConnectorRoutes:
    """Route-level tests for dynamic connector SSRF protection."""

    def test_create_dynamic_connector_route_rejects_private_url(self, client: TestClient):
        headers = _auth(client)
        r = client.post(
            "/api/integrations/dynamic-connectors",
            json={"name": "bad", "base_url": "http://169.254.169.254/"},
            headers=headers,
        )
        assert r.status_code == 400
        assert r.json()["detail"] == "invalid_url"

    def test_create_dynamic_connector_route_accepts_public_url(self, client: TestClient):
        headers = _auth(client)
        r = client.post(
            "/api/integrations/dynamic-connectors",
            json={"name": "good", "base_url": "https://1.1.1.1/"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["base_url"] == "https://1.1.1.1/"


class TestIntegrationWebhooks:
    """Route-level tests for integration source webhook signature verification."""

    @staticmethod
    def _signature(secret: str, body: bytes) -> str:
        import hmac
        from hashlib import sha256

        return hmac.new(secret.encode(), body, sha256).hexdigest()

    def _create_source(self, client: TestClient, headers: dict, secret: str | None) -> str:
        payload: dict[str, Any] = {"adapter_kind": "dynamic", "name": "webhook-source"}
        if secret:
            payload["webhook_secret"] = secret
        r = client.post("/api/integrations/sources", json=payload, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_webhook_with_valid_signature_is_accepted(self, client: TestClient):
        headers = _auth(client)
        secret = "super-secret"
        source_id = self._create_source(client, headers, secret)
        body = b'{"events":[{"source_native_id":"x"}]}'
        sig = self._signature(secret, body)
        r = client.post(
            f"/api/integrations/sources/{source_id}/webhook",
            content=body,
            headers={
                **headers,
                "X-Integration-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "received"

    def test_webhook_with_invalid_signature_is_rejected(self, client: TestClient):
        headers = _auth(client)
        secret = "super-secret"
        source_id = self._create_source(client, headers, secret)
        body = b'{"events":[]}'
        r = client.post(
            f"/api/integrations/sources/{source_id}/webhook",
            content=body,
            headers={
                **headers,
                "X-Integration-Signature": "bad",
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "webhook_unauthorized"

    def test_webhook_without_signature_is_rejected(self, client: TestClient):
        headers = _auth(client)
        secret = "super-secret"
        source_id = self._create_source(client, headers, secret)
        body = b'{"events":[]}'
        r = client.post(
            f"/api/integrations/sources/{source_id}/webhook",
            content=body,
            headers={**headers, "Content-Type": "application/json"},
        )
        assert r.status_code == 401

    def test_webhook_with_valid_signature_but_invalid_json(self, client: TestClient):
        headers = _auth(client)
        secret = "super-secret"
        source_id = self._create_source(client, headers, secret)
        body = b"not json"
        sig = self._signature(secret, body)
        r = client.post(
            f"/api/integrations/sources/{source_id}/webhook",
            content=body,
            headers={
                **headers,
                "X-Integration-Signature": sig,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 422
        assert r.json()["detail"] == "invalid_webhook_payload"
