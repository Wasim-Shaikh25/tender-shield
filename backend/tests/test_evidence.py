"""Evidence module integration tests (TS-254, TS-255)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.evidence.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,evidence"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "evidence@x.com")


def _setup_project(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Evidence site"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": "[p1]\nClause 12 — Variations require notice.\n",
        },
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
    event_id = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Steel revision",
            "reason": "drawing_revision",
            "sources": [{"source_quote": "extra steel bracing required", "source_page": 4}],
        },
        headers=headers,
    ).json()["id"]
    return opp_id, event_id


def test_attach_evidence_via_change_route(client):
    headers = _auth(client)
    _, event_id = _setup_project(client, headers)

    attached = client.post(
        f"/api/change/events/{event_id}/evidence",
        json={
            "record_type": "photograph",
            "title": "Site photo — bay 3",
        },
        headers=headers,
    )
    assert attached.status_code == 200, attached.text
    body = attached.json()
    assert body["record_type"] == "photograph"
    assert body["custody_chain"][0]["action"] == "created"


def test_completeness_lists_missing_types(client):
    headers = _auth(client)
    _, event_id = _setup_project(client, headers)

    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={"record_type": "photograph", "title": "Photo"},
        headers=headers,
    ).raise_for_status()

    completeness = client.get(
        f"/api/evidence/events/{event_id}/completeness", headers=headers
    )
    assert completeness.status_code == 200
    payload = completeness.json()
    assert payload["score"] < 100
    assert payload["missing_types"]

    detail = client.get(f"/api/change/events/{event_id}", headers=headers).json()
    assert detail["evidence_completeness"]["score"] == payload["score"]
