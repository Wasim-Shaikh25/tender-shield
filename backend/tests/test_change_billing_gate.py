"""Per-project billing gate for change events (TS-256)."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base, bind_workspace_context
from app.main import create_app
from app.modules.billing.models import ProjectSubscription
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,billing"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "billinggate@x.com")


def _freeze_project(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Billing gate"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 1 — Works.\n"},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    for finding in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{finding['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender"},
        headers=headers,
    ).raise_for_status()
    return opp_id


def _create_event(client, headers, opp_id, title: str):
    return client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": title,
            "sources": [{"source_quote": f"change noted for {title}", "source_page": 1}],
        },
        headers=headers,
    )


def test_third_event_requires_project_activation(client):
    headers = _auth(client)
    opp_id = _freeze_project(client, headers)

    assert _create_event(client, headers, opp_id, "Event 1").status_code == 200
    assert _create_event(client, headers, opp_id, "Event 2").status_code == 200

    blocked = _create_event(client, headers, opp_id, "Event 3")
    assert blocked.status_code == 402
    assert blocked.json()["detail"] == "billing_required"


def test_activated_project_allows_third_event(client):
    headers = _auth(client)
    opp_id = _freeze_project(client, headers)
    _create_event(client, headers, opp_id, "Event 1").raise_for_status()
    _create_event(client, headers, opp_id, "Event 2").raise_for_status()

    session_maker = client.app.state.ctx.registry.get("db.sessionmaker")
    session = session_maker()
    try:
        from app.modules.auth.models import Workspace

        ws = session.query(Workspace).first()
        bind_workspace_context(session, ws.id)
        session.add(
            ProjectSubscription(
                workspace_id=ws.id,
                opportunity_id=uuid.UUID(str(opp_id)),
                status="active",
                activated_at=datetime.now(UTC),
                activation_fee_minor=25_000_00,
                currency="INR",
            )
        )
        session.commit()
    finally:
        session.close()

    third = _create_event(client, headers, opp_id, "Event 3")
    assert third.status_code == 200, third.text


def test_project_status_endpoint(client):
    headers = _auth(client)
    opp_id = _freeze_project(client, headers)
    status = client.get(f"/api/billing/projects/{opp_id}/status", headers=headers)
    assert status.status_code == 200
    body = status.json()
    assert body["active"] is False
    assert body["activation_fee_minor"] == 25_000_00
