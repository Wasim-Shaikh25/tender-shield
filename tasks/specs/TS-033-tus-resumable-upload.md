# TS-033 — tus resumable upload

**Status:** todo
**Requirement:** Doc §4, §6.1
**Spec(s) updated:** `specs/modules/ingestion.md` (to be updated when built)
**Module(s):** `ingestion`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Resumable, chunked upload (tus protocol) for large tender packs on flaky
connections — today's `POST /opportunities/{id}/upload` (TS-026) is a
single-shot multipart request with no resume-on-failure.

## Implementation (reference plan — not yet built)

- Add a `tusd`-compatible endpoint (either the reference `tusd` server as a
  sidecar, or a minimal in-house tus-protocol handler) in front of
  `ingestion.storage`.
- On upload completion, hand off to the existing `extract_upload` /
  `classify_text` pipeline unchanged — this task only replaces the transport,
  not the extraction/classification path.
- Frontend: swap the current `<input type=file>` multipart post for a
  `tus-js-client` upload with resume support.

## Files touched (planned)

- `backend/app/modules/ingestion/storage.py`, `router.py`
- `frontend/app/opportunities/[id]/` upload component

## Tests (planned)

- Interrupt-and-resume integration test against a large fixture file.

## Acceptance criteria

- [ ] An upload interrupted mid-transfer resumes from the last received
      byte, not from zero.
- [ ] Existing classify/extract pipeline is unaffected by the transport
      change.

## Commit

Not yet implemented.
