# TS-006 — Week-2 accuracy test harness

**Status:** done
**Requirement:** Doc §19
**Spec(s) updated:** `specs/phase0-accuracy-test.md`
**Module(s):** —
**Severity / Gate:** P1 · Phase 0

## What this builds

A throwaway script + scorecard template to de-risk domain accuracy early —
run the pipeline against a real tender, compare to gold answers, before
committing further engineering to unvalidated patterns.

## Implementation

- `scripts/phase0_accuracy_test.py` — runs classification/deadline/risk
  extraction against a sample tender and scores it against
  `evals/in-works/sample_tender/gold_answer.yaml`.
- `specs/phase0-accuracy-test.md` — the experiment design.

## Files touched

- `scripts/phase0_accuracy_test.py`, `specs/phase0-accuracy-test.md`

## Tests

None — this IS the validation tool, run manually with a real
`ANTHROPIC_API_KEY` against real tenders (Doc §18.3/§19.2), not a unit-tested
component.

## Acceptance criteria

- [x] Script runs end-to-end against the sample tender and produces a scorecard.

## Commit

Predates commit-granular history (PR #10 bulk import).
