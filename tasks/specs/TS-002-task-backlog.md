# TS-002 — Task backlog generated from requirements

**Status:** done
**Requirement:** user request
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P1 · Bootstrap

## What this builds

The first task backlog — one row per `TS-###`, derived from
`docs/TenderShield_Full_Build_Doc.md`'s value order (§13.5). Originally
`tasks/backlog.md`; consolidated into `tasks/TRACKER.md` by TS-126's
restructure (see that file's intro).

## Implementation

Original shape (`tasks/backlog.md`, now a stub):

```markdown
| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-001 | Repo bootstrap... | user request | — | done |
```

Current shape (`tasks/TRACKER.md`): the same rows, sectioned by phase/gate,
with added `Task file` and `Requirement`-link columns, checked by
`scripts/check_tracker.py`.

## Files touched

- `tasks/backlog.md` (original) → `tasks/TRACKER.md` (current, TS-126)

## Tests

None — process task. `scripts/check_tracker.py` now checks the tracker's
structural integrity going forward.

## Acceptance criteria

- [x] Every task from the build doc's Phase 0/1 scope has a row.
- [x] Statuses are one of `todo | in-progress | blocked | done`.

## Commit

Predates commit-granular history (PR #10 bulk import).
