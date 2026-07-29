# TS-034 — Celery + Redis: async page-streamed processing (SSE)

**Status:** todo (needs Redis; superseded by TS-105)
**Requirement:** Doc §3.1, §3.3
**Spec(s) updated:** `specs/modules/core.md` (to be updated when built)
**Module(s):** `core`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Async, page-streamed document processing so a large tender pack's
classify/segment/deadline pipeline reports progress via SSE instead of the
caller blocking on one long synchronous request.

## Current status

Superseded by the richer design in **TS-105** (`tasks/specs/TS-105-*.md`,
Gate 5/6/7 batch): a `Job` model + `JobQueue` protocol with both an inline
(no-Redis, dev/test) backend and a Celery+Redis backend, plus SSE progress —
this task's scope is now a subset of R-016 §A's job pipeline rather than a
separate standalone build. Kept as its own tracker row for history; new work
against this scope should target TS-105's acceptance criteria instead.

## Files touched (planned)

Superseded — see TS-105.

## Tests (planned)

Superseded — see TS-105.

## Acceptance criteria

- [ ] Superseded — tracked under TS-105's A1–A6 (R-016 §A) instead.

## Commit

Not yet implemented; superseded before implementation.
