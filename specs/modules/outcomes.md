# `outcomes` — Bid Outcome & Risk Materialization Capture — Spec

**Status:** draft
**Requirement refs:** Build Doc §1.1(9), §11.5; `docs/TenderShield_Market_Strategy_2026.md` §C.6, §C.9
**Task refs:** TS-215, TS-216

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

**Capabilities consumed (soft)**
- `findings.store` — to attach materialization to specific findings
- `marketdata.comparable_awards` — to prefill from the public award record

**Events emitted**
- `outcome.recorded` — consumed by `analytics` (accuracy) and the correction loop
- `outcome.risk_materialized` — a flagged risk actually bit

**API routes**
- `POST /api/outcomes/opportunities/{id}` — record/update outcome
- `POST /api/outcomes/findings/{id}/materialized` — mark a finding as materialized
- `GET  /api/outcomes/opportunities/{id}`

## Data owned

- `oc_bid_outcomes` — `opportunity_id`, result (`submitted|won|lost|declined|disqualified`),
  quoted value, L1 value where known, bidder count, decline reason, recorded_by, recorded_at
- `oc_risk_materialization` — `finding_id`, materialized (bool), impact amount (minor units +
  currency), narrative, recorded_at

All workspace-scoped with RLS, like every other tenant table (`CLAUDE.md` §4).

## Behavior

### Prefill, don't demand
Users will not fill in forms. On `opportunity.status` reaching a terminal state, attempt to match the
public award record via tender reference through `marketdata`, prefill result/winner/L1 value, and
ask for **one-click confirmation**. Manual entry is always available but is never the only path.

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

## Out of scope

- Cross-tenant benchmarking (requires separate opt-in design and k-anonymity)
- Automatic rulepack mutation
- Inferring outcomes from behaviour without user confirmation
