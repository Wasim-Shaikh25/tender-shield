# Phase-0 Week-2 Accuracy Scorecard (Doc §19.4–19.5)

Score `scripts/phase0_accuracy_test.py` output against each tender's gold
answer. **Fix the pass/fail bar before looking at results — no moving goalposts.**

## Per-tender scoring

For each finding in the **gold answer**:
- **HIT** — AI found it, with a correct verbatim quote.
- **MISS** — AI didn't find it. Weight **critical misses** heavily.

For each AI-reported finding NOT in the gold answer:
- **NOISE** — wrong or irrelevant.
- **BONUS** — a real risk the reviewer missed (good sign, count separately).

**Quote integrity:** any `RED_FLAG` (quote not verbatim in document) is an
automatic red, regardless of other scores.

## Scorecard

| Tender | Gold findings | HITs | MISSes | Critical MISSes | NOISE | BONUS | Invented quotes |
|---|---|---|---|---|---|---|---|
| 1 (known loss-maker) | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| **TOTAL** | | | | | | | |

- **Recall** = HITs ÷ gold findings = ____
- **Critical recall** = critical HITs ÷ critical gold findings = ____
- **Loss-making tender:** did it catch the trap that actually bit? YES / NO
- **Noise per tender** = ____

## The bar (Doc §19.5 — decided in advance)

| Metric | Green (build) | Amber (tune & re-run) | Red (stop & diagnose) |
|---|---|---|---|
| Overall recall | ≥ 70% | 50–70% | < 50% |
| Critical-clause recall | ≥ 90% | 75–90% | < 75% |
| Loss-maker's trap caught | Yes | — | No |
| Noise per tender | ≤ 2 | 3–5 | > 5 |
| Invented quotes | 0 | 0 | any |

Amber → tune prompts/patterns/retrieval and re-run (that's the actual work of
the business). Red → diagnose input (OCR), pattern vagueness, or document
quality **before** building anything else.

Gold answers created here seed the golden sets in this folder (Doc §19.6) —
nothing is wasted.
