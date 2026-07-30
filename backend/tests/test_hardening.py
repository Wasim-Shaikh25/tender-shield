"""Production-hardening features that run without live creds: GST computation,
deadline digest, MFA primitives, PDF export, and real file upload + extraction."""

import asyncio
import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.drafting.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.core.storage import ValidationError, VirusScanError, validate_and_store
from app.main import create_app
from app.modules.auth import mfa
from app.modules.billing.gst import compute_invoice, invoice_number
from app.modules.ingestion.extract import extract_text, looks_like_boq_csv
from app.modules.notifications.digest import deadlines_to_alert, format_digest
from tests.helpers import auth_headers

# ---- GST (pure) -----------------------------------------------------------


def test_gst_intra_vs_inter_state():
    # seller in state 27; buyer in 27 → CGST+SGST
    intra = compute_invoice(
        number="TS/1", base_minor=750000, buyer_gstin="27ABCDE1234F1Z5", seller_state_code="27"
    )
    assert [line.name for line in intra.lines] == ["CGST", "SGST"]
    assert intra.total_minor == 750000 + 67500 + 67500  # 9% + 9%
    # buyer in 29 → IGST
    inter = compute_invoice(
        number="TS/2", base_minor=750000, buyer_gstin="29ABCDE1234F1Z5", seller_state_code="27"
    )
    assert [line.name for line in inter.lines] == ["IGST"]
    assert inter.total_minor == 750000 + 135000  # 18%


def test_invoice_number_sequential_gapless():
    assert invoice_number(42) == "TS/2026-27/000042"


# ---- deadline digest (pure) ----------------------------------------------


def test_digest_alerts_within_windows():
    now = datetime(2026, 7, 23)
    deadlines = [
        {"kind": "submission", "due_at": datetime(2026, 7, 24)},  # 1 day → alert
        {"kind": "prebid_meeting", "due_at": datetime(2026, 7, 30)},  # 7 days → alert
        {"kind": "validity", "due_at": datetime(2026, 8, 15)},  # 23 days → no
        {"kind": "other", "due_at": None},  # unparsed → skipped
    ]
    alerts = deadlines_to_alert(deadlines, now)
    kinds = {a["kind"] for a in alerts}
    assert kinds == {"submission", "prebid_meeting"}
    assert "TODAY" not in format_digest("Metro", alerts)


# ---- MFA (pure) -----------------------------------------------------------


def test_mfa_enroll_and_verify():
    secret = mfa.new_secret()
    import pyotp

    code = pyotp.TOTP(secret).now()
    assert mfa.verify(secret, code)
    assert not mfa.verify(secret, "000000")
    assert "otpauth://" in mfa.provisioning_uri(secret, "a@x.com")


# ---- extraction (pure) ----------------------------------------------------


def test_extract_csv_and_boq_detection():
    csv = b"src_row,description,unit_raw,qty,rate,amount\n1,Excavation,cum,10,20,200\n"
    text = extract_text("boq.csv", csv)
    assert "Excavation" in text
    assert "[p2]" in text
    assert looks_like_boq_csv("boq.csv", csv)
    assert not looks_like_boq_csv("notes.txt", csv)


# ---- virus scan (no live clamd) -------------------------------------------


def test_virus_detected_is_quarantined_and_rejected(tmp_path, monkeypatch):
    def _fake_scan(socket_path, data):
        raise VirusScanError("Eicar-Test-Signature FOUND")

    monkeypatch.setattr("app.core.storage._clamd_scan", _fake_scan)
    qdir = tmp_path / "quarantine"
    settings = Settings(
        storage_type="local",
        storage_dir=str(tmp_path / "store"),
        clamd_socket="/tmp/clamd.ctl",
        quarantine_dir=str(qdir),
    )
    # File extension must be in the allow-list and must not fail magic checks.
    data = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    with pytest.raises(ValidationError):
        asyncio.run(validate_and_store(settings, "test.csv", "text/csv", data))
    assert list(qdir.iterdir())


# ---- integration: upload + PDF export ------------------------------------


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,drafting,export"
            ),
            database_url="sqlite:///:memory:",
            storage_dir=str(tmp_path / "storage"),
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "h@x.com")


def _make_pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 800, "NOTICE INVITING TENDER No. 7")
    c.drawString(72, 780, "Last date of submission of bid: 25/08/2026.")
    c.drawString(72, 760, "Clause 5 - Scope. Build a depot.")
    c.save()
    return buf.getvalue()


def test_real_pdf_upload_runs_pipeline(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    files = {"file": ("nit.pdf", _make_pdf(), "application/pdf")}
    up = client.post(f"/api/ingestion/opportunities/{opp_id}/upload", files=files, headers=headers)
    assert up.status_code == 200, up.text
    assert up.json()["kind"] == "nit"  # classified from extracted text
    # deadline extracted from the real PDF's text
    dls = client.get(f"/api/ingestion/opportunities/{opp_id}/deadlines", headers=headers).json()[
        "deadlines"
    ]
    assert any(d["kind"] == "submission" for d in dls)


def test_pdf_export_after_review(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a depot."},
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
    pdf = client.get(f"/api/export/opportunities/{opp_id}?format=pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"
