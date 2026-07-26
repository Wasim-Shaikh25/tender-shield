# Health — Spec

**Status:** implemented
**Requirement refs:** Doc §11.1
**Task refs:** TS-031

## Purpose

A lightweight endpoint for deploy-time health checks, module discovery, and
capability introspection. It is intentionally stateless and read-only: it
reports the module load report produced at boot, including failed modules and
missing soft dependencies, so operators and CI can verify a deployment.

## Public interface

- **Capabilities published:** none.
- **Capabilities consumed (soft):** none.
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes** (prefix `/api/health`):
  - `GET /` (unauthenticated) — `status`, loaded modules, failed modules,
    missing soft dependencies, and capability names.

## Data owned

None. The response is constructed from `app.state.load_report` and
`app.state.ctx.registry`.

## Behavior

- **B1 — Boot report:** The response contains the list of modules that loaded,
  any that failed with exception text, and any soft dependencies that were
  declared but whose providing module is not loaded.
- **B2 — Capability list:** `capabilities` enumerates the string names currently
  registered, making it easy to verify cross-module wiring in staging.
- **B3 — Safe to call:** No DB query is required; the endpoint should return
  200 even if PostgreSQL is temporarily unreachable.

## Acceptance criteria

- A1: `GET /api/health` returns `status: ok` and a non-empty `modules` list when
  the app boots normally.
- A2: The response includes the `findings.store_factory` capability when
  `findings` is enabled.

## Out of scope

- Readiness/liveness split for Kubernetes (P2).
- Deep dependency health checks (DB, Redis, S3) (P2).
