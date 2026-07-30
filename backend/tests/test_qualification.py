"""Qualification matrix: deterministic eligibility extraction."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,qualification",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "q@x.com")

def _opp_with_text(client, headers, text):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.pdf", "sample_text": text},
        headers=headers,
    )
    return opp_id


def test_qualification_matrix_extracts_criteria(client):
    headers = _auth(client)
    text = (
        "[p1] The bidder shall have a minimum turnover of Rs. 10 Cr in the last three years.\n"
        "[p2] Similar works of similar nature costing not less than Rs. 5 Cr.\n"
        "[p3] Bidder must deploy adequate equipment and machinery.\n"
        "[p4] The project manager shall be a graduate engineer.\n"
        "[p5] ISO 9001 certification is mandatory.\n"
        "[p6] EMD of Rs. 50,000 is required.\n"
        "[p7] Bid security in the form of bank guarantee.\n"
        "[p8] Minimum experience of five years in construction of similar works.\n"
    )
    opp_id = _opp_with_text(client, headers, text)

    resp = client.post(f"/api/qualification/opportunities/{opp_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_review"

    keys = {c["key"] for c in body["criteria"]}
    required = {
        "minimum_turnover",
        "similar_project_experience",
        "equipment_requirements",
        "engineer_requirements",
        "certifications",
        "emd_amount",
        "bid_security",
        "experience_years",
    }
    assert required <= keys

    for c in body["criteria"]:
        assert c["status"] == "unknown"
        assert c["source_quote"]
        assert c["action_required"]


def test_qualification_matrix_flags_missing_criteria(client):
    headers = _auth(client)
    opp_id = _opp_with_text(client, headers, "[p1] Scope of work.\n")

    resp = client.get(f"/api/qualification/opportunities/{opp_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_eligible"
    assert any(c["status"] == "not_met" for c in body["criteria"])
