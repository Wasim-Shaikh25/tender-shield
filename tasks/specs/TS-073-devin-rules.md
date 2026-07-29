# TS-073 — Create Devin AI assistant rules mirroring Cursor/Claude rules

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P2 · Phase 1 (remaining)

## What this builds

The third leg of the three-way AI-assistant rule sync CLAUDE.md's header
requires: `.devin/rules/` mirroring `.cursor/rules/` and `CLAUDE.md` itself,
so Devin-driven changes follow the same workflow/architecture/spec-task
discipline as Claude- and Cursor-driven ones.

## Implementation

```
.devin/rules/
├── 00-workflow.mdc       # mirrors .cursor/rules/00-workflow.mdc
├── 10-architecture.mdc   # mirrors .cursor/rules/10-architecture.mdc
└── 20-specs-tasks.mdc    # mirrors .cursor/rules/20-specs-tasks.mdc
```

Kept byte-identical (or near-identical, format-adjusted) to the Cursor
versions at creation time — TS-126's restructure later re-synced all three
surfaces again when the workflow/task-file format changed.

## Files touched

- `.devin/rules/{00-workflow,10-architecture,20-specs-tasks}.mdc`
- `DEVIN.md`

## Tests

None — process/documentation task.

## Acceptance criteria

- [x] `.devin/rules/` exists with the same three files as `.cursor/rules/`.
- [x] Their content matches CLAUDE.md's rules (no drift at creation time).

## Commit

Predates commit-granular history (PR #10 bulk import).
