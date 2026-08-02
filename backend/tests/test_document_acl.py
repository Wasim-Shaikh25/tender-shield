"""Document-class ACL enforcement on read, export, and change paths (TS-338)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec
from tests.helpers import auth_headers_and_workspace, signup


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,drafting,"
                "export,baseline,change"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _owner(client):
    return auth_headers_and_workspace(client, "owner@acl.test", workspace_name="ACL")


def _member_headers(client, owner_headers, owner_workspace_id, email, role):
    data = signup(client, email)
    user_id = data["user_id"]
    keys = client.app.state.ctx.registry.require("auth.keys")
    token = sec.mint_access(
        keys,
        user_id=user_id,
        workspace_id=owner_workspace_id,
        role=role,
        email_verified=True,
        mobile_verified=True,
        ttl=timedelta(minutes=5),
    )
    r = client.post(
        f"/api/auth/workspaces/{owner_workspace_id}/members",
        json={"email": email, "role": role},
        headers=owner_headers,
    )
    assert r.status_code == 200, r.text
    return {"authorization": f"Bearer {token}"}


def _create_opp_and_boq(client, owner_headers):
    opp = client.post(
        "/api/ingestion/opportunities", json={"title": "ACL Test"}, headers=owner_headers
    )
    assert opp.status_code == 200
    opp_id = opp.json()["id"]
    doc = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "boq.pdf",
            "sample_text": "[p1]\nBILL OF QUANTITY\nItem 1",
        },
        headers=owner_headers,
    )
    assert doc.status_code == 200
    assert doc.json()["kind"] == "boq"
    return opp_id, doc.json()["id"]


def test_document_acl_blocks_ingestion_read(client):
    owner_headers, ws_id = _owner(client)
    opp_id, doc_id = _create_opp_and_boq(client, owner_headers)

    r = client.post(
        "/api/auth/document-classes",
        json={"document_class": "boq", "min_role": "admin"},
        headers=owner_headers,
    )
    assert r.status_code == 200

    est_headers = _member_headers(
        client, owner_headers, ws_id, "estimator@acl.test", "estimator"
    )
    paths = [
        f"/api/ingestion/documents/{doc_id}",
        f"/api/ingestion/documents/{doc_id}/text",
        f"/api/ingestion/opportunities/{opp_id}/documents/{doc_id}/addendum",
        f"/api/ingestion/opportunities/{opp_id}/documents/{doc_id}/glossary",
    ]
    for path in paths:
        r = client.get(path, headers=est_headers)
        assert r.status_code == 403, f"{path}: {r.text}"
        assert r.json()["detail"] == "document_class_forbidden"

    r = client.get(f"/api/ingestion/documents/{doc_id}", headers=owner_headers)
    assert r.status_code == 200

    r = client.delete("/api/auth/document-classes/boq", headers=owner_headers)
    assert r.status_code == 200
    r = client.get(f"/api/ingestion/documents/{doc_id}", headers=est_headers)
    assert r.status_code == 200


def _run_risk_and_accept(client, opp_id, owner_headers):
    r = client.post(f"/api/risk/opportunities/{opp_id}/run", headers=owner_headers)
    assert r.status_code == 200, r.text
    queue = client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=owner_headers
    ).json()
    for finding in queue["findings"]:
        r = client.post(
            f"/api/review/findings/{finding['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=owner_headers,
        )
        assert r.status_code == 200, r.text


def test_document_acl_blocks_export(client):
    owner_headers, ws_id = _owner(client)
    opp = client.post(
        "/api/ingestion/opportunities", json={"title": "ACL Export"}, headers=owner_headers
    )
    opp_id = opp.json()["id"]

    gcc = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
                "Clause 5 — Scope. Build a bridge."
            ),
        },
        headers=owner_headers,
    )
    assert gcc.status_code == 200

    _run_risk_and_accept(client, opp_id, owner_headers)

    boq = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "boq.pdf",
            "sample_text": "[p1]\nBILL OF QUANTITY\nItem 1",
        },
        headers=owner_headers,
    )
    assert boq.status_code == 200

    r = client.post(
        "/api/auth/document-classes",
        json={"document_class": "boq", "min_role": "admin"},
        headers=owner_headers,
    )
    assert r.status_code == 200

    est_headers = _member_headers(
        client, owner_headers, ws_id, "est2@acl.test", "estimator"
    )
    r = client.get(f"/api/export/opportunities/{opp_id}?format=xlsx", headers=est_headers)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "document_class_forbidden"

    r = client.get(f"/api/export/opportunities/{opp_id}?format=xlsx", headers=owner_headers)
    assert r.status_code == 200, r.text


def test_document_acl_blocks_baseline_diff(client):
    owner_headers, ws_id = _owner(client)
    opp = client.post(
        "/api/ingestion/opportunities",
        json={"title": "ACL Diff"},
        headers=owner_headers,
    )
    opp_id = opp.json()["id"]

    gcc = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
                "Clause 5 — Scope. Build a bridge."
            ),
        },
        headers=owner_headers,
    )
    assert gcc.status_code == 200

    _run_risk_and_accept(client, opp_id, owner_headers)

    r = client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender"},
        headers=owner_headers,
    )
    assert r.status_code == 200, r.text

    boq = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "boq.pdf",
            "sample_text": "[p1]\nBILL OF QUANTITY\nItem 1",
        },
        headers=owner_headers,
    )
    assert boq.status_code == 200
    boq_id = boq.json()["id"]

    r = client.post(
        "/api/auth/document-classes",
        json={"document_class": "boq", "min_role": "admin"},
        headers=owner_headers,
    )
    assert r.status_code == 200

    est_headers = _member_headers(
        client, owner_headers, ws_id, "est3@acl.test", "estimator"
    )
    r = client.post(
        f"/api/change/opportunities/{opp_id}/diff",
        json={"document_id": boq_id},
        headers=est_headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "document_class_forbidden"

    r = client.post(
        f"/api/change/opportunities/{opp_id}/diff",
        json={"document_id": boq_id},
        headers=owner_headers,
    )
    assert r.status_code == 200, r.text
