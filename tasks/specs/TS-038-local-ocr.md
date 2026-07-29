# TS-038 — Local OCR (RapidOCR, offline) + PDF table extraction (pdfplumber)

**Status:** done
**Requirement:** Doc §6.1, §12.4
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

An offline OCR path for scanned tender documents — no cloud OCR call, per
Doc §12.4 — behind a pluggable `OcrProvider` interface, plus pdfplumber-based
table extraction for digital (non-scanned) PDFs. When OCR is disabled
(`TS_OCR_ENABLED` off), documents needing it are honestly flagged
`needs_ocr` rather than silently degraded.

## Implementation

```python
# backend/app/modules/ingestion/ocr.py
class OcrProvider(Protocol): ...

class NullOcrProvider:
    """Returned when TS_OCR_ENABLED is off — honest needs_ocr degradation,
    never a silent empty-text fallback."""

class RapidOcrProvider:
    """Offline ONNX model (RapidOCR); no network call, no cloud OCR vendor."""

class RapidTableProvider: ...
```

## Files touched

- `backend/app/modules/ingestion/ocr.py`, `extract.py`, `tables.py`

## Tests

- `backend/tests/modules/ingestion/test_ocr.py` (provider selection; not
  sandbox-verified against a real scanned PDF — model download on first use)

## Acceptance criteria

- [x] `TS_OCR_ENABLED=false` yields `NullOcrProvider` and an honest
      `needs_ocr` status, not empty text presented as a clean extraction.
- [x] `TS_OCR_ENABLED=true` runs OCR fully offline (no cloud vendor call).

## Commit

Predates commit-granular history (PR #10 bulk import).
