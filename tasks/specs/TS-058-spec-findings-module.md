# TS-058 — Spec: `findings` module (shared findings store, `Finding` contract)

**Status:** done
**Requirement:** spec audit
**Spec(s) updated:** `specs/modules/findings.md`
**Module(s):** `findings`
**Severity / Gate:** P1 · Spec audit

## What this builds

A spec-audit finding: the `findings` module (shared store every producer —
risk, boq, qualification, standards — writes into) existed in code but had
no spec documenting its `Finding` contract and review-status columns. This
task writes that spec against the real implementation.

## Implementation

```python
# backend/app/modules/findings/models.py
class FindingRow(Base, WorkspaceScopedMixin): ...
```

```python
# backend/app/modules/findings/store.py
class FindingStore:
    """Shared write/query surface for every finding-producing module —
    the one table risk/boq/qualification/standards all persist into,
    per CLAUDE.md §2 ('shared data contracts live in app/core/contracts,
    never in one module imported by another')."""
```

`GET /api/findings` (`router.py::list_findings`) is the one cross-module
read surface for a workspace's findings regardless of which module produced
them.

## Files touched

- `specs/modules/findings.md` (new)

## Tests

None — documentation task; the module's own tests predate this task.

## Acceptance criteria

- [x] `specs/modules/findings.md` documents the `Finding` contract and
      review-status columns matching `FindingRow`.

## Commit

Predates commit-granular history (PR #10 bulk import).
