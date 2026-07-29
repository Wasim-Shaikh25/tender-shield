# TS-017 — `risk` module: pattern engine (retrieve → classify → verify), deterministic severity

**Status:** done
**Requirement:** Doc §6.3
**Spec(s) updated:** `specs/modules/risk.md`
**Module(s):** `risk`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The risk-clause detection pipeline: retrieve candidate clauses by anchor
query, classify with an LLM only to locate/summarize (never to invent facts
or assign severity), verify the returned quote is actually verbatim in the
source clause, then score severity deterministically. Also detects
*absence* findings (e.g. no LD cap stated at all) — the counterpart to
quote-based findings.

## Implementation

```python
# backend/app/modules/risk/engine.py
def retrieve_candidates(clauses: list[Clause], anchor_queries: list[str]) -> list[Clause]: ...

def verify_quote(quote: str, candidates: list[Clause], threshold: float = 0.85) -> bool:
    """Quote-verification gate (CLAUDE.md §4): a returned quote must fuzzy-match
    a real candidate clause above threshold, or the finding is rejected —
    no invented quotes reach the reviewer."""

def _absence_finding(pattern, opp_facts: dict) -> Finding: ...
def run_pattern(pattern, clauses, classifier, opp_facts) -> list[Finding]: ...
def run_patterns(patterns, clauses, classifier, opp_facts) -> list[Finding]: ...
```

```python
# backend/app/modules/risk/severity.py
def evaluate_severity(rule: str, context: dict, *, default: str = "medium") -> str:
    """Evaluates a pattern's severity_rule (e.g. rulepacks TS-008's
    "critical if cap_absent else high if rate_percent_per_week > 0.5 ...")
    via a restricted AST evaluator — deterministic code, never LLM judgment
    (CLAUDE.md §4)."""
```

`classifier.py`'s `AnthropicClassifier`/`NullClassifier` (soft dependency —
absent means classification is skipped, not a crash) is the only LLM
touchpoint; it never determines severity or is trusted for a quote without
`verify_quote` passing.

## Files touched

- `backend/app/modules/risk/{engine,classifier,severity,service,router}.py`

## Tests

- `backend/tests/modules/risk/test_engine.py`, `test_severity.py`

## Acceptance criteria

- [x] A finding's quote must pass `verify_quote` before it's stored/displayed.
- [x] Severity is computed by `evaluate_severity` from the pattern's
      `severity_rule`, never assigned by the LLM.
- [x] Absence of an expected clause (e.g. no LD cap) produces its own
      finding type.

## Commit

Predates commit-granular history (PR #10 bulk import).
