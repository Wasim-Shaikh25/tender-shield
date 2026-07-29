"""Timeline module: milestone calendar over ingestion deadlines."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,timeline",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "t@x.com", "password": "Hunter2!Hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "t@x.com", "password": "Hunter2!Hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


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


def test_timeline_returns_canonical_milestones(client):
    headers = _auth(client)
    text = (
        "[p1] Tender published on 01/07/2026.\n"
        "[p2] Pre-bid meeting: 10/07/2026.\n"
        "[p3] Last date of submission of bid: 25/07/2026 up to 15:00 hrs.\n"
        "[p4] Technical opening: 26/07/2026.\n"
        "[p5] Financial opening: 27/07/2026.\n"
        "[p6] Clarification deadline: 15/07/2026.\n"
        "[p7] EMD validity: 30/09/2026.\n"
        "[p8] Performance guarantee submission: 05/08/2026.\n"
        "[p9] Contract signing: 10/08/2026.\n"
    )
    opp_id = _opp_with_text(client, headers, text)

    resp = client.get(f"/api/timeline/opportunities/{opp_id}/timeline", headers=headers)
    assert resp.status_code == 200
    events = resp.json()["events"]
    kinds = {e["kind"] for e in events}
    required = {
        "tender_published",
        "pre_bid_meeting",
        "clarification_cutoff",
        "bid_submission",
        "technical_opening",
        "financial_opening",
        "emd_validity",
        "bg_submission",
        "contract_signing",
    }
    assert required <= kinds, f"missing {required - kinds}"

    # order: tender published, pre-bid, clarification, submission, technical, financial,
    # EMD validity, BG, contract signing
    dated = [e for e in events if e["due_at"]]
    labels = [e["kind"] for e in dated]
    assert labels.index("tender_published") < labels.index("pre_bid_meeting")
    assert labels.index("pre_bid_meeting") < labels.index("clarification_cutoff")
    assert labels.index("clarification_cutoff") < labels.index("bid_submission")


def test_timeline_ics_export(client):
    headers = _auth(client)
    text = "[p1] Last date of submission of bid: 25/07/2026 up to 15:00 hrs.\n"
    opp_id = _opp_with_text(client, headers, text)

    resp = client.get(f"/api/timeline/opportunities/{opp_id}/timeline.ics", headers=headers)
    assert resp.status_code == 200
    body = resp.text
    assert "BEGIN:VCALENDAR" in body
    assert "BEGIN:VEVENT" in body
    assert "SUMMARY:Bid submission" in body
    assert "END:VCALENDAR" in body
