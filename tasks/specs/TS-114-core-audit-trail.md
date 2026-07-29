# TS-114 — Audit trail beyond review decisions; move `audit_log` to `core`

**Status:** todo
**Requirement:** [R-021 §A](../../specs/requirements/R-021-audit-and-data-rights.md)
**Spec(s) updated:** `specs/modules/core.md` (to be updated when built)
**Module(s):** `core`, `auth`, `billing`, `export`
**Severity / Gate:** P1 · Gate 6

## What this builds

`AuditLog` (TS-021) is written in exactly **one** place in the entire
application — a finding being accepted/rejected. Nothing records login,
failed login, MFA enrollment, password reset, member add/remove, role
change, invitation issued/accepted, workspace switch, plan change, payment,
refund, export, or any superadmin action. Gates 1-4 hardened tenant
isolation, auth, and payments — but none of that hardening can be
*evidenced* after an incident without this.

## Current (the gap)

```python
# backend/app/modules/review/service.py:38 — the ONLY writer today
AuditLog(...)   # finding accepted / rejected
```

## Implementation (reference plan — not yet built)

A shared audit capability in `app.core`, consumed by name so any module can
write an audit row without importing another module (CLAUDE.md §2).
`audit_log` moves out of `review` entirely — a cross-cutting concern owned
by one feature module is the wrong shape; it becomes core-owned,
workspace-scoped, and RLS-protected. Rows carry actor, action, target
type+id, source IP, timestamp — append-only, no update/delete path for
anyone, including superadmins. Call sites added across auth, billing,
ingestion, export, admin. An admin-visible viewer with filters and CSV
export (shares the screen TS-103 already builds for the existing
review-audit view, but now shows everything).

Migration must not lose existing review-decision rows when the table
moves ownership.

## Files touched (planned)

- `backend/app/core/audit.py` (new — the shared capability)
- `backend/app/modules/{auth,billing,export,review}/*.py` (call sites)
- `backend/migrations/versions/` (move `audit_log` table ownership to core)

## Tests (planned)

- `backend/tests/test_core_audit.py::test_cross_tenant_read_impossible`
  (against real Postgres with FORCE RLS — per this repo's standing
  discipline, SQLite's RLS no-op has produced false-green results before
  in this codebase)

## Acceptance criteria (R-021 §A, A1–A5)

- [ ] Login, failed login, member add/remove, role change, plan change,
      refund, export, and superadmin actions each write an audit row.
- [ ] Audit rows cannot be updated or deleted through any route.
- [ ] A cross-tenant audit read is impossible, verified against real
      Postgres with FORCE RLS.
- [ ] Moving the table preserves every existing review-decision row.

## Commit

Not yet implemented.
