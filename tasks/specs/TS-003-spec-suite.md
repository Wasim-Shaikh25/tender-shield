# TS-003 — Spec suite in `specs/` — product overview + per-module specs

**Status:** done
**Requirement:** user request; Doc §0–§9
**Spec(s) updated:** `specs/000-product-overview.md`, `specs/modules/*.md` (created)
**Module(s):** —
**Severity / Gate:** P1 · Bootstrap

## What this builds

The spec suite itself: `specs/000-product-overview.md` (wedge, personas,
scope fences, phase gates) plus the per-module template
(`specs/README.md`) every later module spec follows.

## Implementation

Template established in `specs/README.md` (Purpose · Requirement refs ·
Public interface · Data owned · Behavior · Acceptance criteria · Out of
scope) — every one of the 21 current module specs under `specs/modules/`
follows it. `specs/SYSTEM.md` (added by TS-126's restructure) now indexes
all of them with status in one place.

## Files touched

- `specs/000-product-overview.md`, `specs/README.md`, `specs/modules/` (initial set)

## Tests

None — process/documentation task.

## Acceptance criteria

- [x] `specs/000-product-overview.md` covers wedge/personas/scope/phase
      gates per Doc §0, §1, §10, §12.
- [x] The per-module template is followed by every subsequent spec.

## Commit

Predates commit-granular history (PR #10 bulk import).
