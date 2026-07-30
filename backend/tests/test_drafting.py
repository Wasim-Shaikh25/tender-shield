"""Drafting: the three validators (pure) + generate-from-accepted-findings flow
with version bump and the no-accepted-findings guard."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.drafting.validators import DraftError, FactTable, validate
from tests.helpers import auth_headers

# ---- the spine: three validators (pure) -----------------------------------

FINDINGS = [
    {
        "source_quote": "no escalation shall be payable",
        "detail": "Firm price on a 30-month work. See Clause 14.",
        "amount_exposure": 25000000,
    }
]


def test_validate_passes_grounded_prose():
    facts = FactTable.from_findings(FINDINGS)
    ok = 'We note "no escalation shall be payable" (Clause 14); exposure ₹250,000.00.'
    assert validate(ok, facts) == ok


def test_invented_quote_rejected():
    facts = FactTable.from_findings(FINDINGS)
    with pytest.raises(DraftError) as e:
        validate('The employer said "we will pay all escalation without limit".', facts)
    assert e.value.code == "invented_quote"


def test_uncited_clause_rejected():
    facts = FactTable.from_findings(FINDINGS)
    with pytest.raises(DraftError) as e:
        validate("Please confirm the position under Clause 99.", facts)
    assert e.value.code == "uncited_clause"


def test_invented_number_rejected():
    facts = FactTable.from_findings(FINDINGS)
    with pytest.raises(DraftError) as e:
        validate("The exposure is ₹9,999,999.00 in our estimate.", facts)
    assert e.value.code == "invented_number"


# ---- integration ----------------------------------------------------------


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,review,drafting",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "dr@x.com")


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a bridge."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def test_generate_requires_accepted_findings(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    # nothing accepted yet → 409
    r = client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "clarification_letter"},
        headers=headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "no_accepted_findings"


def test_generate_bid_decision(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )

    resp = client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "bid_decision"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()["body"]
    assert body["kind"] == "bid_decision"
    assert 0 <= body["score"] <= 100
    assert body["recommendation"] in {"proceed", "proceed_with_conditions", "do_not_proceed"}
    assert "strengths" in body
    assert "concerns" in body
    assert "conditions" in body


def test_generate_after_accept_and_version_bump(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    # accept every finding
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )

    a1 = client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "clarification_letter"},
        headers=headers,
    ).json()
    assert a1["version"] == 1
    assert a1["body"]["kind"] == "clarification_letter"
    assert len(a1["body"]["items"]) >= 1

    a2 = client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "clarification_letter"},
        headers=headers,
    ).json()
    assert a2["version"] == 2  # regeneration is a new version, never a mutation

    listed = client.get(f"/api/drafting/opportunities/{opp_id}/artifacts", headers=headers).json()[
        "artifacts"
    ]
    assert len(listed) == 2
