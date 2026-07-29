# TS-010 — Eval / golden-set folder scaffold

**Status:** done
**Requirement:** Doc §19
**Spec(s) updated:** `specs/phase0-accuracy-test.md`
**Module(s):** —
**Severity / Gate:** P0 · Bootstrap

## What this builds

The `evals/` folder shape the Week-2 accuracy harness (TS-006) and all later
category-specific evals run against: one sample tender with a hand-scored
gold answer, plus per-category scaffolds for the evals that follow.

## Implementation

```
evals/in-works/
├── README.md
├── scorecard.md              # Doc §19.4-19.5 scoring template
├── sample_tender/
│   ├── README.md
│   ├── boq.csv
│   ├── conditions.md
│   └── gold_answer.yaml      # hand-scored ground truth
├── boq/.gitkeep
├── classification/.gitkeep
├── deadlines/.gitkeep
├── drafting/.gitkeep
└── risk_patterns/.gitkeep
```

`scorecard.md` fixes the pass/fail bar (HIT/MISS/critical-MISS/NOISE/BONUS,
and a hard red-flag rule: any reported quote not verbatim in the source
document is an automatic fail) *before* looking at results, per Doc §19 —
no moving goalposts once real numbers are in.

## Files touched

- `evals/in-works/{README.md,scorecard.md}`
- `evals/in-works/sample_tender/{README.md,boq.csv,conditions.md,gold_answer.yaml}`
- `evals/in-works/{boq,classification,deadlines,drafting,risk_patterns}/.gitkeep`

## Tests

None — fixture/scaffold. Consumed by `scripts/phase0_accuracy_test.py` (TS-006).

## Acceptance criteria

- [x] A sample tender with a hand-scored gold answer exists.
- [x] The scoring rubric (scorecard.md) is fixed before any run's results
      are scored against it.
- [x] Per-category folders exist for evals added by later tasks.

## Commit

Predates commit-granular history (PR #10 bulk import).
