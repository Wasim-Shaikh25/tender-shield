"""Cross-reference search and clause change detection (TS-053 + TS-051)."""

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
            enabled_modules="health,rulepacks,auth,ingestion,crossref",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "cr@x.com")

def _opp_with_docs(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay the contractor "
                "within 30 days of the running account bill.\n"
                "[p2]\n"
                "Clause 2 - Scope. The contractor shall build a bridge.\n"
            ),
        },
        headers=headers,
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "scc.pdf",
            "sample_text": (
                "[p1]\nClause A - Payment terms. Interest at 12% per annum on delayed payments.\n"
            ),
        },
        headers=headers,
    )
    return opp_id


def test_cross_reference_search(client):
    headers = _auth(client)
    opp_id = _opp_with_docs(client, headers)

    resp = client.get(f"/api/crossref/opportunities/{opp_id}?q=payment&limit=10", headers=headers)
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 2
    texts = " ".join(r["text"].lower() for r in results)
    assert "payment" in texts


def test_contradiction_engine_flags_disagreement_and_names_governing_instance(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
                "Clause 1 - Validity. The bid shall remain valid for 90 days "
                "from the date of opening.\n"
            ),
        },
        headers=headers,
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "addendum1.pdf",
            "sample_text": (
                "[p1]\nADDENDUM No. 1\n"
                "Clause 1 - Validity extension. The bid shall remain valid for "
                "120 days from the date of opening.\n"
            ),
        },
        headers=headers,
    )

    resp = client.get(f"/api/crossref/opportunities/{opp_id}/contradictions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["precedence"] == ["addendum", "scc", "gcc", "nit"]
    found = [c for c in body["contradictions"] if c["fact_type"] == "bid_validity_days"]
    assert len(found) == 1
    c = found[0]
    assert {i["value"] for i in c["instances"]} == {90, 120}
    assert c["governing"]["value"] == 120
    assert c["governing"]["document_kind"] == "addendum"
    # both sides keep their own citation (Strategy §C.5)
    for instance in c["instances"]:
        assert instance["quote"]
        assert instance["page"] == 1


def test_contradiction_engine_no_findings_when_documents_agree(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Warehouse"}, headers=headers
    ).json()["id"]
    text = (
        "[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
        "Clause 1 - Validity. The bid shall remain valid for 90 days from the date of opening.\n"
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": text},
        headers=headers,
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc_copy.pdf", "sample_text": text},
        headers=headers,
    )

    resp = client.get(f"/api/crossref/opportunities/{opp_id}/contradictions", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contradictions"] == []


def test_contradiction_engine_degrades_without_rulepacks():
    app = create_app(
        Settings(
            enabled_modules="health,auth,ingestion,crossref",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    client = TestClient(app)
    headers = auth_headers(client, "nopack@x.com")
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    resp = client.get(f"/api/crossref/opportunities/{opp_id}/contradictions", headers=headers)
    assert resp.status_code == 200
    # rulepacks disabled → hardcoded DEFAULT_PRECEDENCE fallback, not a crash.
    assert resp.json()["precedence"] == ["addendum", "scc", "gcc", "nit"]


def test_change_detection_by_supersedes(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Road"}, headers=headers
    ).json()["id"]

    old = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay within 30 days.\n"
                "[p2]\n"
                "Clause 2 - Scope. Build a road.\n"
            ),
        },
        headers=headers,
    ).json()

    new = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc_v2.pdf",
            "supersedes": old["id"],
            "sample_text": (
                "[p1]\n"
                "Clause 1 - Payment. The employer shall pay within 45 days.\n"
                "[p2]\n"
                "Clause 3 - LD. Liquidated damages at 0.5% per week.\n"
            ),
        },
        headers=headers,
    ).json()

    diff = client.post(
        f"/api/crossref/opportunities/{opp_id}/diff?document_id={new['id']}",
        headers=headers,
    ).json()
    assert "added" in diff and "removed" in diff and "changed" in diff
    assert any("45 days" in c["new"]["text"] for c in diff["changed"])
    assert any(c.get("heading") and "Scope" in c["heading"] for c in diff["removed"])
