# TS-049 — Qualification Compliance Matrix

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/qualification.md`
**Module(s):** `qualification`
**Severity / Gate:** P0 · Phase 1.5

## What this builds

The `qualification` module: extracts eligibility criteria (minimum turnover,
years of experience, EMD amount, required certifications) from the tender
and flags gaps against the org's own qualification profile as findings.

## Implementation

```python
# backend/app/modules/qualification/service.py
@dataclass
class QualificationCriterion:
    kind: str            # turnover | experience | emd | certification
    required: str
    org_value: str | None
    status: str           # met | not_met | unknown

def _build_evidence(clause: dict, keyword: str) -> tuple[str, int | None, str]:
    """(source_quote, source_page, matched keyword) — provenance for every
    extracted criterion, per CLAUDE.md §4."""

class QualificationService: ...

def _to_finding(c: QualificationCriterion) -> Finding: ...
```

`not_met`/`unknown` statuses feed directly into TS-048's Bid Readiness
Score (`qualification_gap` finding kind).

## Files touched

- `backend/app/modules/qualification/{service,router,module}.py`

## Tests

- `backend/tests/modules/qualification/test_service.py`

## Acceptance criteria

- [x] Every extracted criterion carries a verbatim source quote + page.
- [x] A criterion the org's profile doesn't meet produces a `not_met`
      finding; missing org data produces `unknown`, not a false `met`.

## Commit

Predates commit-granular history (PR #10 bulk import).
