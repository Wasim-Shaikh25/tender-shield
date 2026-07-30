# TenderShield AI — Combined Roadmap, Stage 1 → Stage 5
### Reconciling the founding research, the build doc, and what actually exists

**Document version:** 1.0 · 30 July 2026
**Status:** Master roadmap. Supersedes the phase sequencing in the Build Doc §10 from Phase 16 onward.
**Requirement sources (all three, reconciled here):**
- `TenderShield_AI_Architecture_and_Market_Research.pdf` (20 Jul 2026) — the founding research ("Research Doc")
- `docs/TenderShield_Full_Build_Doc.md` (22 Jul 2026) — the engineering blueprint ("Build Doc")
- `docs/TenderShield_Market_Strategy_2026.md` (30 Jul 2026) — defensibility and market research ("Strategy Doc")

**Disclaimer:** Product/engineering planning document. Not legal, quantity-surveying or investment
advice. Revenue figures are hypotheses drawn from Research Doc §10.1 and are marked as such.

---

## PART 1 — WHERE WE ACTUALLY ARE

The Research Doc defines a **five-stage value ladder** (§Executive Summary, p2). Mapping the
codebase against it:

| Stage | Customer outcome | Research Doc commercial model | Built? |
|---|---|---|---|
| **1. Pre-bid assessment** | Fewer underpriced or contractually dangerous bids | Per-tender fee + team subscription | ✅ **Substantially complete** |
| **2. Baseline lock** | Structured contract/BOQ baseline with traceable assumptions | Project activation fee | ⚠️ **Partial** — `baseline` module exists (932 LOC); handover pack, watchlists, notice rules, cost codes and approval matrix missing |
| **3. Change & notice control** | Changes detected, notices not missed, evidence preserved | **Per-project recurring subscription** | ❌ **Not built** |
| **4. Claims workspace** | Draft claim packages and commercial exposure dashboard | **Premium module** | ❌ **Not built** |
| **5. Portfolio intelligence** | Benchmarks across projects, clauses, clients, outcomes | Enterprise annual contract | ❌ **Not built** |

**The structural problem this exposes:** stages 1 and 2 are *transactional*. Stages 3, 4 and 5 are
*recurring*. Every line of the 24,500-line backend sits in the transactional half.

---

## PART 2 — THE MONEY LADDER

Using the Research Doc's own pricing hypotheses (§10.1), for a single mid-market general contractor
bidding ~10 tenders/month with ~8 active projects:

| Stage | Pricing basis (Research Doc §10.1) | Annual value from **one** customer | Churn profile |
|---|---|---|---|
| 1. Pre-bid | ₹25,000/mo Pro (or ₹7,500/tender) | ~₹3 L | **High** — cancellable any month; value stops when bidding stops |
| 2. Baseline lock | Project activation fee | ~₹1–2 L | Event-driven |
| **3. Change & notice** | **₹10,000–75,000 per project/month** | **~₹38 L** (8 projects × ₹40k × 12) | **Very low** — switching mid-project is unthinkable |
| **4. Claims** | Premium module | Variable, high | Very low |
| 5. Portfolio | Enterprise annual | Contract-scale | Annual |

`assumption:` figures are illustrative arithmetic over the Research Doc's stated price bands, not
market facts. Validate in discovery.

**The conclusion is stark: stage 3 is worth roughly an order of magnitude more per customer than
stage 1, and it is far stickier.** Pre-bid is how you get in the door. Project commercial control is
the business.

There is also a retention asymmetry that matters more than the revenue multiple:

- A contractor can stop using pre-bid review the month they stop bidding. Nothing breaks.
- A contractor **cannot** stop using change-and-notice control mid-project. The notice register, the
  evidence chain and the deadline countdown are live commercial infrastructure. Removing them
  mid-contract destroys entitlement.

That is switching cost (Strategy Doc moat class 4), and it only exists from stage 3 onward.

---

## PART 3 — GAP ANALYSIS: WHAT THE RESEARCH DOC SPECIFIED AND WE NEVER BUILT

Everything below is in the founding research and absent from both the codebase and the Phase 16 plan.

### 3.1 Missing capability blocks

| Research Doc ref | Capability | Why it matters |
|---|---|---|
| §4.E | **Baseline → project controls**: convert tender risks into watchlists; define notice rules, correspondence addresses, authorized representatives, approval matrix; create cost codes mapped to BOQ and variation categories | The bridge from stage 1 to stage 3. Without it there is nothing for change detection to compare against |
| §4.F | **Change & variation detection**: compare new drawings/specs/instructions against baseline; capture signals from RFIs, emails, minutes, site instructions, daily reports; potential-variation inbox; site confirmation workflow; notice deadline countdown and escalation | Stage 3 — the recurring revenue engine |
| §4.G | **Claims & notice workspace**: contract-specific notice templates populated with verified facts; chronology builder; evidence checklist; quantum workspace; delay-event register; issue→response→negotiation→settlement tracking | Stage 4 |
| §4.H | **Commercial control tower**: at-risk revenue, unnotified change, submitted/certified/rejected value, ageing, cash exposure, risk-adjusted forecast at completion, client response-time analytics | Stage 5 |
| §4.I | **Integrations**: Autodesk, Procore, Aconex, SharePoint/OneDrive, email, ERP, scheduling | Research Doc §12.3 says start with upload/export, add APIs after proven value — correctly deferred, but must not be forgotten |
| §13 | **Subcontract control**: flow-down clause comparison, subcontract scope-gap checks, back-to-back notice calendar, **pay-when-paid exposure flags** | Directly serves the specialty-contractor persona, which is the cheapest segment to sell to |
| §13 | **Payment control**: RA/progress bill checklist, certification variance, retention and security release dates, ageing and collection actions | Cash is the mid-market contractor's actual pain |
| §13 | **Site evidence**: voice-to-daily-record, geotagged photos, labor/plant/daywork capture, offline mobile sync | Prerequisite for stage 4 per the Research Doc's own kill gate |
| §8.3 | **Advisor Edition**: multi-client separation, review queues, branded reports, evidence export | The partner channel with the best CAC in the plan |

### 3.2 Missing concept: evidence continuity

The Research Doc's closing sentence (§14):

> *"Your most valuable product is the chain of evidence from original commercial promise to actual
> project change — and the timely action that chain enables."*

This is not a feature; it is the product's spine, and nothing in the codebase implements it. It
requires:

- **Evidence-completeness scoring** per potential event (§2.1: *"each potential event has an
  evidence-completeness score and a list of missing contemporaneous records"*)
- **Chain of custody** on every evidence item (§6.3 canonical data model: `Evidence` entity with
  `chain of custody`, `event link`, `completeness`)
- An unbroken link: **tender clause → baseline obligation → change event → notice → evidence →
  claim → outcome**

The Phase 16 reproducibility chain (TS-219) covers half of this — provenance *within* a finding. The
other half is provenance *across* the project lifecycle, and it is what makes the graph valuable.

### 3.3 Missing metric: the north star

Research Doc §12.1:

> **"Verified contractor margin protected"** — accepted risk allowances + approved variations/claims
> linked to TenderShield evidence, excluding speculative value.

Not instrumented anywhere. `analytics` measures precision, recall and review dispositions — engine
quality, not customer value. This is the number that makes a case study (§10.2), justifies renewal,
and answers "why should we pay for this."

### 3.4 Missing operating metrics (Research Doc §12.2)

| Category | Metrics | Status |
|---|---|---|
| Adoption | Tenders processed, weekly active reviewers, active projects, changes reviewed | Partial |
| Quality | Citation precision, critical-clause recall, false positives, reviewer edit/rejection rate | Partial (`analytics`) |
| Workflow | Time to first review, notice timeliness, evidence completeness, claim cycle time | **None** |
| Economics | Paid conversion, gross margin, CAC payback, project retention, expansion revenue | **None** |
| Customer outcome | Risks priced, bad bids declined, omissions corrected, value notified/certified, hours saved | **None** |

---

## PART 4 — THE RESTRUCTURED PHASE PLAN

Six phases, each mapped to a Research Doc stage, each with an **unlock gate** taken from the
Research Doc's own kill/continue criteria (§12.4).

> **On gates.** The Research Doc's gates exist because building stage *N+1* before stage *N* is
> adopted produces software nobody uses. They are stated here as **unlock conditions**, visible and
> deliberate. Overriding one is a decision the founder is entitled to make — but it should be a
> decision, not an accident. Every override should be recorded in the tracker.

| Phase | Stage | Theme | Tasks | Unlock gate (Research Doc §12.4) |
|---|---|---|---|---|
| **16** | 1 | Defensibility, domain-agnosticism, scale validation | TS-195 – TS-234 | — (in progress) |
| **17** | 2 | Baseline Lock & Handover completion | TS-235 – TS-242 | Phase 16 exit gates |
| **18** | 3 | **Change & Notice Control** — first recurring revenue | TS-243 – TS-256 | *"Two projects use baseline weekly"* |
| **19** | 4 | Claims & Evidence Workspace | TS-257 – TS-270 | *"Do not build claims valuation until users capture contemporaneous evidence in the platform"* + *"Document at least five real events before work completion"* |
| **20** | 5 | Commercial Control Tower & Portfolio | TS-271 – TS-280 | Phase 19 in production use |
| **21** | — | Integrations, Subcontract Control & Advisor Edition | TS-281 – TS-292 | *"Integration marketplaces only after workflow proof"* (§10.2) |

### Why this order

**Phase 17 before 18.** Change detection compares against a baseline. The `baseline` module freezes
documents but does not produce the *controls* — notice rules, watchlists, cost codes, approval matrix
— that stage 3 consumes. Building change detection first gives it nothing to diff against.

**Phase 18 is the priority phase of the whole plan.** It converts the product from transactional to
recurring, it creates real switching cost, and it is where the Research Doc puts per-project
subscription revenue. Everything in Phase 16 exists to make Phase 18 credible.

**Phase 19 gated on evidence capture.** The Research Doc is explicit: do not build claims valuation
until contemporaneous evidence is actually being captured. A claims workspace fed by reconstructed
evidence produces exactly the "slow, expensive and disputable" claims the product exists to prevent
(§1.1).

**Phase 21 last.** Integrations are a force multiplier on a workflow people already use, and dead
weight on one they do not.

---

## PART 5 — THE THROUGH-LINE: EVIDENCE CONTINUITY

Every phase from 17 onward extends a single chain. This is the architecture's spine and the reason
the phases cannot be reordered arbitrarily:

```
tender clause  →  baseline obligation  →  change event  →  notice  →  evidence  →  claim  →  outcome
   (P1 ✅)          (P17)                  (P18)           (P18)      (P18/19)     (P19)     (P16 ✅ TS-215)
      │                │                      │               │           │           │          │
      └────────────────┴──────────────────────┴───────────────┴───────────┴───────────┴──────────┘
                        every link carries provenance, citation and chain of custody
                          (Phase 16 TS-219 reproducibility chain extended across the lifecycle)
```

Note that outcome capture (TS-215, Phase 16) is the **far end** of the chain being built before the
middle. That is deliberate and correct: it is cheap, it feeds the correction loop immediately from
pre-bid data, and it means the chain closes the moment the middle links land.

---

## PART 6 — METRICS

### 6.1 North star — instrument in Phase 16 (TS-234)

**Verified contractor margin protected** = accepted risk allowances + approved variations/claims
linked to TenderShield evidence, **excluding speculative value**.

Computation is deterministic and staged as the ladder is climbed:

| Component | Available from |
|---|---|
| Accepted risk allowances (from bid loadings) | Phase 16 (TS-203) |
| Declined bad bids × modelled exposure avoided | Phase 16 (TS-215 outcomes) |
| BOQ defects corrected pre-submission × value | Phase 16 |
| Variations notified on time × approved value | Phase 18 |
| Claims recovered with TenderShield evidence | Phase 19 |

The metric exists from Phase 16 with the components then available, and grows as later phases land.
"Excluding speculative value" is a hard rule — only *approved* or *accepted* values count.

### 6.2 Operating metrics — the four missing categories

Workflow, economics and customer-outcome metrics (Research Doc §12.2) are added incrementally with
the phase that makes each measurable. Tracked in `tasks/roadmap_tracker.md`.

---

## PART 7 — WHAT COULD BREAK THIS

| Risk | Source | Guard |
|---|---|---|
| Building stage 3 before anyone adopts stage 1 | Research Doc §12.4 | Unlock gates, visible in the tracker; overrides recorded |
| Claims workspace fed by reconstructed evidence | Research Doc §12.4 | Phase 19 gated on real evidence capture in Phase 18 |
| Scope reflex — six phases written, all started | Build Doc §12.6 | One phase in flight at a time; the tracker shows exactly one `in-progress` phase |
| Recurring revenue assumed rather than validated | Research Doc §10.1 ("hypotheses, not market facts") | Price bands re-tested with the first three project-control customers |
| Evidence chain broken by a missing link | Research Doc §14 | Chain-integrity test: every claim traces to a notice, event, baseline obligation and tender clause |
| Express lane becomes the only thing anyone buys | Research Doc §12.4 (*"stop or reposition if customers value only one-off summaries"*) | Express → subscription conversion rate instrumented in TS-214 |

---

## Appendix — Reconciliation notes

Three points where the founding research and later documents diverge, resolved here:

1. **The AI assistant** appears nowhere in the Research Doc's capability architecture (§4 A–I). It
   was introduced in Build Doc §8 and built in Phase 1. Build Doc §13.5 itself said *"not the
   assistant."* It exists; it is not load-bearing; no further investment until stage 3 ships.
2. **Domain scope.** The Research Doc was never civil-only — §3.3 targets specialty, general, EPC
   and consultancy segments; §3.4 and §8.2 specify configurable contract and jurisdiction packs from
   the start. The civil narrowing happened in `rulepacks/`, not in strategy. Strategy Doc Part D
   corrects this and is consistent with the founding research.
3. **Geography.** Strategy Doc Part E sequences India → Saudi → UAE. Research Doc §12.4 requires a
   local specialist **and** a paid design customer before any jurisdiction expansion. The sequence
   stands; the gate stands with it.

*End of document — v1.0.*
