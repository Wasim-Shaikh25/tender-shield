# TS-008 — First 5 risk patterns (LD, defect liability, termination, payment, escalation)

**Status:** done
**Requirement:** Doc §14, §6.3
**Spec(s) updated:** `specs/modules/risk.md`
**Module(s):** `risk`
**Severity / Gate:** P0 · Bootstrap

## What this builds

The first seed set of risk-clause detection patterns in the `in-works`
rule-pack (TS-007's scaffold) — the minimum needed to run the Week-2 accuracy
test (TS-006) against a real tender.

## Implementation

```yaml
# rulepacks/in-works/risk_patterns/liquidated_damages.yaml
id: liquidated_damages_uncapped
category: ld
title: LD rate high or cap absent
confidence: unvalidated
source: >
  CPWD GCC compensation-for-delay clause (typically 0.5%/week capped at 10%)
  as the normal baseline; Arcadis/CMAA 2025 — delay damages a leading claim
  category.
severity_rule: >
  critical if cap_absent else
  high if rate_percent_per_week > 0.5 or cap_percent > 10 else medium
anchor_queries:
  - "liquidated damages"
  - "compensation for delay"
  - "penalty for delay"
judgment_prompt: >
  Find the liquidated damages / compensation-for-delay clause. Report the
  rate (% per week or per day), the basis (contract value or delayed
  portion), and whether a maximum cap is stated. The ABSENCE of a cap is
  itself the key finding. Quote verbatim.
affected_trades: [all]
```

The five files, each following this `id`/`category`/`title`/`confidence`/
`source`/`severity_rule`/`anchor_queries`/`judgment_prompt`/
`affected_trades` shape:

- `liquidated_damages.yaml` — LD rate/cap
- `defect_liability.yaml` — defect liability period length/scope
- `termination_risk.yaml` — termination-for-convenience / one-sided exit
- `payment_terms.yaml` — payment cycle, retention, delay-in-payment silence
- `price_escalation.yaml` — escalation clause absence/formula risk

Each `severity_rule` is a deterministic expression evaluated by code against
extracted field values — never an LLM-assigned severity (CLAUDE.md §4).

## Files touched

- `rulepacks/in-works/risk_patterns/{liquidated_damages,defect_liability,termination_risk,payment_terms,price_escalation}.yaml`

## Tests

Exercised indirectly by `scripts/phase0_accuracy_test.py` (TS-006) against
`evals/in-works/sample_tender/gold_answer.yaml`.

## Acceptance criteria

- [x] 5 patterns exist, each with `source:` and `confidence: unvalidated`.
- [x] Each pattern's severity is computed by a deterministic `severity_rule`,
      not left to LLM judgment.

## Commit

Predates commit-granular history (PR #10 bulk import).
