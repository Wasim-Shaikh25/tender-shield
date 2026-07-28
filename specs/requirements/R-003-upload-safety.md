# R-003 — Upload safety: streaming, limits, type allowlist, quotas

**Status:** draft
**Severity:** P1 — memory-exhaustion DoS, unbounded tenant storage
**Requirement refs:** Doc §11.2, §6.1
**Task refs:** TS-095
**Gap refs:** `docs/GAP_ANALYSIS.md` §1.9
**Specs to update:** `specs/modules/ingestion.md`

## Purpose

The upload endpoint buffers the entire request body in RAM before checking its
size, accepts any file type, and imposes no per-workspace storage limit. A
handful of concurrent large uploads takes the process down.

## Current

```python
# backend/app/modules/ingestion/router.py:108
@router.post("/opportunities/{opportunity_id}/upload")
async def upload_document(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    svc = _service(request, session)
    if not svc.get_opportunity(principal.workspace_id, opportunity_id):
        raise HTTPException(404, "not_found")
    data = await file.read()                     # ← entire body into RAM
    if len(data) > MAX_UPLOAD_BYTES:             # ← 2 GB, checked AFTER buffering
        raise HTTPException(413, "file_too_large")
    storage = LocalStorage(request.app.state.ctx.settings.storage_dir)
    key, sha = storage.put(str(principal.workspace_id), file.filename, data)
    ...
```

Problems, in order of severity:

1. **`await file.read()` before the size check.** `MAX_UPLOAD_BYTES` is 2 GB
   (`router.py:12`). Three concurrent 2 GB uploads is 6 GB of resident memory.
2. **No content-type or extension allowlist.** `LocalStorage.put`
   (`storage.py:22`) takes `Path(filename).suffix` verbatim, so any extension
   lands on disk. (Not a traversal — only the suffix is used — but arbitrary.)
3. **No per-workspace quota.** A free-tier account can fill the volume.
4. **No malware scanning**, and tender packs arrive as email attachments from
   third parties.
5. **`extract_upload` runs inline** — a 800-page scanned PDF with OCR enabled
   blocks the worker for minutes (addressed properly in R-016).

## Target

### B.1 Stream to a temp file with a running byte count

```python
# backend/app/modules/ingestion/router.py

import shutil
import tempfile
from pathlib import Path

MAX_UPLOAD_BYTES = 512 * 1024 * 1024        # 512 MB per file
CHUNK = 1024 * 1024

ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".zip", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
    "application/zip",
    "application/octet-stream",   # browsers send this for unknown types; magic bytes decide
}


async def _spool(file: UploadFile, limit: int) -> tuple[Path, int, str]:
    """Stream the upload to a temp file, aborting the moment it exceeds `limit`.

    Never materialises the whole body in memory (R-003 §B.1). Returns
    (path, size, sha256).
    """
    digest = hashlib.sha256()
    size = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix)
    try:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > limit:
                raise HTTPException(413, "file_too_large")
            digest.update(chunk)
            tmp.write(chunk)
        tmp.flush()
        return Path(tmp.name), size, digest.hexdigest()
    except BaseException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    finally:
        tmp.close()
```

The size cap also belongs at the edge — set `client_max_body_size` (nginx) or the
equivalent so oversized bodies never reach Python at all. The application check
is the backstop, not the only line.

### B.2 Validate type by magic bytes, not by the client's claim

```python
_MAGIC = {
    b"%PDF-": ".pdf",
    b"PK\x03\x04": ".zip",       # also .docx/.xlsx (both are ZIP containers)
    b"\xd0\xcf\x11\xe0": ".doc",  # OLE2: legacy .doc/.xls
}


def sniff(path: Path, filename: str) -> str:
    """Return a canonical extension from magic bytes, falling back to the name
    for plain text/CSV which have no signature."""
    head = path.open("rb").read(8)
    for magic, ext in _MAGIC.items():
        if head.startswith(magic):
            return ext
    suffix = Path(filename).suffix.lower()
    if suffix in {".csv", ".txt"}:
        return suffix
    raise HTTPException(415, "unsupported_file_type")
```

Reject when the declared suffix and the sniffed type disagree in a way that
matters (a `.pdf` whose bytes are a ZIP), and record both in the audit log.

### B.3 Per-workspace storage quota

```python
# backend/app/modules/ingestion/models.py — Document
size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
content_type: Mapped[str | None] = mapped_column(String, nullable=True)
```

```python
# quota is an entitlement, so it comes from billing (R-009) via the registry
STORAGE_QUOTA_BYTES = {"free": 1 << 30, "paygo": 5 << 30, "pro": 50 << 30, "scale": 200 << 30}


def _check_quota(self, workspace_id, incoming_bytes: int) -> None:
    used = self.s.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0))
        .where(Document.workspace_id == uuid.UUID(str(workspace_id)))
    )
    entitlements = self._registry.get("billing.entitlements")
    quota = entitlements(workspace_id).storage_bytes if entitlements else STORAGE_QUOTA_BYTES["free"]
    if used + incoming_bytes > quota:
        raise HTTPException(
            413,
            detail={"code": "storage_quota_exceeded", "used": used, "quota": quota},
        )
```

Return the same upsell-shaped payload the paywall uses (R-004 §B.3) so the
frontend can render one paywall component for both.

### B.4 ZIP handling

Tender packs arrive as ZIPs (`specs/000-product-overview.md` NFR: "ZIP
ingestion"). ZIP expansion needs its own guards:

- **Zip-bomb defence**: reject when the sum of `ZipInfo.file_size` exceeds
  10× the compressed size or 2 GB uncompressed, whichever is lower.
- **Path traversal**: reject any entry whose normalised path escapes the root
  (`..`, absolute paths, symlinks).
- **Entry count cap**: 2,000 files.
- **Nesting cap**: do not recurse into nested archives.

```python
def safe_extract(zf: zipfile.ZipFile, dest: Path, *, max_total=2 << 30, max_entries=2000) -> list[Path]:
    total = 0
    if len(zf.infolist()) > max_entries:
        raise HTTPException(413, "zip_too_many_entries")
    for info in zf.infolist():
        if info.is_dir():
            continue
        target = (dest / info.filename).resolve()
        if not str(target).startswith(str(dest.resolve())):
            raise HTTPException(400, "zip_path_traversal")
        total += info.file_size
        if total > max_total:
            raise HTTPException(413, "zip_bomb_suspected")
    ...
```

### B.5 Malware scanning hook

Define the interface now, ship the no-op, plug ClamAV later — the same pattern
`notifications/sender.py` uses:

```python
# backend/app/modules/ingestion/scan.py

class Scanner(Protocol):
    def scan(self, path: Path) -> tuple[bool, str | None]:
        """Return (clean, signature_name)."""


class NullScanner:
    """Dev/test default. Reports everything clean and records that no scanning
    took place, so `Document.scan_status` never lies about being scanned."""

    def scan(self, path: Path) -> tuple[bool, str | None]:
        return True, None
```

`Document.scan_status` takes `unscanned | clean | infected`; an `infected`
document is quarantined (never extracted, never exported) and the upload returns
`422 file_rejected`.

## Behavior

- **B1** The request body is streamed to disk; the size cap aborts mid-stream and
  the process never holds a whole upload in memory.
- **B2** File type is determined by magic bytes; unsupported types are rejected
  with `415`.
- **B3** Uploads exceeding the workspace's storage entitlement are rejected with
  an upsell payload.
- **B4** ZIP archives are validated against bombs, traversal and entry-count
  limits before extraction.
- **B5** Every stored document records `size_bytes`, `content_type`, `sha256`
  and `scan_status`.
- **B6** Temp files are removed on every path, including exceptions.
- **B7** Re-uploading identical bytes (same sha256) within a workspace reuses the
  stored object rather than duplicating it.

## Acceptance criteria

- **A1** Posting a body larger than `MAX_UPLOAD_BYTES` returns `413` and peak
  process RSS stays within ~2× `CHUNK` of baseline.
- **A2** A `.exe` renamed to `.pdf` returns `415`.
- **A3** A workspace at quota receives `413 storage_quota_exceeded` carrying
  `used` and `quota`.
- **A4** A crafted zip bomb returns `413 zip_bomb_suspected`; a zip containing
  `../../etc/passwd` returns `400 zip_path_traversal`.
- **A5** No temp files remain under `TMPDIR` after a rejected upload.
- **A6** Uploading the same file twice creates one storage object and two
  `documents` rows referencing it.

## Out of scope

- Resumable/tus uploads — TS-033.
- Moving extraction off the request thread — R-016 §A.
- Real AV integration — interface only here; ClamAV deployment is an ops task.

## Assumptions

- `assumption:` 512 MB per file is the practical ceiling for a single tender
  document; the 2 GB figure in the current code was a pack-level limit. Packs
  arrive as ZIPs and are capped at 2 GB uncompressed by B.4.
