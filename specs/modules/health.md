# Health — Spec

**Status:** implemented  
**Requirement refs:** Doc §11.1, `PRODUCTION_READINESS_AUDIT.md` F23  
**Task refs:** TS-031, TS-083

## Purpose

A lightweight endpoint for deploy-time health checks and module discovery. The
public surface is intentionally minimal to avoid information disclosure; the
detailed capability/module report is gated behind super-admin authentication.

## Public interface

- **Capabilities published:** none.
- **Capabilities consumed (soft):** `auth.current_principal` (for `/details`).
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes** (prefix `/api/health`):
  - `GET /` (unauthenticated, public) — `status`, `version`.
  - `GET /details` (super-admin) — loaded modules, failed modules, missing soft
    dependencies, and capability names.

## Data owned

None. The response is constructed from `app.state.load_report` and
`app.state.ctx.registry`.

## Behavior

- **B1 — Public health:** `GET /api/health` returns `{"status":"ok","version":"0.1.0"}`
  and never queries the database, so it remains available during DB outages.
- **B2 — Detailed report:** `GET /api/health/details` requires an authenticated
  super-admin (`principal.is_superadmin` is true). It returns the module load
  report and capability list.
- **B3 — Safe to call:** No DB query is required for the public endpoint.

## Acceptance criteria

- A1: `GET /api/health` returns `status: ok` and `version` without authentication.
- A2: `GET /api/health/details` without a super-admin token returns 403.
- A3: `GET /api/health/details` with a super-admin token returns loaded modules
  and capabilities.

## Out of scope

- Readiness/liveness split for Kubernetes (P2).
- Deep dependency health checks (DB, Redis, S3) (P2).
