# TS-125 — Support/ops investigation console (read-only; no impersonation by design)

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** frontend, `auth`
**Severity / Gate:** P2 (Domain-Expected) · Gate 7

## What this builds

`GET /auth/admin/users` and `/admin/workspaces` (TS-077) exist, but there
is no way for support to investigate "why did this customer's review
fail," inspect a workspace's entitlement state, or see job/run status.
Depends on TS-117 (run records) to have anything useful to show.

## Implementation (reference plan — not yet built)

A read-only console: workspace lookup showing plan/entitlements
(TS-098), recent job/run status and failure causes (TS-117), and recent
audit-log entries (TS-114) for that workspace. **Impersonation is
deliberately not proposed here** — for a product holding confidential
commercial tender packs, read-only diagnostics plus an audit record is the
safer default; impersonation would need its own consent and audit design
and is explicitly out of scope for v1 (same call made in TS-103's `/admin`
console design).

## Files touched (planned)

- `frontend/app/admin/support/page.tsx` (new)
- `backend/app/modules/auth/router.py` (read-only diagnostic endpoints)
- Depends on TS-117 (run records) and TS-114 (audit trail)

## Tests (planned)

- `backend/tests/modules/auth/test_admin_router.py::test_no_impersonation_endpoint_exists`

## Acceptance criteria (R-023)

- [ ] Support can see a workspace's plan, entitlement state, and recent
      run failures without database access.
- [ ] No impersonation capability exists anywhere in the console.

## Commit

Not yet implemented.
