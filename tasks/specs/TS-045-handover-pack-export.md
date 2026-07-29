# TS-045 — Handover-pack file export (DOCX/PDF) reusing the export renderer

**Status:** todo
**Requirement:** Doc §1.1(8), §0.1
**Spec(s) updated:** `specs/modules/export.md` (to be updated when built)
**Module(s):** `baseline`, `export`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

A downloadable file for the handover pack TS-041/042 currently only render
in-browser — reusing `export.render_docx`/`render_pdf` (TS-023/030) rather
than building a parallel renderer.

## Implementation (reference plan — not yet built)

- `baseline.service` assembles the handover pack's structured content
  (frozen baseline summary, notice register, award-vs-tender delta) into the
  same `findings`-shaped input `export.render_docx`/`render_pdf` already
  accept, so the existing stamp/gate logic applies unchanged.
- New route: `POST /api/baseline/{id}/handover/export`.

## Files touched (planned)

- `backend/app/modules/baseline/{service,router}.py`
- `backend/app/modules/export/render.py` (new content-shape branch, if
  needed, rather than a parallel renderer)

## Tests (planned)

- `backend/tests/modules/baseline/test_handover_export.py`

## Acceptance criteria

- [ ] The handover pack exports as DOCX/PDF using the existing export
      renderer, stamped identically to the Bid Review Pack.

## Commit

Not yet implemented.
