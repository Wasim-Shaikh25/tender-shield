# TS-063 — Fix route wording in `timeline.md`/`crossref.md` specs

**Status:** done
**Requirement:** spec audit
**Spec(s) updated:** `specs/modules/timeline.md`, `specs/modules/crossref.md`
**Module(s):** `timeline`, `crossref`
**Severity / Gate:** P0 · Spec audit

## What this builds

A spec-audit finding: both specs described API routes that no longer
matched the actual mounted paths/methods in `timeline/router.py` and
`crossref/router.py` after those modules evolved past their initial spec
draft.

## Implementation

Corrected the "API routes" section of both spec files to match the real
`@router.get`/`@router.post` decorators, verified by direct comparison
against the router source rather than re-describing from memory —
CLAUDE.md §1.2's rule that "code that contradicts its spec is a bug in one
of the two; fix the mismatch."

## Files touched

- `specs/modules/timeline.md`, `specs/modules/crossref.md`

## Tests

None — documentation-only correction.

## Acceptance criteria

- [x] Every route listed in both specs exists verbatim (path + method) in
      the corresponding router.

## Commit

Predates commit-granular history (PR #10 bulk import).
