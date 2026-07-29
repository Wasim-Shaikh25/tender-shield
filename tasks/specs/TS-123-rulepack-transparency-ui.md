# TS-123 — Rule-pack transparency UI

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/rulepacks.md` (to be updated when built)
**Module(s):** frontend, `rulepacks`
**Severity / Gate:** P2 · Gate 7

## What this builds

A UI answering "why did you flag this?" honestly: which rule-pack patterns
ran against a given opportunity, at which pack version, and at what
confidence (`validated` vs `unvalidated`, TS-008/TS-057's governance
data). Supports the product's own provenance invariant (CLAUDE.md §4) that
every finding is labelled by how it was produced, not just what it found.

## Implementation (reference plan — not yet built)

A panel (likely alongside TS-054's existing `explanation` object display)
showing the pack version and pattern confidence for each finding, plus a
standalone "what ran" view listing every pattern evaluated for the
opportunity — including patterns that produced no finding, so a reviewer
can distinguish "checked, clean" from "never checked."

## Files touched (planned)

- `frontend/app/opportunities/[id]/page.tsx` (finding-card extension)
- `frontend/app/opportunities/[id]/rulepacks/page.tsx` (new, "what ran" view)

## Tests (planned)

- Manual verification against existing rule-pack metadata already attached
  to findings (TS-054).

## Acceptance criteria (R-023)

- [ ] Every displayed finding shows its originating pattern's confidence
      level (`validated`/`unvalidated`).
- [ ] A reviewer can see which patterns ran and produced no finding, not
      just which patterns fired.

## Commit

Not yet implemented.
