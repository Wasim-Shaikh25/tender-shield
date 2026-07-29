# TS-021 — Review workbench API + append-only audit log + export gating

**Status:** done
**Requirement:** Doc §1.1(7), §11.4
**Spec(s) updated:** `specs/modules/review.md`
**Module(s):** `review`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The human-in-the-loop checkpoint: findings queue for review/confirm,
append-only audit trail of every review decision, and the gate that blocks
export until required review is complete.

## Implementation

```python
# backend/app/modules/review/models.py
class AuditLog(Base, WorkspaceScopedMixin):
    """Append-only: no update/delete path exists in the service layer —
    every review decision (confirm/reject/edit) is a new row."""
```

```python
# backend/app/modules/review/router.py
def queue(...): ...          # findings pending review
def review_finding(...): ...  # confirm/reject/edit a finding
def gate(...): ...            # is export unlocked for this opportunity?
def audit_trail(...): ...     # full history
```

`gate()` is what `export`'s router checks before rendering a Bid Review Pack
(TS-023) — export is refused, not just warned, when required review isn't
complete.

## Files touched

- `backend/app/modules/review/{models,service,router,module}.py`

## Tests

- `backend/tests/modules/review/test_service.py`

## Acceptance criteria

- [x] Every review decision is recorded in an append-only audit log (no
      update/delete path).
- [x] Export is blocked by `gate()` until required review criteria are met.

## Commit

Predates commit-granular history (PR #10 bulk import).
