# TS-108 — Product metrics: finding-acceptance rate, golden-set scorer in CI, funnel events

**Status:** todo
**Requirement:** [R-016 §D](../../specs/requirements/R-016-platform-scale.md)
**Spec(s) updated:** `specs/modules/analytics.md` (to be updated when built)
**Module(s):** `analytics`, `review`, evals
**Severity / Gate:** P1 · Gate 4

## What this builds

The highest-leverage item in R-016: `specs/000-product-overview.md` defines
the Phase-1 exit gate as deadline F1 ≥ 0.95, QS acceptance ≥ 70%, 10 real
tenders, 3 paid conversions, and a kill gate at "finding acceptance <50%
after two eval cycles" — **none of these are measurable today**. The raw
data exists (TS-021's audit log records every accept/reject decision); this
task builds the aggregation that turns it into an answer to "has the kill
gate been crossed?"

## Implementation (reference plan — not yet built)

```python
# backend/app/modules/analytics/service.py
def finding_acceptance(self, *, workspace_id=None, since=None, pack_version=None) -> dict:
    """The Phase-1 kill-gate metric. Denominator is REVIEWED findings, not
    all findings — unreviewed ones are pending, not rejected, and counting
    them would understate quality and could trip the kill gate on a
    product that is actually working."""
    return {
        "acceptance_rate": (accepted + edited) / reviewed if reviewed else None,
        "by_pattern_id": {...},   # THE actionable cut: which patterns to
                                  # promote to confidence: validated, which to retire
    }
```

Deadline F1 needs a real golden set (today `evals/in-works/` holds one
synthetic tender):

```
evals/golden/<tender-id>/
    source/          # the pack (gitignored if licensing prevents committing)
    expected.yaml    # deadlines, key findings, BOQ defects — QS-verified
    provenance.md    # where it came from, who verified it, when

def score_deadlines(expected, actual) -> dict:
    """Precision/recall/F1, ±1 day tolerance on due_at, matching kind.
    Deterministic — a measurement, not a judgement."""
```

`scripts/phase0_accuracy_test.py` (TS-006) exists as a standalone script;
this task turns it into a CI job that fails when F1 regresses below the
gate on the golden set.

Funnel events, none emitted today: `signup`, `email_verified`,
`first_opportunity`, `first_upload`, `first_review_run`,
`first_finding_accepted`, `first_export`, `paywall_hit`,
`checkout_started`, `payment_succeeded`, `second_tender_uploaded` — the
last is the important one, since the kill gate is "<40% second-tender
conversion," which is the metric that says whether the product is
habit-forming or a one-off curiosity. Privacy constraint: analytics store
event counts and identifiers only, never tender content, clause text, or
customer names — the "no training on customer data" commitment extends to
telemetry.

## Files touched (planned)

- `backend/app/modules/analytics/service.py`
- `evals/golden/` (new golden-set structure)
- `scripts/phase0_accuracy_test.py` → CI job

## Tests (planned)

- `backend/tests/modules/analytics/test_finding_acceptance.py`
- `.github/workflows/ci.yml` golden-set F1 regression job

## Acceptance criteria (R-016 §D, A14–A18)

- [ ] `finding_acceptance()` correctly excludes unreviewed findings from
      its denominator.
- [ ] A golden-set F1 regression below the gate fails CI.
- [ ] No analytics event or store contains tender document text or clause
      quotes.

## Commit

Not yet implemented.
