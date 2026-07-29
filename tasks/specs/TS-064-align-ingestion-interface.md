# TS-064 — Align `ingestion` public interface with code

**Status:** done
**Requirement:** spec audit; Doc §3.3, §6.1
**Spec(s) updated:** `specs/modules/ingestion.md`
**Module(s):** `ingestion`
**Severity / Gate:** P2 · Spec audit

## What this builds

A spec-audit finding: `ingestion.md`'s documented public interface (the
`service_factory` shape) was stale, and didn't yet mention the
`doc_chunks`/`doc_text` capability this same audit batch adds in TS-068.

## Implementation

Updated `specs/modules/ingestion.md`'s "Public interface" section to match
the real `ingestion.service_factory` signature and list the
`ingestion.doc_text` capability (`DocTextService`) alongside the existing
`ingestion.ocr`/`ingestion.file_to_boq_csv` entries.

## Files touched

- `specs/modules/ingestion.md`

## Tests

None — documentation-only correction, paired with TS-068's implementation.

## Acceptance criteria

- [x] Every capability `ingestion/module.py` actually calls `reg.provide()`
      for is listed in the spec, and vice versa.

## Commit

Predates commit-granular history (PR #10 bulk import).
