"""Ingestion: pure classifier unit tests + full-stack integration (auth-gated,
org-scoped) through the app."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401 — register auth tables
import app.modules.ingestion.models  # noqa: F401 — register ingestion tables
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.ingestion.classify import classify_text, missing_documents

# ---- pure unit tests (no DB, no FastAPI) ---------------------------------

ANCHORS = {
    "nit": [r"NOTICE\s+INVITING\s+TENDER", r"\bNIT\s*No"],
    "gcc": [r"GENERAL\s+CONDITIONS\s+OF\s+CONTRACT"],
    "boq": [r"BILL\s+OF\s+QUANTIT"],
}


def test_classify_matches_anchor():
    assert classify_text("...NOTICE INVITING TENDER No. 42...", ANCHORS) == "nit"
    assert classify_text("General Conditions of Contract, 2019", ANCHORS) == "gcc"
    assert classify_text("random letterhead", ANCHORS) is None


def test_missing_documents():
    assert missing_documents(["nit", "boq"], ["nit", "gcc", "boq"]) == ["gcc"]
    assert missing_documents(["nit", "gcc", "boq"], ["nit", "gcc", "boq"]) == []


# ---- integration ----------------------------------------------------------


@pytest.fixture
def app_client():
    application = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return application


def _owner_token(client: TestClient, email="e@example.com") -> str:
    from tests.helpers import ensure_workspace, login, signup

    signup(client, email)
    tokens = login(client, email)
    tokens, _ = ensure_workspace(client, tokens)
    return tokens["access_token"]


def test_opportunity_and_document_flow(app_client):
    client = TestClient(app_client)
    auth = {"authorization": f"Bearer {_owner_token(client)}"}

    opp = client.post("/api/ingestion/opportunities", json={"title": "Metro Depot"}, headers=auth)
    assert opp.status_code == 200, opp.text
    opp_id = opp.json()["id"]

    # rules-first classification uses the in-works pack anchors
    d1 = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.pdf", "sample_text": "NOTICE INVITING TENDER No. 7"},
        headers=auth,
    )
    assert d1.json()["kind"] == "nit"

    # missing-doc checklist flags absent gcc + boq (expected set from the pack)
    report = client.get(f"/api/ingestion/opportunities/{opp_id}/missing-docs", headers=auth).json()
    assert report["present"] == ["nit"]
    assert set(report["missing"]) == {"gcc", "boq"}


def test_list_opportunities_scoped_to_org(app_client):
    client = TestClient(app_client)
    a = {"authorization": f"Bearer {_owner_token(client, 'la@x.com')}"}
    b = {"authorization": f"Bearer {_owner_token(client, 'lb@x.com')}"}
    client.post("/api/ingestion/opportunities", json={"title": "A1"}, headers=a)
    client.post("/api/ingestion/opportunities", json={"title": "A2"}, headers=a)
    client.post("/api/ingestion/opportunities", json={"title": "B1"}, headers=b)
    list_a = client.get("/api/ingestion/opportunities", headers=a).json()["opportunities"]
    list_b = client.get("/api/ingestion/opportunities", headers=b).json()["opportunities"]
    assert {o["title"] for o in list_a} == {"A1", "A2"}
    assert {o["title"] for o in list_b} == {"B1"}


def test_requires_auth(app_client):
    client = TestClient(app_client)
    # no token → protected route rejects
    assert client.post("/api/ingestion/opportunities", json={"title": "x"}).status_code == 401


def test_org_isolation(app_client):
    client = TestClient(app_client)
    a = {"authorization": f"Bearer {_owner_token(client, 'a@x.com')}"}
    b = {"authorization": f"Bearer {_owner_token(client, 'b@x.com')}"}
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "A secret bid"}, headers=a
    ).json()["id"]
    # org B must not see org A's opportunity (explicit workspace_id scoping)
    assert client.get(f"/api/ingestion/opportunities/{opp_id}", headers=b).status_code == 404
    assert client.get(f"/api/ingestion/opportunities/{opp_id}", headers=a).status_code == 200


def test_soft_dep_absent_uses_fallback_anchors():
    # ingestion enabled WITHOUT rulepacks → falls back to built-in anchors
    application = create_app(
        Settings(enabled_modules="health,auth,ingestion", database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    client = TestClient(application)
    auth = {"authorization": f"Bearer {_owner_token(client)}"}
    opp_id = client.post("/api/ingestion/opportunities", json={"title": "t"}, headers=auth).json()[
        "id"
    ]
    d = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "b.xlsx", "sample_text": "BILL OF QUANTITIES"},
        headers=auth,
    )
    assert d.json()["kind"] == "boq"


def test_confirm_deadline_rejects_foreign_opportunity(app_client):
    client = TestClient(app_client)
    auth = {"authorization": f"Bearer {_owner_token(client, 'dl@x.com')}"}

    opp_a = client.post("/api/ingestion/opportunities", json={"title": "A"}, headers=auth).json()[
        "id"
    ]
    opp_b = client.post("/api/ingestion/opportunities", json={"title": "B"}, headers=auth).json()[
        "id"
    ]

    doc_a = client.post(
        f"/api/ingestion/opportunities/{opp_a}/documents",
        json={
            "filename": "nit.pdf",
            "sample_text": "Last date of submission: 25/12/2026.",
        },
        headers=auth,
    ).json()
    # Process document synchronously for this test.
    client.post(f"/api/ingestion/documents/{doc_a['id']}/process", headers=auth)
    dl_a = client.get(f"/api/ingestion/opportunities/{opp_a}/deadlines", headers=auth).json()[
        "deadlines"
    ][0]

    # Confirming a deadline under a different opportunity must 404.
    resp = client.post(
        f"/api/ingestion/opportunities/{opp_b}/deadlines/{dl_a['id']}/confirm",
        headers=auth,
    )
    assert resp.status_code == 404


def test_doc_chunks_stored_on_register_and_can_be_read_back(app_client):
    client = TestClient(app_client)
    auth = {"authorization": f"Bearer {_owner_token(client, 'chunk@x.com')}"}
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Chunky"}, headers=auth
    ).json()["id"]
    doc_id = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "two.pdf",
            "sample_text": "[p1]\nPage one line.\n[p2]\nPage two line.",
        },
        headers=auth,
    ).json()["id"]

    all_pages = client.get(f"/api/ingestion/documents/{doc_id}/text", headers=auth).json()
    assert "1" in all_pages["pages"]
    assert "2" in all_pages["pages"]
    assert "Page one line." in all_pages["pages"]["1"]

    p2 = client.get(f"/api/ingestion/documents/{doc_id}/text?page=2", headers=auth).json()
    assert p2["page"] == 2
    assert "Page two line." in p2["text"]
