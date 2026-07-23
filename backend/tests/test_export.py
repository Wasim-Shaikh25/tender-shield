"""Export: the gate blocks export until review completes, then produces a valid
XLSX + DOCX Bid Review Pack carrying the review/pack stamp."""

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,drafting,export"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "x@x.com", "password": "hunter2hunter2", "org_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "x@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _opp_reviewed(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a depot."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def test_export_blocked_until_review_complete(client):
    headers = _auth(client)
    opp_id = _opp_reviewed(client, headers)
    # findings exist but none reviewed → gate closed → 403
    r = client.get(f"/api/export/opportunities/{opp_id}?format=xlsx", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "review_incomplete"


def test_export_xlsx_and_docx_after_review(client):
    headers = _auth(client)
    opp_id = _opp_reviewed(client, headers)
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}", json={"decision": "accepted"}, headers=headers
        )

    xlsx = client.get(f"/api/export/opportunities/{opp_id}?format=xlsx", headers=headers)
    assert xlsx.status_code == 200
    assert "spreadsheetml" in xlsx.headers["content-type"]
    wb = load_workbook(io.BytesIO(xlsx.content))
    cells = [c.value for row in wb.active.iter_rows() for c in row if c.value]
    assert any("Bid Review Pack" in str(v) for v in cells)
    assert any("Prepared with TenderShield" in str(v) for v in cells)  # the stamp

    docx = client.get(f"/api/export/opportunities/{opp_id}?format=docx", headers=headers)
    assert docx.status_code == 200
    assert "wordprocessingml" in docx.headers["content-type"]
    assert len(docx.content) > 500  # a real .docx zip
