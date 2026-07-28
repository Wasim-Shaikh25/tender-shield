"""Upload safety: stream to disk with a size cap enforced mid-stream, and
validate file type by magic bytes rather than trusting the client's claimed
filename/content-type (R-003 §B.1–B.2, TS-095).

Core infrastructure, not owned by any one module — both `ingestion` and `boq`
accept file uploads and must not import each other (CLAUDE.md §2), so this is
the shared, module-boundary-respecting home for the logic.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile

CHUNK_SIZE = 1024 * 1024  # 1 MiB

ALLOWED_SUFFIXES = frozenset({".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt"})

# Signature bytes -> canonical extension. .docx/.xlsx are ZIP containers and
# share PK\x03\x04 with plain .zip, so they can't be told apart by magic bytes
# alone; the declared suffix decides between them (both land in
# ALLOWED_SUFFIXES, so this only matters for the mismatch check below).
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", ".pdf"),
    (b"PK\x03\x04", ".zip"),  # also matches .docx / .xlsx
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", ".doc"),  # OLE2: legacy .doc / .xls
)
_ZIP_CONTAINER_SUFFIXES = frozenset({".docx", ".xlsx"})
_OLE2_CONTAINER_SUFFIXES = frozenset({".doc", ".xls"})
_TEXT_SUFFIXES = frozenset({".csv", ".txt"})  # no magic-byte signature


class UploadRejected(HTTPException):
    def __init__(self, status_code: int, code: str):
        super().__init__(status_code, code)


def _sniff(head: bytes, declared_suffix: str) -> None:
    """Reject a body whose magic bytes disagree with its declared extension in
    a way that matters. Plain text formats have no signature and are trusted
    by extension alone once the caller has already checked ALLOWED_SUFFIXES.
    """
    if declared_suffix in _TEXT_SUFFIXES:
        return
    for magic, sniffed in _MAGIC:
        if head.startswith(magic):
            if sniffed == ".pdf" and declared_suffix == ".pdf":
                return
            if sniffed == ".zip" and declared_suffix in _ZIP_CONTAINER_SUFFIXES:
                return
            if sniffed == ".doc" and declared_suffix in _OLE2_CONTAINER_SUFFIXES:
                return
            raise UploadRejected(415, "unsupported_file_type")
    raise UploadRejected(415, "unsupported_file_type")


async def spool_upload(file: UploadFile, *, max_bytes: int) -> tuple[bytes, str, str]:
    """Stream an UploadFile to a temp file with a running byte count, aborting
    the moment it exceeds `max_bytes` — never materialises the whole body in
    memory (R-003 §B.1). Validates the extension and magic bytes, then reads
    the (size-capped) result back as bytes for the extraction pipeline, which
    already expects `bytes` in this codebase.

    Returns (data, sha256_hex, canonical_suffix). Raises UploadRejected on any
    validation failure; the temp file is always removed.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadRejected(415, "unsupported_file_type")

    digest = hashlib.sha256()
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    sniffed = False
    try:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise UploadRejected(413, "file_too_large")
            if not sniffed:
                _sniff(chunk[:8], suffix)
                sniffed = True
            digest.update(chunk)
            tmp.write(chunk)
        tmp.flush()
        if size == 0:
            raise UploadRejected(400, "empty_file")
        tmp.close()
        return Path(tmp.name).read_bytes(), digest.hexdigest(), suffix
    finally:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
