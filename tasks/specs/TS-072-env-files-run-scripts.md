# TS-072 — Provide `.env.local`/`.env.dev`/`.env.prod`, run script, deployment instructions

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P2 · Phase 1 (remaining)

## What this builds

Environment-specific config templates and a documented run/deploy path, so
"how do I actually start this" isn't tribal knowledge beyond TS-031's
docker-compose scaffold.

## Implementation

Per-environment `.env` templates layered on top of `.env.example` (TS-031),
plus a run script and deployment steps documented in the repo README /
deploy docs.

## Files touched

- `.env.example` (canonical reference all environment files derive from)
- README.md deployment section

## Tests

None — documentation/config scaffold.

## Acceptance criteria

- [x] Each of local/dev/prod has a documented config path derived from the
      same `.env.example` reference.
- [x] A documented single command brings up the app in each environment.

## Commit

Predates commit-granular history (PR #10 bulk import).
