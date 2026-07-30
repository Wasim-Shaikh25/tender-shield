# `pricing-intel` — Risk-to-Price, Rate Benchmarking & Cashflow — Spec

**Status:** draft
**Requirement refs:** `docs/TenderShield_Market_Strategy_2026.md` §C.2, §C.3, §C.4, §B.2 (moat class 2)
**Task refs:** TS-201 – TS-207

## Purpose

Convert commercial risk into the numbers an estimator actually uses: a **rupee loading per finding**,
a **rate variance against the published Schedule of Rates**, and a **month-by-month funding curve**.

This is the bridge from "here is your risk register" to "here is what it does to your bid." Every
output in this module is **deterministic arithmetic over verified facts — never LLM** (`CLAUDE.md` §4,
Build Doc §6.4).

## Public interface

**Capabilities published**
- `pricing.bid_loading` — per-finding price impact for an opportunity
- `pricing.rate_benchmark` — BOQ rates vs schedule-of-rates variance
- `pricing.cashflow` — funding curve, peak requirement, financing cost

**Capabilities consumed (soft)**
- `findings.store` — accepted findings only
- `boq.items` — normalized BOQ lines
- `timeline.milestones` — milestone dates for the cashflow profile
- `rulepacks.loader` — `price_impact` blocks, SOR data, index series
- `marketdata.price_benchmark` — optional employer context on the benchmark

**Events emitted**
- `pricing.loading_computed`, `pricing.cashflow_computed`

**API routes**
- `GET /api/pricing/opportunities/{id}/loading`
- `GET /api/pricing/opportunities/{id}/rate-benchmark`
- `POST /api/pricing/opportunities/{id}/cashflow` (body carries cost of capital + overrides)

## Data owned

- `pi_loadings` — one row per finding: basis, formula id, inputs snapshot, computed amount (minor
  units + currency), rulepack version
- `pi_rate_matches` — BOQ item ↔ schedule item, match method, match confidence, variance
- `pi_cashflow_runs` — inputs, assumptions used, resulting curve

## Behavior

### 1. Risk-to-price loading

Each risk pattern gains an optional `price_impact` block in its rulepack YAML:

```yaml
price_impact:
  basis: percent_of_contract_value   # | per_unit | lump_sum
  formula: escalation_unhedged        # named, versioned, implemented in code
  inputs: [project_duration_months, index_series]
  confidence: unvalidated
```

Rules:
- Inputs come **only** from facts that passed quote verification, or from public index series.
  A missing input means **no loading is produced** — never a default.
- Formulas are named, versioned, implemented in deterministic code, and unit-tested against worked
  examples. The LLM never computes, selects, or adjusts a loading.
- Every loading renders with its formula and inputs visible.
- Loadings are computed **only from accepted findings** (post-review), never from proposed ones.

### 2. Schedule-of-Rates benchmarking

SOR data is versioned rulepack content: `rulepacks/<pack>/rates/<authority>/<year>.yaml`.

Matching is two-band and the band is always disclosed:

| Band | Method | Reported as |
|---|---|---|
| High confidence | Schedule item code present in the BOQ and matched exactly | `matched_by: code` |
| Indicative | Normalized description similarity above threshold | `matched_by: description` |
| Unmatched | Neither | `unmatched` — reported, never force-matched |

Output: per-item variance and a value-weighted portfolio variance computed over **code-matched items
only**. Description-matched items are shown separately and excluded from the headline number —
precision over coverage.

### 3. Cashflow / working capital

Deterministic model over: payment days and trigger, retention % and release schedule, mobilization
advance and recovery profile, PBG/EMD amounts and validity, milestone dates, user-supplied cost of
capital.

Outputs: monthly net position, **peak funding requirement and the month it occurs**, total financing
cost, and an explicit `assumptions[]` block naming every substituted default.

Missing facts never become silent defaults — each one appears in `assumptions[]` with what was
assumed and why.

## Guardrails (highest-liability module in the product)

1. **Reviewer gate.** Loadings and cashflow are artifacts and inherit the export gate — no export
   before review approval (Build Doc §11.4).
2. **Excluded from unreviewed Express tiers** (`specs/modules/express-report.md`).
3. **Never auto-applied** to BOQ rates or any submitted document. The output is advisory and is
   labelled indicative on every surface.
4. **Formula transparency is mandatory** — a loading whose formula cannot be shown is not displayed.
5. **Numbers never come from the LLM** — enforced by test: the module has no LLM client dependency.

## Acceptance criteria

1. Loadings are byte-identical on re-run for identical inputs and rulepack version.
2. A missing required input yields no loading plus a stated reason — never a defaulted value.
3. Headline rate variance uses code-matched items only; description matches are reported separately.
4. Unmatched BOQ items are reported as unmatched.
5. Cashflow output always includes a complete `assumptions[]` block.
6. All money in minor units with explicit currency.
7. The module imports no LLM client — asserted by test.
8. Loadings compute only from accepted findings.
9. Export of any pricing artifact is blocked without review approval.
10. Disabling the module leaves risk, BOQ and export fully functional.

## Out of scope

- Recommending a bid price or a margin
- Automatically adjusting BOQ rates
- Competitor-specific bid prediction
- Any pricing output in an unreviewed tier
