# TS-032 — Frontend CI (npm build) job in GitHub Actions

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

The `frontend` CI job — a build-break on the frontend is now caught on push,
same as the `backend`/`backend-postgres` jobs (TS-005/TS-086) already do for
the backend.

## Implementation

```yaml
# .github/workflows/ci.yml
frontend:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: frontend
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: "22"
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npm run build
```

## Files touched

- `.github/workflows/ci.yml`

## Tests

The job itself is the check — `npm run build` failing fails CI.

## Acceptance criteria

- [x] `npm run build` runs on every push and fails CI on a build error.

## Commit

Predates commit-granular history (PR #10 bulk import).
