# `pricing-intel` — Risk-to-Price, Rate Benchmarking & Cashflow — Spec

**Status:** implemented (TS-296 closed — `Finding.facts` and `Opportunity.contract_value_minor` now source pricing loadings)
**Requirement refs:** `docs/TenderShield_Market_Strategy_2026.md` §C.2, §C.3, §C.4, §B.2 (moat class 2)
**Task refs:** TS-201 – TS-207

## Implementation notes (TS-201–207)

- **Package is `app/modules/pricing/`, not `pricing_intel` or `pricing-intel`.** The module loader
  (`app/main.py`) enforces `route prefix == package name == ModuleSpec.name`, and neither a hyphen
  nor most conceptual names survive that as Python identifiers. `pricing` matches this spec's stated
  routes (`/api/pricing/...`) exactly; `pricing_intel` would not.
- **`GET /rate-benchmark` is `POST` instead.** It carries a BOQ CSV body; a GET request body is
  unreliable across HTTP clients and proxies, and `boq/router.py`'s own `run_boq` already makes the
  same call for the same reason. `GET /loading` matches the spec as written; query parameters are
  optional overrides, and the endpoint defaults to the persisted opportunity contract value and
  finding facts.
- **`app/modules/boq/service.py`'s `BoqEngine` gained one method, `normalize_dataframe`** — the
  normalization half of `check_dataframe` split out so `pricing` can consume normalized BOQ rows via
  the already-published `boq.engine` capability, without a new registry entry and without importing
  `app.modules.boq` directly (`CLAUDE.md` §2).
- **Known limitation, not silently worked around:**
  1. `rulepacks/in-works/rates/` ships **empty by design** — see its README. A Schedule-of-Rates is
     authoritative regulatory data; fabricating even a plausible-looking rate would violate the
     product's own "numbers never invented" invariant. The loader and `benchmark()` both treat an
     empty/missing schedule as "everything unmatched," never an error.

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

All verified by `backend/tests/test_pricing.py` (31 tests).

1. ✅ Loadings are byte-identical on re-run for identical inputs and rulepack version.
2. ✅ A missing required input yields no loading plus a stated reason — never a defaulted value.
3. ✅ Headline rate variance uses code-matched items only; description matches are reported separately.
4. ✅ Unmatched BOQ items are reported as unmatched.
5. ✅ Cashflow output always includes a complete `assumptions[]` block.
6. ✅ All money in minor units with explicit currency.
7. ✅ The module imports no LLM client — asserted by a static AST-import-scan test, not just behavior.
8. ✅ Loadings compute only from accepted findings — enforced inside `compute_loadings` itself, not
   only by caller discipline.
9. ✅ Every route (`loading`, `rate-benchmark`, `cashflow`) is blocked with `409 review_incomplete`
   until the review gate passes — verified end to end through the real router, not just the service.
10. ✅ Disabling `pricing` leaves risk, BOQ and export fully functional (all deps are soft).

## Out of scope

- Recommending a bid price or a margin
- Automatically adjusting BOQ rates
- Competitor-specific bid prediction
- Any pricing output in an unreviewed tier
