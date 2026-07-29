# TS-115 — Workspace data export + account/workspace closure (DPDP)

**Status:** todo
**Requirement:** [R-021 §B](../../specs/requirements/R-021-audit-and-data-rights.md)
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** `auth`, all workspace-scoped modules
**Severity / Gate:** P1 · Gate 6

## What this builds

There is no workspace deletion, no account deletion, and no data-export
route today — but the product already makes a privacy promise in shipped
copy ("Everything you upload lives inside your workspace only... never
used to train models" — `frontend/app/help/page.tsx`) that implies
controls (export, erasure) which don't exist yet. TS-109's planned legal
pages would otherwise describe a DPDP process the software cannot actually
perform.

## Implementation (reference plan — not yet built)

**Workspace data export**: owner-initiated, delivered as a job (TS-105):
structured JSON of every workspace-scoped entity plus all original
uploaded files. **Workspace closure**: owner-initiated, schedules deletion
after a grace period, orchestrated across every module owning
workspace-scoped tables (each module handles its own cleanup — no
cross-module foreign-key cascade, CLAUDE.md §2). **Statutory retention is
an explicit, disclosed exception**: issued GST invoices (TS-096) are
retained per Indian tax law even after closure, and the user is told this
plainly at the point of closure, not discovered later. **Account
deletion** is distinct from workspace deletion: a user who is the sole
owner of a workspace must transfer ownership or close the workspace first
— the existing last-owner guard (TS-084) already models this constraint
and this task reuses it.

## Files touched (planned)

- `backend/app/modules/auth/{service,router}.py` (closure orchestration)
- Every module owning workspace-scoped tables gains a "purge this
  workspace" capability, called by the closure job
- `backend/app/core/jobs.py` integration (TS-105)

## Tests (planned)

- `backend/tests/modules/auth/test_closure.py::test_purges_all_modules_except_retained_invoices`
  (against real Postgres — must verify data is genuinely unreachable, not
  just hidden)

## Acceptance criteria (R-021 §B, B1–B5)

- [ ] Export contains every workspace-scoped entity and every stored file.
- [ ] Closure removes all workspace data except statutorily retained
      invoices, and that exception is disclosed before confirmation.
- [ ] After the grace period, deletion is irreversible and audited
      (TS-114).
- [ ] A deleted workspace's data is unreachable from every module, verified
      against real Postgres.
- [ ] A sole owner cannot delete their account without first resolving the
      workspace.

## Commit

Not yet implemented.
