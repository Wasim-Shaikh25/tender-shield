# TS-055 — Structured Review Outcomes

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/review.md`
**Module(s):** `review`
**Severity / Gate:** P0 · Phase 1.5

## What this builds

Extends TS-021's review decision beyond a binary accept/reject: adds
`needs_clarification` and `false_positive` outcomes with a rejection-reason
field, so review data itself becomes useful telemetry (feeds TS-057's
accuracy dashboard) instead of a coarse yes/no.

## Implementation

```python
# backend/app/modules/review/service.py
DECISIONS = {"accepted", "edited", "rejected", "false_positive", "needs_clarification"}
```

```python
# backend/app/modules/review/router.py
class ReviewBody(BaseModel):
    decision: str  # accepted | edited | rejected | false_positive | needs_clarification
```

Export gating (TS-021's `gate()`) treats both `proposed` and
`needs_clarification` findings as still pending (Doc §11.4) — export stays
blocked until a finding reaches a terminal reviewed state, not merely
"touched."

## Files touched

- `backend/app/modules/review/{service,router,models}.py`

## Tests

- `backend/tests/modules/review/test_service.py::test_structured_outcomes`

## Acceptance criteria

- [x] All 5 decision states are accepted and persisted with an optional
      rejection reason.
- [x] `needs_clarification` still counts as pending for export gating, not
      as resolved.

## Commit

Predates commit-granular history (PR #10 bulk import).
