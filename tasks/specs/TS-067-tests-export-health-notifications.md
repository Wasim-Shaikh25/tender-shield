# TS-067 — Add tests for `export`, `health`, and `notifications` modules

**Status:** done
**Requirement:** spec audit
**Spec(s) updated:** none
**Module(s):** `export`, `health`, `notifications`
**Severity / Gate:** P2 · Spec audit

## What this builds

A spec-audit finding: three modules (export, health, notifications) had
real implementations but no test coverage — the audit's code-vs-spec pass
surfaced this gap as a testing gap too.

## Implementation

- `backend/tests/modules/export/test_render.py` — DOCX/XLSX/PDF render +
  stamp assertions (also referenced by TS-023/030).
- `backend/tests/modules/health/test_router.py` — `/api/health` shape,
  including a fail-isolated module in the load report.
- `backend/tests/modules/notifications/test_digest.py`,
  `test_sender.py` — digest windowing + `ConsoleSender` behavior.

## Files touched

- `backend/tests/modules/{export,health,notifications}/test_*.py`

## Tests

The task's deliverable is the tests themselves (listed above).

## Acceptance criteria

- [x] All three previously-untested modules have at least one passing test
      file.

## Commit

Predates commit-granular history (PR #10 bulk import).
