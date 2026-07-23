"""Deadline extraction: pure parser unit tests + integration proving the board
countdown (submission_due) lights up from an uploaded NIT."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.ingestion.deadlines import extract_deadlines, parse_date

# ---- pure unit tests ------------------------------------------------------


def test_parse_date_formats():
    assert parse_date("25/07/2026") == datetime(2026, 7, 25)
    assert parse_date("25-07-2026") == datetime(2026, 7, 25)
    assert parse_date("15 August 2026") == datetime(2026, 8, 15)
    assert parse_date("15 Aug 2026") == datetime(2026, 8, 15)
    assert parse_date("not a date") is None


def test_extract_deadlines_classifies_by_keyword():
    text = (
        "[p1]\n"
        "Last date of submission of bid: 25/07/2026 up to 15:00 hrs.\n"
        "Pre-bid meeting shall be held on 20/07/2026.\n"
        "Last date for clarifications: 18/07/2026.\n"
        "Some unrelated line with a date 01/01/2026 and no keyword.\n"
    )
    got = {d.kind: d for d in extract_deadlines(text)}
    assert set(got) == {"submission", "prebid_meeting", "clarification"}
    assert got["submission"].due_at == datetime(2026, 7, 25)
    assert got["submission"].source_page == 1
    assert "25/07/2026" in got["submission"].source_quote


def test_extract_skips_lines_without_keywords():
    # a bare date with no deadline keyword is not emitted (noise control)
    assert extract_deadlines("[p1]\nInvoice number 12/06/2026 for records.") == []


# ---- integration ----------------------------------------------------------


@pytest.fixture
def client():
    app = create_app(
        Settings(enabled_modules="health,rulepacks,auth,ingestion", database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "d@x.com", "password": "hunter2hunter2", "org_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "d@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def test_upload_extracts_deadlines_and_sets_submission_due(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]

    nit = (
        "[p1]\nNOTICE INVITING TENDER No. 7\n"
        "Last date of submission of bid: 25/08/2026.\n"
        "Pre-bid meeting on 05/08/2026.\n"
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.pdf", "sample_text": nit},
        headers=headers,
    )

    deadlines = client.get(
        f"/api/ingestion/opportunities/{opp_id}/deadlines", headers=headers
    ).json()["deadlines"]
    kinds = {d["kind"] for d in deadlines}
    assert {"submission", "prebid_meeting"} <= kinds

    # submission_due now populated → the board countdown lights up
    opp = client.get(f"/api/ingestion/opportunities/{opp_id}", headers=headers).json()
    assert opp["submission_due"].startswith("2026-08-25")

    # confirm chip flips the flag
    sub = next(d for d in deadlines if d["kind"] == "submission")
    assert sub["confirmed"] is False
    confirmed = client.post(
        f"/api/ingestion/opportunities/{opp_id}/deadlines/{sub['id']}/confirm", headers=headers
    ).json()
    assert confirmed["confirmed"] is True
