# `marketdata` — Employer Behaviour Graph — Spec

**Status:** employer context on findings implemented (TS-200); P0 harvest adapters shipped (TS-197)
**Requirement refs:** `docs/TenderShield_Market_Strategy_2026.md` §A.2, §C.1, §B.2 (moat class 1)
**Task refs:** TS-195 – TS-200

## Purpose

Turn public procurement records into a queryable graph of **how each awarding authority actually
behaves** — bidder counts, award prices against estimate, award latency, retender rate, repeat
winners — and join it to risk findings so the product can say *"this clause is risky, and here is
what happens when this employer uses it"* rather than *"this clause is risky."*

This is the product's primary data moat (Strategy §B.2 class 1). It is built entirely from public
sources and requires no customers.

## Public interface

**Capabilities published**
- `marketdata.employer_profile` — aggregates for an employer family/division
- `marketdata.comparable_awards` — awards comparable to an opportunity (scope, value band, region)
- `marketdata.price_benchmark` — L1-to-estimate distribution for a comparable set
- `marketdata.award_prefill` — one-click-confirm prefill payload for `outcomes` from a tender ref
- `marketdata.employer_context_for_family` — employer profile block for findings/reports

**Capabilities consumed (soft)**
- `findings.store` — to annotate risk findings with employer context
- `rulepacks.loader` — employer-family definitions and precedence data

**Events emitted**
- `marketdata.profile_updated` — an employer profile's aggregates changed materially
- `marketdata.harvest_completed` — a harvest cycle finished, with counts

**Events consumed**
- `opportunity.created` — opportunistically warm the profile cache for that employer

**API routes** (all workspace-scoped, read-only)
- `GET /api/marketdata/employers/{family}/profile`
- `GET /api/marketdata/opportunities/{id}/comparables`
- `GET /api/marketdata/opportunities/{id}/benchmark`
- `GET /api/marketdata/opportunities/{id}/employer-context`

## Data owned

- `md_employers` — resolved employer identity: `family` (CPWD, NHAI, `<state>_PWD`), `division`,
  `region`, aliases, resolution confidence
- `md_tenders` — OCDS-shaped harvested tender records (see `specs/eval-at-scale.md` §2.1)
- `md_awards` — winner, award value (minor units + currency), bidder count, award date
- `md_profiles` — materialized per-employer aggregates with sample sizes and computed-at timestamps
- `md_harvest_runs` — provenance: source, adapter version, fetched_at, counts, errors

**Not workspace-scoped.** This is reference data shared across all tenants. It therefore contains
**no customer data of any kind**, and the module must never write tenant data into these tables.

## Behavior

### Harvest
Reuses the adapters specified in `specs/eval-at-scale.md` §2.2 — one corpus, two consumers (the eval
harness and this module). Harvest rules in §2.3 of that spec apply in full: robots.txt, rate limits,
public records only, never behind authentication.

**TS-198 implemented:** `employer_families.yaml` in the active pack drives a deterministic
normalization pipeline in `marketdata/resolution.py`. `MarketDataStore.resolve_tender_buyer` links
harvested tenders to `md_employers` with a published confidence score; unresolved portal names are
never guessed into a family.

**TS-199 implemented:** `aggregates.py` materializes per-employer stats into `md_profiles` with
`MIN_SAMPLE_SIZE = 12` suppression. `comparables.py` returns the filter definition alongside results.

### Employer resolution
Portal buyer names are inconsistent (`"E.E., PWD Div-II, Pune"`). Resolution is a deterministic
normalization pipeline — casefold, expand known abbreviations from rulepack data, strip honorifics,
match against a curated alias table — producing `family + division + region` with a confidence score.
**Unresolved buyers are stored unresolved, never guessed into a family.**

### Aggregates
Computed deterministically (never LLM):

| Aggregate | Definition |
|---|---|
| `bidder_count_p50/p90` | Distribution of qualified bidders |
| `l1_to_estimate_pct` | (award value − estimate) ÷ estimate, distribution |
| `award_latency_days` | Award date − bid opening date |
| `retender_rate` | Share of tenders followed by a matching re-issue |
| `winner_concentration` | HHI over winners in the comparable set |

### Suppression rule
No aggregate is returned below a minimum sample size (`assumption:` n ≥ 12). Below it the API
returns `insufficient_data` with the actual n. **A weak statistic is worse than no statistic** —
it is exactly the kind of confident-but-wrong output that ends accounts (Build Doc §12.1).

### Comparable-set construction
Deterministic filter: same employer family (optionally same division), overlapping classification,
value within a configurable band, award date within a lookback window. The filter used is returned
alongside the result so the user can see what "comparable" meant.

### Degradation
If `marketdata` is disabled or a profile is unavailable, risk findings render exactly as they do
today, with no employer context block and a logged warning. No route, no report, and no other module
may hard-depend on it (`CLAUDE.md` §2).

## Acceptance criteria

1. Harvest produces normalized `md_tenders`/`md_awards` with full provenance for ≥3 sources.
2. Employer resolution reports confidence; unresolved buyers remain unresolved.
3. Aggregates are deterministic — identical input produces byte-identical output.
4. Sample-size suppression is enforced and covered by a test.
5. `GET /…/comparables` returns the filter definition used to build the set.
6. Money is stored in minor units with an explicit currency (`CLAUDE.md` §4).
7. Disabling the module leaves every other feature working (architecture test).
8. No tenant data is written to any `md_*` table; enforced by test.
9. Every harvested record carries `source_url`, `fetched_at`, adapter name and version.

## Out of scope

- Predicting a specific competitor's bid for a specific tender (adversarial, and legally fraught)
- Any use of customer-supplied documents or outcomes in the shared graph — private outcomes live in
  `outcomes` and are workspace-scoped
- Selling raw harvested documents; the graph exposes aggregates and citations, not redistributed packs
