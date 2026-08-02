"""Governance, document-class ACL, and branded report templates (TS-330–TS-332)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import (
    TEST_PASSWORD,
    auth_headers_and_workspace,
    login,
    signup,
)

MODULES = "health,rulepacks,auth,ingestion,governance,export"


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _owner(client):
    headers, ws_id = auth_headers_and_workspace(client, "governance@x.com")
    return headers, ws_id


def _estimator_headers(client, owner_headers: dict, workspace_id: str):
    signup(client, "estimator@x.com", password=TEST_PASSWORD)
    client.post(
        f"/api/auth/workspaces/{workspace_id}/members",
        json={"email": "estimator@x.com", "role": "estimator"},
        headers=owner_headers,
    )
    tokens = login(client, "estimator@x.com", password=TEST_PASSWORD)
    switched = client.post(
        f"/api/auth/workspaces/{workspace_id}/switch",
        headers={"authorization": f"Bearer {tokens['access_token']}"},
    )
    assert switched.status_code == 200, switched.text
    return {"authorization": f"Bearer {switched.json()['access_token']}"}


def test_document_class_acl_blocks_unauthorized_upload_ts330(client):
    """TS-330: document-class ACL rejects uploads below the configured min role."""
    owner_headers, ws_id = _owner(client)
    estimator_headers = _estimator_headers(client, owner_headers, ws_id)

    opp = client.post(
        "/api/ingestion/opportunities",
        json={"title": "ACL OPP"},
        headers=owner_headers,
    )
    assert opp.status_code == 200, opp.text
    opp_id = opp.json()["id"]

    # Owner sets GCC documents to require admin.
    set_acl = client.post(
        "/api/auth/document-classes",
        json={"document_class": "gcc", "min_role": "admin"},
        headers=owner_headers,
    )
    assert set_acl.status_code == 200, set_acl.text

    denied = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": "General Conditions of Contract. Clause 1.",
        },
        headers=estimator_headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "document_class_forbidden"

    allowed = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "other.pdf", "sample_text": "Random notes."},
        headers=estimator_headers,
    )
    assert allowed.status_code == 200, allowed.text


def test_governance_settings_and_retention_candidates_ts332(client):
    """TS-332: data governance settings can be updated and retention listed."""
    owner_headers, ws_id = _owner(client)

    get = client.get(
        f"/api/governance/workspaces/{ws_id}/data-governance",
        headers=owner_headers,
    )
    assert get.status_code == 200, get.text

    put = client.put(
        f"/api/governance/workspaces/{ws_id}/data-governance",
        json={
            "data_region": "IN-MH",
            "retention_days": 365,
            "encryption_at_rest": "aes-256",
        },
        headers=owner_headers,
    )
    assert put.status_code == 200, put.text
    assert put.json()["data_region"] == "IN-MH"
    assert put.json()["retention_days"] == 365

    candidates = client.get(
        f"/api/governance/workspaces/{ws_id}/data-governance/retention-candidates",
        headers=owner_headers,
    )
    assert candidates.status_code == 200, candidates.text
    assert "candidates" in candidates.json()


def test_report_templates_crud_and_default_ts331(client):
    """TS-331: branded report templates are managed and a default can be set."""
    owner_headers, ws_id = _owner(client)

    created = client.post(
        "/api/export/templates",
        json={
            "name": "Branded Tender Pack",
            "report_title": "Bid Review",
            "primary_color": "#003366",
            "accent_color": "#cc0000",
            "watermark_text": "DRAFT",
            "footer_text": "Confidential",
        },
        headers=owner_headers,
    )
    assert created.status_code == 200, created.text
    template_id = created.json()["id"]

    listed = client.get("/api/export/templates", headers=owner_headers).json()
    assert any(t["id"] == template_id for t in listed["templates"])

    updated = client.put(
        f"/api/export/templates/{template_id}",
        json={"name": "Updated Pack"},
        headers=owner_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Pack"

    default = client.post(
        f"/api/export/templates/{template_id}/default",
        headers=owner_headers,
    )
    assert default.status_code == 200, default.text
    assert default.json()["is_default"] is True

    deleted = client.delete(
        f"/api/export/templates/{template_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200, deleted.text
