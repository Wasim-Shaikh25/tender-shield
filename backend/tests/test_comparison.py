"""Comparison: portfolio ranking across opportunities."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.comparison.models  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,drafting,comparison"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "cmp@x.com")


def _opp_with_bid_decision(client, headers, title, due_date_text):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": title}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "nit.pdf",
            "sample_text": (
                f"[p1]\nClause 5 — Scope. Build a bridge.\n"
                f"[p2]\nBid submission last date {due_date_text}.\n"
            ),
        },
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )
    client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "bid_decision"},
        headers=headers,
    )
    return opp_id


def test_comparison_ranks_opportunities(client):
    headers = _auth(client)
    future = (datetime.utcnow() + timedelta(days=25)).strftime("%d %B %Y")
    _opp_with_bid_decision(client, headers, "Bridge", future)

    # second opportunity without a bid decision
    opp2 = client.post(
        "/api/ingestion/opportunities", json={"title": "Road"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp2}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a road.\n"},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp2}/run", headers=headers)

    resp = client.get("/api/comparison/opportunities", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()["opportunities"]
    assert len(rows) == 2

    bridge = next(r for r in rows if r["title"] == "Bridge")
    road = next(r for r in rows if r["title"] == "Road")

    assert bridge["rank"] == 1
    assert bridge["bid_readiness_score"] is not None
    assert bridge["recommendation"] in {"proceed", "proceed_with_conditions", "do_not_proceed"}
    assert 20 <= bridge["days_to_submission"] <= 25
    assert road["rank"] == 2
    assert road["bid_readiness_score"] is None
