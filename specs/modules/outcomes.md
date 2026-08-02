# `outcomes` — Bid Outcome & Risk Materialization Capture — Spec

**Status:** implemented (TS-215 scaffold; prefill TS-216; margin metric TS-234)
**Requirement refs:** Build Doc §1.1(9), §11.5; `docs/TenderShield_Market_Strategy_2026.md` §C.6, §C.9;
`docs/TenderShield_Roadmap_Stage1_to_5.md` §6.1
**Task refs:** TS-215, TS-216, TS-234, TS-269

## Purpose

Close the loop the Build Doc specified and the codebase never built: record what happened to each bid
and, post-award, which flagged risks actually materialized.

`Opportunity` currently has `status` (default `reviewing`) and no bid result. Without this table there
is no private outcome layer over the public Employer Behaviour Graph, and the correction loop that
Build Doc §11.5 calls "the compounding moat" has nothing to learn from.

This is the cheapest moat increment in the plan — a handful of columns, one form, one event.

## Public interface

**Capabilities published**
- `outcomes.record` — write a bid outcome
- `outcomes.for_opportunity` — read outcomes + materialization
- `outcomes.margin_protected` — workspace north-star metric (TS-234)
- `outcomes.record_claim_outcome` — write a recovered claim value (TS-269)
- `outcomes.historical_scope_patterns` — read historical `scope_gap` categories for missing-scope suggestions (TS-319)

**Capabilities consumed (soft)**
- `findings.store` — to attach materialization to specific findings
- `marketdata.comparable_awards` — legacy comparable stub
- `marketdata.award_prefill` — prefill from public award record via tender reference

**Events emitted**
- `outcome.recorded` — consumed by `analytics` (accuracy) and the correction loop
- `outcome.risk_materialized` — a flagged risk actually bit
- `outcome.claim_recovered` — a claim was settled and the recovered amount captured (TS-269)

**API routes**
- `POST /api/outcomes/opportunities/{id}` — record/update outcome
- `POST /api/outcomes/findings/{id}/materialized` — mark a finding as materialized
- `GET  /api/outcomes/opportunities/{id}`
- `GET  /api/outcomes/opportunities/{id}/scope-patterns` — historical scope-gap patterns for missing-scope suggestions (TS-319)
- `GET  /api/outcomes/metrics/margin-protected` — verified margin protected (TS-234)

## Data owned

- `oc_bid_outcomes` — `opportunity_id`, result (`submitted|won|lost|declined|disqualified`),
  quoted value, L1 value where known, bidder count, decline reason, recorded_by, recorded_at
- `oc_risk_materialization` — `finding_id`, materialized (bool), impact amount (minor units +
  currency), narrative, recorded_at
- `oc_claim_recoveries` — `opportunity_id`, `claim_id` (one recovery per claim),
  `recovered_amount_minor` + currency, recorded_by, recorded_at (TS-269)

All workspace-scoped with RLS, like every other tenant table (`CLAUDE.md` §4).

## Behavior

### Prefill, don't demand
Users will not fill in forms. On `opportunity.status` reaching a terminal state, attempt to match the
public award record via tender reference through `marketdata`, prefill result/winner/L1 value, and
ask for **one-click confirmation**. Manual entry is always available but is never the only path.

### North-star metric — margin protected (TS-234)

Deterministic aggregation in `backend/app/modules/outcomes/margin.py`:

- **Risk allowances** — sum of `amount_exposure` on reviewed (`accepted`/`edited`) risk findings
  for opportunities that were not declined
- **Declined exposure avoided** — same exposure on reviewed findings tied to `declined` outcomes
- **BOQ defects corrected** — count of reviewed `boq_defect` findings (pre-submission corrections)
- **Materialized impact** — sum of `impact_amount_minor` on materialized risk rows
- **Claim recoveries** — sum of `recovered_amount_minor` on `oc_claim_recoveries` rows (TS-269)

Unreviewed findings and amounts without explicit currency matching the requested currency are
excluded — speculative value is never invented.

### Materialization capture
Post-award, a user can mark any accepted finding as materialized with an optional impact amount. This
is the ground truth that no public source provides (Strategy §A.2) — the difference between "the
project overran" and "this clause cost us this much."

### Feeding the correction loop
`outcome.recorded` and `outcome.risk_materialized` feed:
1. `analytics` — precision/recall by pattern, now weighted by real consequence
2. The correction loop (Strategy §C.9) — patterns whose findings never materialize across many
   outcomes are candidates for severity downgrade; findings that materialize but were never flagged
   are candidates for new patterns
3. The eval gold set — a materialized finding on a lost or loss-making bid is exactly the
   "loss-maker" case the Build Doc §19 scorecard requires

**The loop proposes; a human approves.** Rulepacks are never auto-mutated (Build Doc §2.4).

### Historical scope patterns (TS-319)
`outcomes.historical_scope_patterns` reads past `scope_gap` findings produced by
`boq` for the workspace, excluding the current opportunity. It groups them by
category and returns a compact list of patterns used by the BOQ engine to suggest
missing-scope items. The data stays workspace-scoped and is read from the shared
`findings` store via `findings.store_factory`.

### Privacy
Outcome data is commercially sensitive — it reveals a firm's win rate and pricing. It is
workspace-scoped, never contributes to the shared `marketdata` graph, and never appears in any
cross-tenant aggregate. Any future benchmarking product built on it requires explicit opt-in and
k-anonymity thresholds.

## Acceptance criteria

1. A bid outcome can be recorded, updated, and read, scoped to the workspace.
2. Prefill from the public award record works where a tender reference matches, and degrades silently
   to manual entry where it does not.
3. Marking a finding materialized emits `outcome.risk_materialized`.
4. `analytics` reflects outcomes in pattern accuracy.
5. Outcome data never leaves the workspace — asserted by a cross-tenant test.
6. Money in minor units with explicit currency.
7. Disabling `marketdata` leaves outcome recording fully functional (manual path).
8. No rulepack is mutated automatically by any outcome.
9. `GET /api/outcomes/metrics/margin-protected` returns a deterministic workspace snapshot and
   excludes unreviewed findings.
10. Settled claim `recovered_amount_minor` is captured and added to the `margin_protected` total (TS-269).
11. `GET /api/outcomes/opportunities/{id}/scope-patterns` returns historical `scope_gap` categories
    from past opportunities, excluding the current one, and includes a per-category historical count
    (TS-319).

## Out of scope

- Cross-tenant benchmarking (requires separate opt-in design and k-anonymity)
- Automatic rulepack mutation
- Inferring outcomes from behaviour without user confirmation
