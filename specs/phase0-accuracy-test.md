# Phase-0 Week-2 Accuracy Test — Spec

**Status:** draft
**Requirement refs:** Doc §19
**Task refs:** TS-006

## Purpose

De-risk the judgment layer before building the easy 80%: does the AI catch the
risks that matter on 5 real tenders, without noise or misquotes? Throwaway
script + human scorecard — not product code.

## Inputs

- 5 real tenders (3 with known outcomes incl. 1 loss-maker; 2 live), each with
  at least GCC/SCC + BOQ.
- A gold answer per tender (founder- or QS-authored: the 5–8 findings a good
  reviewer would flag).

## Behavior

- **B1:** script lives in `scripts/phase0_accuracy_test.py`, marked throwaway;
  reads PDFs, runs the 5 Phase-0 patterns (from `rulepacks/in-works/`), prints
  findings with verbatim quotes and page hints.
- **B2:** scorecard per tender: HIT / MISS (critical misses weighted) / NOISE /
  BONUS / invented quotes. Template in `evals/in-works/scorecard.md`.
- **B3 (pass bar, fixed before looking):** overall recall ≥70% green;
  critical-clause recall ≥90% green; loss-making tender's trap caught = yes;
  noise ≤2/tender; invented quotes = 0 (any → red).
- **B4:** gold answers seed `evals/in-works/` golden sets (§11.5) — nothing wasted.

## Acceptance criteria

- A1: script runs end-to-end on a local PDF and prints per-pattern JSON findings.
- A2: scorecard template committed with the decision table.

## Out of scope

Any productionization — this code is deleted after Phase 0.
