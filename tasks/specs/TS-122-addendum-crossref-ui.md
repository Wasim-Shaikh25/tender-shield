# TS-122 — Addendum cross-reference / diff UI

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/crossref.md` (to be updated when built)
**Module(s):** frontend, `crossref`
**Severity / Gate:** P1 · Gate 7

## What this builds

A frontend surface for TS-051's Clause Change Detection engine (already
built server-side, no UI). The product's own copy warns that addenda
change the commercial position — the engine that proves it exists, but the
surface showing it to a reviewer doesn't.

## Implementation (reference plan — not yet built)

An addendum-diff view: select two document versions, show added/removed/
changed clauses side by side (TS-051's existing diff output), with each
change linkable back to its source page. Also a surface for TS-053's
cross-document clause search (same module, closely related).

## Files touched (planned)

- `frontend/app/opportunities/[id]/addenda/page.tsx` (new)

## Tests (planned)

- Manual verification against TS-051's existing backend data.

## Acceptance criteria (R-023)

- [ ] A reviewer can select two document versions and see added/removed/
      changed clauses without calling the API directly.

## Commit

Not yet implemented.
