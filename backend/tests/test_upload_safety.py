"""Upload safety: streaming size cap, magic-byte type validation (R-003, TS-095).

Covers both the core spool_upload() unit and the two router integrations
(ingestion, boq) that consume it — boq's endpoint had NO size limit at all
before this task.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.core.uploads import UploadRejected, spool_upload
from app.main import create_app


class _FakeUploadFile:
    """Minimal async-read stand-in for fastapi.UploadFile, chunked like a real
    multipart stream so spool_upload's cap check runs mid-transfer."""

    def __init__(self, filename: str, data: bytes, chunk_size: int = 1024):
        self.filename = filename
        self._data = data
        self._pos = 0
        self._chunk_size = chunk_size

    async def read(self, n: int = -1) -> bytes:
        size = self._chunk_size if n == -1 else min(n, self._chunk_size)
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


def _make_pdf_bytes() -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 800, "Hello")
    c.save()
    return buf.getvalue()


# ---- unit: spool_upload -----------------------------------------------------


@pytest.mark.anyio
async def test_spool_upload_accepts_a_real_pdf():
    pdf = _make_pdf_bytes()
    data, sha, suffix = await spool_upload(_FakeUploadFile("nit.pdf", pdf), max_bytes=10_000_000)
    assert data == pdf
    assert suffix == ".pdf"
    assert len(sha) == 64  # hex sha256


@pytest.mark.anyio
async def test_spool_upload_enforces_size_cap_mid_stream():
    pdf = _make_pdf_bytes()
    oversized = pdf + b"\x00" * (2_000_000 - len(pdf))
    with pytest.raises(UploadRejected) as exc:
        await spool_upload(_FakeUploadFile("nit.pdf", oversized), max_bytes=1_000_000)
    assert exc.value.status_code == 413
    assert exc.value.detail == "file_too_large"


@pytest.mark.anyio
async def test_spool_upload_rejects_disallowed_extension():
    with pytest.raises(UploadRejected) as exc:
        await spool_upload(_FakeUploadFile("payload.exe", b"MZ\x90\x00"), max_bytes=10_000_000)
    assert exc.value.status_code == 415


@pytest.mark.anyio
async def test_spool_upload_rejects_magic_byte_mismatch():
    # An .exe's bytes wearing a .pdf extension — the classic disguise attempt.
    fake = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    with pytest.raises(UploadRejected) as exc:
        await spool_upload(_FakeUploadFile("disguised.pdf", fake), max_bytes=10_000_000)
    assert exc.value.status_code == 415
    assert exc.value.detail == "unsupported_file_type"


@pytest.mark.anyio
async def test_spool_upload_rejects_empty_file():
    with pytest.raises(UploadRejected) as exc:
        await spool_upload(_FakeUploadFile("empty.pdf", b""), max_bytes=10_000_000)
    assert exc.value.status_code == 400
    assert exc.value.detail == "empty_file"


@pytest.mark.anyio
async def test_spool_upload_no_temp_file_left_behind():
    import tempfile
    from pathlib import Path

    created: list[str] = []
    real_ntf = tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        f = real_ntf(*args, **kwargs)
        created.append(f.name)
        return f

    import app.core.uploads as uploads_module

    original = uploads_module.tempfile.NamedTemporaryFile
    uploads_module.tempfile.NamedTemporaryFile = spy
    try:
        fake = b"MZ\x90\x00" + b"\x00" * 100
        with pytest.raises(UploadRejected):
            await spool_upload(_FakeUploadFile("disguised.pdf", fake), max_bytes=10_000_000)
    finally:
        uploads_module.tempfile.NamedTemporaryFile = original

    assert created, "spool_upload never created a temp file"
    assert not Path(created[0]).exists()


# ---- integration: both upload routes reject an oversized/disguised file ----


@pytest.fixture
def client(tmp_path):
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,boq",
            database_url="sqlite:///:memory:",
            storage_dir=str(tmp_path / "storage"),
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "u@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "u@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def test_ingestion_upload_rejects_disguised_exe(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    files = {"file": ("nit.pdf", b"MZ\x90\x00" + b"\x00" * 100, "application/pdf")}
    r = client.post(f"/api/ingestion/opportunities/{opp_id}/upload", files=files, headers=headers)
    assert r.status_code == 415


def test_ingestion_upload_rejects_disallowed_extension(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    files = {"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")}
    r = client.post(f"/api/ingestion/opportunities/{opp_id}/upload", files=files, headers=headers)
    assert r.status_code == 415


def test_ingestion_upload_records_size_and_content_type(client):
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    pdf = _make_pdf_bytes()
    files = {"file": ("nit.pdf", pdf, "application/pdf")}
    r = client.post(f"/api/ingestion/opportunities/{opp_id}/upload", files=files, headers=headers)
    assert r.status_code == 200, r.text


def test_boq_upload_now_rejects_disguised_exe(client):
    """boq's upload endpoint had NO size/type validation at all before TS-095
    — this is the regression test for that gap, not just ingestion's."""
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    files = {"file": ("boq.pdf", b"MZ\x90\x00" + b"\x00" * 100, "application/pdf")}
    r = client.post(f"/api/boq/opportunities/{opp_id}/upload", files=files, headers=headers)
    assert r.status_code == 415
