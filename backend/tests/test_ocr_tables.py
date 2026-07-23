"""PDF table extraction (pdfplumber, no cloud) + BOQ-from-PDF upload, and a real
offline OCR round-trip (skipped where the optional `ocr` extra isn't installed)."""

import io

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.ingestion.tables import boq_table_to_csv, extract_tables, find_boq_table


def _boq_pdf() -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    rows = [
        ["S.No", "Description", "Unit", "Qty", "Rate", "Amount"],
        ["1", "Earthwork in excavation", "Cum", "1200", "250", "300000"],
        ["2", "Earthwork in excavation", "Cum", "1200", "250", "300000"],  # duplicate
        ["3", "Brick masonry in CM 1:6", "Cum", "220", "5200", "1140000"],  # 220*5200=1,144,000
    ]
    table = Table(rows)
    # Grid lines give pdfplumber the rulings it needs to detect the table.
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4).build([table])
    return buf.getvalue()


# ---- table extraction (pure) ----------------------------------------------


def test_extract_and_map_boq_table():
    tables = extract_tables(_boq_pdf())
    boq = find_boq_table(tables)
    assert boq is not None
    csv_text = boq_table_to_csv(boq)
    header = csv_text.splitlines()[0]
    assert header.startswith("src_row,description,unit_raw,qty,rate,amount")


# ---- BOQ-from-PDF upload (integration) ------------------------------------


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,boq",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "o@x.com", "password": "hunter2hunter2", "org_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "o@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def test_boq_pdf_upload_runs_checks(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    files = {"file": ("boq.pdf", _boq_pdf(), "application/pdf")}
    r = client.post(
        f"/api/boq/opportunities/{opp_id}/upload", files=files, headers=headers
    )
    assert r.status_code == 200, r.text
    cats = {f["category"] for f in r.json()["findings"]}
    assert "duplicate" in cats and "arith" in cats  # read straight out of the PDF table


# ---- real offline OCR round-trip ------------------------------------------


def test_ocr_reads_scanned_pdf():
    pytest.importorskip("rapidocr_onnxruntime")
    fitz = pytest.importorskip("fitz")
    # Build an IMAGE-ONLY PDF (no text layer) — a stand-in for a scan.
    from reportlab.pdfgen import canvas

    from app.modules.ingestion.extract import extract_upload
    from app.modules.ingestion.ocr import RapidOcrProvider

    tbuf = io.BytesIO()
    c = canvas.Canvas(tbuf)
    c.setFont("Helvetica", 26)
    c.drawString(72, 760, "LIQUIDATED DAMAGES 1 PERCENT PER WEEK")
    c.save()
    src = fitz.open(stream=tbuf.getvalue(), filetype="pdf")
    pix = src[0].get_pixmap(dpi=150)
    out = fitz.open()
    page = out.new_page(width=pix.width, height=pix.height)
    page.insert_image(page.rect, pixmap=pix)
    image_pdf = out.tobytes()

    # Without OCR → flagged needs_ocr (honest degradation).
    _, status_off = extract_upload("scan.pdf", image_pdf, None)
    assert status_off == "needs_ocr"

    # With OCR → text recovered.
    text, status_on = extract_upload("scan.pdf", image_pdf, RapidOcrProvider())
    assert status_on == "ocr_applied"
    assert "LIQUIDATED DAMAGES" in text.upper()
