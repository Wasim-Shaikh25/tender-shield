# TS-048 — Bid / No-Bid Recommendation: deterministic Bid Readiness Score

**Status:** done
**Requirement:** Phase 1.5 doc §5
**Spec(s) updated:** `specs/modules/drafting.md`
**Module(s):** `drafting`
**Severity / Gate:** P0 · Phase 1.5

## What this builds

A deterministic 0-100 Bid Readiness Score computed from every confirmed
finding's kind/severity, plus a conditional recommendation artifact — never
an LLM opinion on whether to bid, per CLAUDE.md §4 ("severity scoring
[is] deterministic code").

## Implementation

```python
# backend/app/modules/drafting/generator.py
def _bid_decision(title: str, findings: list[dict], weights: dict | None) -> dict:
    weights = weights or {}
    risk_w = weights.get("risk", {"critical": 25, "high": 15, "medium": 8, "low": 3, "info": 0})
    qual_w = weights.get("qualification", {"not_met": 20, "unknown": 10, "met": 0})
    boq_w = weights.get("boq", {"critical": 15, "high": 10, "medium": 5, "low": 2, "info": 0})
    std_w = weights.get("standard_violation", 15)

    score = 100
    concerns = []
    for f in findings:
        kind = f.get("kind", "risk_clause")
        sev = f.get("severity", "medium")
        if kind == "risk_clause":
            score -= risk_w.get(sev, 0)
            if sev in ("critical", "high"):
                concerns.append(f)
        elif kind == "qualification_gap":
            status = f.get("explanation", {}).get("status") or "unknown"
            if status == "not_met":
                score -= qual_w.get("not_met", 20)
            elif status == "unknown":
                score -= qual_w.get("unknown", 10)
        elif kind == "boq_defect":
            score -= boq_w.get(sev, 0)
        elif kind == "standard_violation":
            score -= std_w
    score = max(0, min(100, score))
```

Weights are configurable (org-tunable) but the arithmetic itself is fixed
code — the recommendation text is templated off the score band, not
generated free-form by an LLM.

## Files touched

- `backend/app/modules/drafting/generator.py`

## Tests

- `backend/tests/modules/drafting/test_generator.py::test_bid_decision`

## Acceptance criteria

- [x] The score is a pure function of finding kind/severity — reproducible
      given the same findings.
- [x] A `critical` risk finding or `not_met` qualification gap materially
      lowers the score.

## Commit

Predates commit-granular history (PR #10 bulk import).
