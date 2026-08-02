"""Ingestion Phase 22 gap-closure tests (TS-310–TS-316)."""

from __future__ import annotations

import io
import zipfile

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion"


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "ingestion22@x.com")


def _opp(client, headers):
    r = client.post(
        "/api/ingestion/opportunities", json={"title": "Phase 22"}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _docx_bytes(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()


def _png_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color="white")
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return bio.getvalue()


def test_docx_upload_extracts_text_ts310(client):
    """TS-310: DOCX files are accepted and their text is extracted."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    data = _docx_bytes("General Conditions of Contract. This is a sample DOCX.")
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    r = client.post(
        f"/api/ingestion/opportunities/{opp_id}/upload",
        files={"file": ("conditions.docx", data, content_type)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "gcc"
    assert body["chars"] > 0
    assert body["ocr_status"] == "done"

    doc = client.get(f"/api/ingestion/documents/{body['id']}", headers=headers).json()
    assert doc["language"] == "en"


def test_image_upload_degrades_to_ocr_pending_ts311(client):
    """TS-311: standalone PNG uploads are stored and flagged for OCR."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    data = _png_bytes()
    r = client.post(
        f"/api/ingestion/opportunities/{opp_id}/upload",
        files={"file": ("drawing.png", data, "image/png")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "other"
    assert body["chars"] == 0
    assert body["ocr_status"] == "needs_ocr"


def test_zip_bulk_upload_extracts_package_ts312(client):
    """TS-312: ZIP uploads produce a combined text payload with file markers."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    files = {
        "notes.txt": b"Retention money is 10%.",
        "conditions.docx": _docx_bytes("General Conditions of Contract. Payment terms 30 days."),
    }
    data = _zip_bytes(files)
    r = client.post(
        f"/api/ingestion/opportunities/{opp_id}/upload",
        files={"file": ("package.zip", data, "application/zip")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chars"] > 0
    text_resp = client.get(
        f"/api/ingestion/documents/{body['id']}/text", headers=headers
    ).json()
    combined = "\n".join(text_resp["pages"].values())
    assert "[file:" in combined


def test_duplicate_document_flagged_ts314(client):
    """TS-314: re-uploading identical text marks the document as a duplicate."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    payload = {"filename": "gcc.pdf", "sample_text": "General Conditions of Contract."}
    first = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents", json=payload, headers=headers
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents", json=payload, headers=headers
    )
    assert second.status_code == 200, second.text
    doc_id = second.json()["id"]
    doc = client.get(f"/api/ingestion/documents/{doc_id}", headers=headers).json()
    assert doc["meta"]["duplicate_of"] == first.json()["id"]
    assert doc["ocr_status"] == "duplicate"


def test_addendum_links_supersedes_and_diff_ts314(client):
    """TS-314: addendum documents link to the base doc and store clause diffs."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    base = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "conditions.pdf",
            "sample_text": "[p1]\nClause 1 — Original payment terms.\n",
        },
        headers=headers,
    )
    assert base.status_code == 200, base.text
    base_id = base.json()["id"]

    add = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "conditions_addendum.pdf",
            "sample_text": "[p1]\nClause 1 — Revised payment terms.\n",
        },
        headers=headers,
    )
    assert add.status_code == 200, add.text
    add_id = add.json()["id"]

    doc = client.get(f"/api/ingestion/documents/{add_id}", headers=headers).json()
    assert doc["supersedes"] == base_id
    assert doc["meta"]["addendum"] is True

    addendum = client.get(
        f"/api/ingestion/opportunities/{opp_id}/documents/{add_id}/addendum",
        headers=headers,
    )
    assert addendum.status_code == 200, addendum.text
    changes = addendum.json()["addendum_changes"]
    assert any(c["clause_ref"] == "1" and c["status"] == "modified" for c in changes)


def test_hindi_document_language_detected_ts315(client):
    """TS-315: non-Latin script text sets the document language metadata."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    r = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "notice_hi.pdf",
            "sample_text": "यह निविदा दस्तावेज़ है।",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    doc = client.get(f"/api/ingestion/documents/{r.json()['id']}", headers=headers).json()
    assert doc["language"] == "hi"


def test_defined_term_glossary_extracted_ts316(client):
    """TS-316: 'X means Y' definitions are extracted into the glossary."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    r = client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "definitions.pdf",
            "sample_text": '"Contractor" means the successful bidder.\n"Employer" means the owner.',
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    glossary = client.get(
        f"/api/ingestion/opportunities/{opp_id}/glossary", headers=headers
    )
    assert glossary.status_code == 200, glossary.text
    terms = {t["term"] for t in glossary.json()["terms"]}
    assert "Contractor" in terms
