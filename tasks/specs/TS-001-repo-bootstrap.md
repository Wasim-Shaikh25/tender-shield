# TS-001 — Repo bootstrap: AI workflow rules, requirement doc, repo map

**Status:** done
**Requirement:** user request
**Spec(s) updated:** none (this task created the rules the specs live under)
**Module(s):** —
**Severity / Gate:** P1 · Bootstrap

## What this builds

The mandatory AI-assistant workflow (Requirement → Task → Spec → Implement →
Commit → Changelog) and the repo map, so every later task follows one
process regardless of which assistant (Claude/Cursor/Devin) does the work.

## Implementation

- `CLAUDE.md` — the canonical rules (workflow loop, module architecture,
  specs convention, product invariants, conventions).
- `.cursor/rules/00-workflow.mdc`, `.cursor/rules/10-architecture.mdc` —
  Cursor's mirror.
- `docs/TenderShield_Full_Build_Doc.md` — the requirement source of truth
  every spec cites a section of.
- `README.md` — repo map (`## Repository map` section).

## Files touched

- `CLAUDE.md`, `.cursor/rules/00-workflow.mdc`, `.cursor/rules/10-architecture.mdc`
- `README.md`

## Tests

None — process/documentation task.

## Acceptance criteria

- [x] `CLAUDE.md` and `.cursor/rules/` state the same workflow.
- [x] A requirement doc (the Build Doc) exists for every spec to cite.

## Commit

Predates this repo's commit-granular history (landed in the initial bulk
import, PR #10 — see `tasks/TRACKER.md`'s intro). Reconstructed from the
current state of `CLAUDE.md`/`.cursor/rules/`, which is the ground truth for
what this task shipped.
