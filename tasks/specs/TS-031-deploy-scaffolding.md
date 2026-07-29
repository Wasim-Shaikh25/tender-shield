# TS-031 — Deploy scaffolding: Postgres docker-compose + Dockerfiles + `.env.example`

**Status:** done
**Requirement:** Doc §4, §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

The first reproducible local/deploy environment: a Postgres service via
docker-compose (the real dialect RLS depends on, vs. SQLite in unit tests),
backend and frontend Dockerfiles, and a documented `.env.example` so no
required setting is tribal knowledge.

## Implementation

```
docker-compose.yml     # postgres service + backend + frontend
backend/Dockerfile
frontend/Dockerfile
.env.example           # every TS_-prefixed setting, documented
```

## Files touched

- `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`,
  `.env.example`

## Tests

None — infra scaffold; exercised by the `backend-postgres` CI job (TS-086)
running against this same Postgres service shape.

## Acceptance criteria

- [x] `docker-compose up` brings up Postgres + backend + frontend.
- [x] Every setting the app reads has a documented default/example in
      `.env.example`.

## Commit

Predates commit-granular history (PR #10 bulk import).
