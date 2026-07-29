# TS-026 — Real file upload (multipart) + text extraction (PDF/XLSX/CSV)

**Status:** done
**Requirement:** Doc §3.3, §6.1
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

Replaces placeholder/text-only ingestion with real multipart upload plus
extraction across the actual formats a tender pack arrives in — feeding
classify/segment/deadlines (TS-014/015/016) with real document text instead
of a stub.

## Implementation

```python
# backend/app/modules/ingestion/extract.py
def extract_text(filename: str, data: bytes) -> str: ...
def _pdf(data: bytes) -> str: ...          # pypdf
def _xlsx(data: bytes) -> str: ...         # openpyxl
def extract_upload(filename: str, data: bytes, ocr=None) -> tuple[str, str]: ...
def looks_like_boq_csv(filename: str, data: bytes) -> bool: ...
def xlsx_to_csv(data: bytes) -> str: ...
```

`extract_upload` returns `(text, status)` — `status` includes `needs_ocr`
when the PDF has no extractable text layer (a scanned image), which TS-038
later resolves via OCR rather than silently returning empty text.

## Files touched

- `backend/app/modules/ingestion/extract.py`, `storage.py`, `router.py`

## Tests

- `backend/tests/modules/ingestion/test_extract.py`

## Acceptance criteria

- [x] PDF, XLSX, and CSV uploads all produce extracted text/rows feeding the
      pipeline.
- [x] A scanned (non-text-layer) PDF is flagged `needs_ocr`, not silently
      returned as empty.

## Commit

Predates commit-granular history (PR #10 bulk import).
