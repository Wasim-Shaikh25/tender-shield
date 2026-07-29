# TS-095 — Stream uploads; enforce size cap before buffering; type allowlist; ZIP guards

**Status:** done
**Requirement:** [R-003](../../specs/requirements/R-003-upload-safety.md)
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `core`, `ingestion`, `boq`
**Severity / Gate:** P1 · Gate 1

## What this builds

Closes five upload-safety gaps: (1) the whole file body was read into RAM
*before* the size check ran (three concurrent 2GB uploads = 6GB resident
memory); (2) no content-type/extension allowlist — `LocalStorage.put` took
any suffix verbatim; (3) no per-workspace storage quota; (4) no ZIP guards
(zip-bomb, path traversal) despite tender packs legitimately arriving as
ZIPs; (5) no malware-scanning hook.

## Current (the defect)

```python
# backend/app/modules/ingestion/router.py:108 (before this task)
async def upload_document(...):
    data = await file.read()                     # entire body into RAM
    if len(data) > MAX_UPLOAD_BYTES:             # 2 GB, checked AFTER buffering
        raise HTTPException(413, "file_too_large")
```

## Implementation

```python
# backend/app/modules/ingestion/router.py
MAX_UPLOAD_BYTES = 512 * 1024 * 1024        # 512 MB per file
ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".zip", ".txt"}

async def _spool(file: UploadFile, limit: int) -> tuple[Path, int, str]:
    """Stream to a temp file, abort the moment size exceeds limit — never
    materializes the whole body in memory."""
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix)
    while chunk := await file.read(CHUNK):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, "file_too_large")
        tmp.write(chunk)
    ...
```

```python
# type validated by magic bytes, not client-claimed extension
_MAGIC = {b"%PDF-": ".pdf", b"PK\x03\x04": ".zip", b"\xd0\xcf\x11\xe0": ".doc"}

def sniff(path: Path, filename: str) -> str:
    """Canonical extension from magic bytes; rejects when the declared
    suffix and sniffed type disagree (a .pdf whose bytes are a ZIP)."""
```

```python
# per-workspace storage quota, sourced from billing entitlements (R-009)
def _check_quota(self, workspace_id, incoming_bytes: int) -> None:
    used = self.s.scalar(select(func.coalesce(func.sum(Document.size_bytes), 0))...)
    quota = entitlements(workspace_id).storage_bytes if entitlements else STORAGE_QUOTA_BYTES["free"]
    if used + incoming_bytes > quota:
        raise HTTPException(413, detail={"code": "storage_quota_exceeded", ...})
```

```python
# ZIP guards: zip-bomb defense, path-traversal rejection, entry-count cap
def safe_extract(zf, dest, *, max_total=2 << 30, max_entries=2000) -> list[Path]:
    if len(zf.infolist()) > max_entries:
        raise HTTPException(413, "zip_too_many_entries")
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest.resolve())):
            raise HTTPException(400, "zip_path_traversal")
        ...
```

```python
# backend/app/modules/ingestion/scan.py — malware-scan interface, shipped as
# a no-op (same pattern as notifications.Sender), real scanner pluggable later
class Scanner(Protocol):
    def scan(self, path: Path) -> tuple[bool, str | None]: ...

class NullScanner:
    """Dev/test default; Document.scan_status stays 'unscanned', never lies
    about being scanned."""
```

## Files touched

- `backend/app/modules/ingestion/{router,storage,scan,models}.py`
- `backend/migrations/versions/c9ed90a8524f_document_size_and_content_type.py`

## Tests

- `backend/tests/modules/ingestion/test_upload_safety.py` (streaming size
  cap, magic-byte sniffing, ZIP guards, quota enforcement)

## Acceptance criteria (R-003, A1–A6)

- [x] An oversized upload is rejected before the full body is buffered in
      memory.
- [x] A file whose declared extension disagrees with its magic bytes is
      rejected.
- [x] Uploads beyond a workspace's storage quota are rejected with the same
      upsell-shaped payload as the billing paywall.
- [x] A malicious ZIP (bomb or path traversal) is rejected before
      extraction.

## Commit

Predates commit-granular history (PR #10 bulk import).
