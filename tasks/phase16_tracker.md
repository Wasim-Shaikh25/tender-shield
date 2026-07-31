# Phase 16 — Defensibility, Domain-Agnosticism & Scale Validation — Tracker

**Requirement source:** `docs/TenderShield_Market_Strategy_2026.md`
**Specs:** `specs/eval-at-scale.md`, `specs/modules/marketdata.md`, `specs/modules/pricing-intel.md`,
`specs/modules/express-report.md`, `specs/modules/outcomes.md`
**Backlog:** `tasks/backlog.md` §Phase 16 (TS-195 – TS-234)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Move the product from *"an LLM reads your tender"* — a position being consolidated by
Trimble/Procore/Autodesk — to four things a general-purpose AI structurally cannot do: a proprietary
employer graph, deterministic money math, an accountability chain, and encoded workflow.

**Phase non-goal.** Features that map to no moat class in Strategy §B.2. If a proposed task cannot
name its moat class, it is out of scope for Phase 16.

---

## Moat-class map (every task must have one)

| Class | Meaning | Task groups |
|---|---|---|
| 1 | Proprietary data an LLM has never seen | 16.A `marketdata`, 16.D `outcomes`, TS-218 correction loop |
| 2 | Deterministic computation at LLM-hostile scale | 16.B `pricing-intel`, TS-217 contradictions |
| 3 | Accountability a model cannot carry | TS-219 reproducibility, TS-213 unreviewed-export handling |
| 4 | Workflow position / switching cost | TS-220 pack SDK, TS-221/222 packs, TS-216 outcome prefill |
| — | Revenue lane (enables the above to be sold) | 16.C `express` |
| — | Proof (measures whether any of it works) | 16.H eval at scale |

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Measure before building** | TS-223 ✅, TS-226 ✅, TS-230 ✅ | Cost-per-review p50/p95 known; M1 invariants run on the existing 20-tender smoke slice | **done** |
| **1** | **Corpus** | TS-224 ✅, TS-225, TS-197 | ≥1,000 tenders harvested across ≥3 sources with provenance; legality reviewed per adapter | in-progress |
| **2** | **Prove correctness at scale** | TS-227, TS-229, TS-231, TS-232 | M1 100% pass on 1,000 tenders; M2 deadline match ≥95%; CI blocking on smoke slice | todo |
| **3** | **Graph** | TS-195, TS-196, TS-198, TS-199, TS-200 | Employer profiles queryable with suppression; comparable-set filter disclosed | todo |
| **4** | **Money math** | TS-201–TS-207 ✅ | Loadings byte-identical on re-run; no LLM dependency in module; export gate enforced | **done** |
| **5** | **Revenue lane** | TS-208–TS-214 | Stranger → teaser → pay → report, webhook-only activation, watermarked unreviewed export | todo |
| **6** | **Loop + accountability** | TS-215, TS-216, TS-217 ✅, TS-218, TS-219 | Outcomes recorded; contradictions detected; findings reproducible; corrections proposed not applied | in-progress |
| **7** | **Domain ladder** | TS-220 ✅, TS-221 ✅, TS-222 (gated) | Third party can author a pack; 4 new trades ship as YAML only | **done** |
| **8** | **Backtest + gold set** | TS-228, TS-233 | Time-split L1 backtest baseline published; 50-tender gold set annotated | todo |

### Why this order

**Sprint 0 before everything.** Cost per review is not currently instrumented, so no pricing decision
in Strategy §F is safe and no scale run is affordable to launch blind. Measure first.

**Corpus before graph and before pricing.** Both depend on harvested data. Building `marketdata`
aggregates before there is a corpus produces code with nothing to run against.

**Correctness (Sprint 2) before revenue (Sprint 5).** The Express lane sells reports to strangers with
no reviewer in the loop. Shipping that before M1 invariants pass on 1,000 real tenders is the single
highest-liability sequencing error available in this plan.

**Graph before money math.** Rate benchmarking and loadings are far more credible with employer
context, and the comparable-set machinery is shared.

---

## Dependency graph (critical path in bold)

```
**TS-223 cost instrumentation**
        │
**TS-224 corpus schema + harvester**
        │
   ┌────┴─────────────────┬──────────────────┐
**TS-225 adapters**    TS-197 (P0 adapters, shared)
        │
   ┌────┴───────────────────────────┬─────────────────┐
**TS-226 M1 invariants**      TS-227 M2        TS-229 M4
        │                            │                │
**TS-230 bulk runner** ───────────────┴────────────────┘
        │
**TS-231 report + regression** ── TS-232 CI gates
        │
   ┌────┴──────────┐
TS-195..200        TS-228 backtest ── needs award subset
 marketdata
        │
   ┌────┴──────────┬──────────────┐
TS-201..207     TS-215/216      TS-217 ✅/218/219
 pricing        outcomes         loop + accountability
        │
TS-208..214 express  ← gated on Sprint 2 exit
        │
TS-220..222 domain ladder
        │
TS-233 gold set (parallel from Sprint 1 onward)
```

`TS-233` (human gold set) has no code dependencies and should run in parallel from Sprint 1 — it is
calendar-bound, not engineering-bound.

---

## Feature tracker

| ID | Feature | Module | Moat | Priority | Status | Acceptance gate | Blockers |
|---|---|---|---|---|---|---|---|
| TS-195 | `marketdata` scaffold | `marketdata` | 1 | P1 | **done** | Boots with module disabled; no hard deps | — |
| TS-196 | Corpus schema (non-tenant) | `marketdata` | 1 | P1 | todo | No tenant data in `md_*`, test-asserted | TS-224 |
| TS-197 | P0 adapters (CPPP, state NIC) | `marketdata` | 1 | P0 | todo | Legality review in docstring; rate-limit compliant | — |
| TS-198 | Employer resolution | `marketdata` | 1 | P1 | todo | Confidence published; unresolved stays unresolved | TS-196 |
| TS-199 | Aggregates + suppression | `marketdata` | 1 | P1 | todo | n ≥ 12 suppression tested; deterministic | TS-198 |
| TS-200 | Employer context on findings | `marketdata` | 1 | P2 | todo | Degrades to today's behaviour when disabled | TS-199 |
| TS-201 | `pricing` scaffold | `pricing` | 2 | P1 | **done** | No LLM client import, test-asserted | — |
| TS-202 | `price_impact` schema + formulas | `rulepacks` | 2 | P1 | **done** | Worked-example tests per formula | TS-201 |
| TS-203 | Bid loading sheet | `pricing` | 2 | P1 | **done** | Missing input → no loading, never a default | TS-202 |
| TS-204 | SOR/DSR pack data | `rulepacks` | 2 | P2 | **done** | Versioned, sourced, confidence-flagged | — |
| TS-205 | Rate benchmarking | `pricing` | 2 | P2 | **done** | Headline from code matches only | TS-204 |
| TS-206 | Cashflow model | `pricing` | 2 | P1 | **done** | `assumptions[]` always present | TS-201 |
| TS-207 | Review gate on pricing artifacts | `pricing` | 3 | P0 | **done** | Export blocked pre-approval; excluded from Express | TS-203 |
| TS-208 | `express` scaffold | `express` | — | P1 | **done** | Ephemeral workspace backing; isolation reused | — |
| TS-209 | Anonymous session lifecycle | `express` | — | P1 | todo | Pre-buffer size caps; non-enumerable tokens | TS-208 |
| TS-210 | Teaser renderer | `express` | — | P1 | todo | Full deadline wall + 2 cited findings | TS-209 |
| TS-211 | Server-owned prices + guest checkout | `billing` | — | P0 | todo | Client-supplied amount rejected | TS-209 |
| TS-212 | Webhook-only activation | `billing` | — | P0 | todo | Redirect-without-webhook test returns locked | TS-211 |
| TS-213 | `unreviewed` export variant | `export` | 3 | P0 | todo | Watermark all formats; ack logged w/ IP + version | TS-212 |
| TS-214 | Anti-abuse + retention + claim | `express` | — | P1 | todo | Teaser dedupe by document hash; deletion job tested | TS-210 |
| TS-215 | Outcome capture | `outcomes` | 1 | P1 | todo | Workspace-scoped; never in shared graph | — |
| TS-216 | Award-record prefill | `outcomes` | 4 | P2 | todo | Degrades to manual when no match | TS-199, TS-215 |
| TS-217 | Contradiction engine | `crossref` | 2 | P1 | **done** | Both sides keep citations; precedence from pack | — |
| TS-218 | Correction loop | `rulepacks` | 1 | P2 | todo | Proposes only; never auto-mutates a pack | TS-215 |
| TS-219 | Reproducibility chain | `findings` | 3 | P0 | **done** | Deterministic stages byte-identical on re-run | — |
| TS-220 | Pack SDK | `packsdk` | 4 | P2 | **done** | Third party authors + validates a pack end-to-end | — |
| TS-221 | Rung-1 trade checklists | `rulepacks` | 4 | P2 | **done** | 4 trades, YAML only, zero code change | TS-220 |
| TS-222 | Supply-and-erection patterns | `rulepacks` | 4 | P3 | todo | Gated on a customer asking (Strategy §D.2) | TS-221 |
| TS-223 | Cost instrumentation | `observability` | — | P0 | **done** | p50/p95 cost per review; token ceiling test | — |
| TS-224 | Corpus schema + harvester | `evalcorpus` | — | P0 | **done** | Adapter interface + sha256 + provenance | — |
| TS-225 | Adapters (4 sources) | scripts | — | P0 | todo | Legality review recorded per adapter | TS-224 |
| TS-226 | M1 invariants | `evalinvariants` | — | P0 | **done** | 100% pass required; failure blocks release | TS-224 |
| TS-227 | M2 metadata agreement | evals | — | P1 | todo | Triage into miss/wrong/portal-wrong | TS-225 |
| TS-228 | M3 backtest | evals | 1 | P2 | todo | Time-based split, not random | TS-199 |
| TS-229 | M4 metamorphic | evals | — | P1 | todo | 5 invariance properties | TS-226 |
| TS-230 | Bulk runner | `evalrunner` | — | P0 | **done** | Resumable, sharded, cost-guarded, 1,000+ unattended | TS-226 |
| TS-231 | Report + regression diff | `evalrunner` | — | P1 | **done** | Scorecard readable without raw data | TS-230 |
| TS-232 | CI gates | CI | — | P1 | todo | Smoke blocks PRs; >2pt drop blocks change | TS-231 |
| TS-233 | Human gold set (50) | evals | — | P1 | todo | Slice table filled; annotated per §19 | — |
| TS-294 | `Finding.document_id` | `findings` | 3 | P2 | todo | Migration + writers updated | TS-226 |
| TS-295 | `Finding.currency` | `findings` | 3 | P1 | todo | Explicit ISO 4217 alongside amount_exposure | TS-226 |
| TS-296 | `Finding.facts` + `Opportunity.contract_value_minor` | `findings` | 3 | P2 | todo | Real fact sourcing for pricing.loading | TS-203 |
| TS-234 | North-star metric — margin protected | `outcomes` | 1 | P0 | todo | Deterministic; excludes speculative value; grows with Phases 18–19 | TS-203, TS-215 |

---

## Phase 16 exit gates

Phase 16 is complete when **all** hold:

1. **M1 structural invariants pass 100%** on a ≥1,000-tender multi-country corpus.
2. **M2 deadline and value extraction ≥95%** exact match against portal metadata.
3. **Cost per completed review is known** (p50 and p95) and is under 25% of the lowest Express tier.
4. **Employer profiles are queryable** for at least one Indian employer family with suppression enforced.
5. **Pricing outputs are byte-identical on re-run** and carry no LLM dependency.
6. **Express lane transacts end-to-end** with webhook-only activation and watermarked unreviewed export.
7. **The 50-tender gold set is annotated**, and gold-set critical recall meets the Build Doc §19.5 bar.
8. **A trade pack ships as YAML only**, proving the domain ladder.

## Kill conditions (Strategy §H)

- Critical-clause recall < 75% on the gold set after two tuning rounds → stop and diagnose before
  building anything further.
- Any invented quote reaching a customer → halt the Express lane immediately.
- Fully-loaded p95 cost > 25% of the lowest Express tier → repricing or re-architecture before launch.
- Saudi/UAE work starting before the India accuracy gate is green → scope-reflex violation
  (Build Doc §12.6).

## Standing constraints

- **Numbers never from the LLM** (`CLAUDE.md` §4) — `pricing-intel` and `marketdata` are asserted
  LLM-free by test.
- **Every module degrades gracefully** when any other is disabled (`CLAUDE.md` §2).
- **Money in minor units with explicit currency** — multi-jurisdiction makes an implicit default a bug.
- **One workspace, many jurisdictions** — jurisdiction is a property of the opportunity, not the
  workspace (Strategy §E.2).
- **Public records only in the corpus.** No customer document, no authenticated source.
