# Synthetic sample tender (NOT real)

Hand-written fixture with **deliberately planted traps**, used to prove the
pipeline end-to-end without needing a real tender or an API key. Because every
trap is planted, `gold_answer.yaml` is its own ground truth — unlike a real
tender, where a human/QS must author the gold answer (Doc §14.2).

| File | What it is | Exercises |
|---|---|---|
| `boq.csv` | 9-row BOQ with planted defects | Deterministic BOQ engine (zero LLM) |
| `conditions.md` | NIT + SCC excerpts with 5 planted clause traps + `[pN]` page markers | LLM risk patterns + civil scope-gap checklist |
| `gold_answer.yaml` | The answer key (deterministic + LLM halves) | Scoring |

## Run the deterministic half now (no API key)

Covered by `backend/tests/test_boq.py` — it asserts the engine catches exactly
the planted BOQ defects (duplicate, arithmetic error, blank rate, grand-total
mismatch) and the five civil scope gaps, with zero false positives.

## Run the LLM half (needs an API key)

```bash
cd backend && pip install -e ".[dev]" && pip install anthropic
export ANTHROPIC_API_KEY=...
python ../scripts/phase0_accuracy_test.py ../evals/in-works/sample_tender/conditions.md
```

Then compare its output to the `risk_findings` block in `gold_answer.yaml`
using `../scorecard.md`. Expected: 5 HITs (escalation barred, 90-day payment,
uncapped 1%/week LD, 36-month DLP + 10% retention, convenience termination),
zero invented quotes.
