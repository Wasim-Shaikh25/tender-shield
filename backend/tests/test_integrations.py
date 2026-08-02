"""Integrations module tests (TS-336 SSRF protection)."""

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

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,integrations"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
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
