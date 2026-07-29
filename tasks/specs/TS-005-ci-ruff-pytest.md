# TS-005 — CI: ruff + pytest on push (GitHub Actions)

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P1 · Bootstrap

## What this builds

The `backend` CI job: `ruff check .` + `pytest -q` on every push, so a
regression is caught before merge. Later extended with `backend-postgres`
(TS-086, RLS/race tests against real Postgres) and `frontend` (TS-032, `npm run build`).

## Implementation

```yaml
# .github/workflows/ci.yml
jobs:
  backend:
    ...
  backend-postgres:
    ...
  frontend:
    ...
```

## Files touched

- `.github/workflows/ci.yml`

## Tests

The job itself is the test harness; no separate test-of-the-test exists
beyond "does the job run green on a real push," which every commit since
proves.

## Acceptance criteria

- [x] `ruff check .` runs on every push.
- [x] `pytest -q` runs on every push.

## Commit

Predates commit-granular history (PR #10 bulk import).
