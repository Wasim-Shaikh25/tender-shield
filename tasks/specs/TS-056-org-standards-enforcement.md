# TS-056 — Organization Standards Enforcement

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/standards.md`
**Module(s):** `standards`, `review`, `drafting`
**Severity / Gate:** P0 · Phase 1.5

## What this builds

Lets an org set its own commercial thresholds (e.g. "flag any LD rate above
0.3%/week," stricter than the rule-pack default) and turns a breach into a
`standard_violation` finding that flows through review the same as any
other finding and feeds TS-048's Bid Readiness Score.

## Implementation

```python
# backend/app/modules/standards/service.py
class WorkspaceCommercialStandardsService: ...

def _extract_number(finding: dict, unit: str) -> float | None:
    """Pulls the comparable numeric value out of an existing risk/BOQ
    finding (e.g. the LD rate already extracted by TS-017) — does not
    re-extract from raw text."""

def _compare(value: float, operator: str, threshold: float) -> bool: ...
```

Reuses the numbers `risk`/`boq` already extracted rather than re-parsing
clause text — standards enforcement is a policy layer over existing
findings, not a new extraction pass.

## Files touched

- `backend/app/modules/standards/service.py`
- `backend/app/modules/drafting/generator.py` (`std_w` weight in
  `_bid_decision`, TS-048)

## Tests

- `backend/tests/modules/standards/test_service.py::test_org_threshold_violation`

## Acceptance criteria

- [x] A finding's numeric value breaching an org-set threshold produces a
      `standard_violation` finding.
- [x] `standard_violation` findings lower the Bid Readiness Score via
      `std_w`.

## Commit

Predates commit-granular history (PR #10 bulk import).
