# TenderShield AI — Market Strategy, Defensibility & Value Features
### Research base and requirement source for Phase 16 (India → Saudi → UAE)

**Document version:** 1.0 · 30 July 2026
**Status:** Requirement source. Companion to `docs/TenderShield_Full_Build_Doc.md` (the "Build Doc").
Where this document and the Build Doc disagree on *scope sequencing*, this document supersedes for
Phase 16 only; the Build Doc remains source of truth for Phases 0–15 and for all product invariants
(§4 of `CLAUDE.md`).
**Disclaimer:** Product/engineering strategy document. Not legal, quantity-surveying, or investment
advice. Every market figure carries its source; figures without a source are marked `assumption:`.

---

## TABLE OF CONTENTS

- **Part A — Research base:** every source, what it gives us, and how it was verified
- **Part B — The defensibility thesis:** why "AI can do this" is the wrong frame, and what actually holds
- **Part C — Value features:** ranked, each with why / how / what-if
- **Part D — Domain-agnostic architecture:** the engine/pack split and the generalization ladder
- **Part E — Geographic sequencing:** India → Saudi → UAE, and why Europe is deferred
- **Part F — Business model:** subscription + the new pay-per-report lane
- **Part G — Profitability model:** unit economics and the instrumentation required to know them
- **Part H — Risks, what-ifs, and kill conditions**

---

## PART A — RESEARCH BASE

Every claim below was verified against a public source on 30 July 2026. Sources are listed so that
any pattern, threshold, or business assumption derived from them can be traced (`CLAUDE.md` §3,
Build Doc §14.1).

### A.1 The competitive landscape

| Finding | Source | Implication |
|---|---|---|
| Trimble signed an agreement to acquire **Document Crunch** (Apr 2026, closing Q2 2026); Document Crunch has been used on 10,000+ projects for contract risk, payment and compliance | [Trimble newsroom](https://news.trimble.com/2026-04-02-Trimble-to-Acquire-Document-Crunch-to-Add-AI-Powered-Risk-Management-and-Document-Compliance-to-Trimble-Construction-One-Project-Delivery-Ecosystem) | The category is validated and an incumbent is now armed. Do **not** compete on "AI reads your contract" |
| Procore acquired Datagrid (Jan 2026); Autodesk closed Rhumbix (Mar 2026) | [Construction Dive](https://www.constructiondive.com/news/trimble-acquire-document-crunch-contech/816630/) | Contech AI consolidation is active across all three majors. Their focus is the **post-award project lifecycle**, not pre-bid tender assurance |
| India already has a crowded **tender discovery + L1 prediction** segment: Bid India, IndianTenders, TenderDekho, gembid.help | [Bid India](https://bidindia.co.in/), [IndianTenders](https://www.indiantenders.in/contract-awards/) | Discovery and price-prediction alone is a contested commodity. **Risk + assurance is unoccupied. The combination is the wedge** |

**Conclusion.** Two occupied positions exist — *post-award project intelligence* (US majors) and
*pre-bid discovery/pricing* (Indian aggregators). The gap between them is **pre-bid commercial
assurance tied to price**, which is exactly TenderShield's wedge.

### A.2 Public procurement data — the corpus that changes everything

This is the most important research finding in this document.

| Source | What it provides | Access | Verified |
|---|---|---|---|
| **CPPP (India)** — `eprocure.gov.in` | Tender documents + **~4.9 M Award of Contract records** naming winner and price; archived tenders are public domain, searchable by keyword/value/organisation | Web, archive search. Datacenter IPs may be blocked — harvest from a resident/allowed egress | [CPPP archive](https://eprocure.gov.in/eprocure/app?page=FrontEndTendersInArchive&service=page), [award record volume](https://www.indiantenders.in/contract-awards/) |
| **State PWD portals (India)** | Employer-family tender packs — `mahatenders.gov.in`, `tntenders.gov.in`, `eproc.rajasthan.gov.in`, `etenders.kerala.gov.in`, `eproc.karnataka.gov.in`, `etender.up.nic.in`, `nprocure.com` | NIC eProcurement instances, per-state | Portal inspection |
| **NHAI / MoRTH (India)** | EPC and HAM packs — NIT, BoQ, specs, corrigenda, free without login | Web | [NHAI tender mirrors](https://tenders.infralens.in/nhai-tenders) |
| **CAG of India** | Audit reports naming **specific clauses, specific failures, specific ₹ amounts** — e.g. performance security under "clause 4.5" not forfeited → ₹41.65 Cr undue benefit; foreclosure approved without imposing ₹19.42 Cr damages | Free PDFs at `cag.gov.in` | [CAG Report No. 18 of 2025](https://cag.gov.in/uploads/download_audit_report/2025/Report-No.-18-of-2025,-Union-Government(Commercial)-06a2ba46ba3bfa0.02468565.pdf) |
| **MoSPI / PAIMANA (India)** | Monthly flash report: 1,847 monitored projects, ₹4.92 trillion cumulative cost overrun, per-project time/cost overrun and delay buckets | Public monthly reports; PAIMANA real-time tracker since Sep 2025 | [Business Standard, Jun 2026 report](https://www.business-standard.com/economy/news/infrastructure-projects-see-cost-overrun-of-4-92-trillion-mospi-126072801176_1.html) |
| **Etimad (Saudi)** | Unified national procurement platform; **283,000+ tender records, full public access**; official developer portal with a Tenders Inquiry Service API | [apiportal.etimad.sa](https://apiportal.etimad.sa/en/api_products/TendersInquiryService) | Etimad developer portal |
| **UAE** | Federal MoF digital procurement platform (2021); Dubai **eSupply** covering 40+ entities; Abu Dhabi separate | [UAE MoF](https://mof.gov.ae/en/public-finance/government-procurement/digital-procurement-platform/), [eSupply](https://esupply.dubai.gov.ae/) | Portal inspection |
| **TED (EU)** | All EU notices as **eForms structured XML + a knowledge graph with a SPARQL endpoint**; API for search and archive retrieval | [TED Developer Portal](https://developer.ted.europa.eu/home), [TED Open Data](https://data.ted.europa.eu/) | TED docs |
| **OCDS (global)** | The Open Contracting Data Standard — a single normalized schema implemented by **30+ governments**; OpenTender covers **35 jurisdictions** (27 EU states + EU institutions, Georgia, Iceland, North Macedonia, Norway, Serbia, Switzerland, UK); bulk JSON downloads and APIs via the OCP Data Registry | [OCDS standard](https://standard.open-contracting.org/latest/en/primer/what/), [OCP Data Registry](https://data.open-contracting.org/en/search/) | OCP docs |
| **UK** | Find a Tender + Contracts Finder, JSON API with OCDS export | Contracts Finder API | [OCDS on Contracts Finder](https://assets.publishing.service.gov.uk/media/5e99b67dd3bf7f0318cff3b8/Guide-to-Open-Contracting-Data-Standard-implementation-on-Contracts-Finder-V.2.1.pdf) |
| **World Bank / ADB** | Standard Bidding Documents (already used in `evals/e2e/fixtures/`) + MDB tender feeds | Public PDF + APIs | [WB Small Works SBD](https://thedocs.worldbank.org/en/doc/367901600894158277-0290022012/render/SmallworksDec2012.pdf) |

**Three consequences that reshape the plan:**

1. **The outcome graph — previously assumed to require paying customers — is buildable from public
   data, today, with zero customers.** Award records give winner, price and bidder counts at scale.
2. **CAG reports are better rulepack provenance than the research-report citations currently in
   `rulepacks/in-works/`.** "HKA CRUX says payment is a top dispute driver" becomes "CAG Report
   No. 18 of 2025 — clause 4.5 performance security unenforced, ₹41.65 Cr". The second is Indian,
   employer-specific, quotable to a customer, and evidentiary.
3. **OCDS is the normalization target for multi-country work.** Rather than writing a bespoke model
   per country, map every source into OCDS-shaped records. This is what makes the corpus — and
   therefore the eval harness in `specs/eval-at-scale.md` — country-agnostic by construction.

### A.3 Regulatory environment

| Finding | Source | Implication |
|---|---|---|
| EU AI Act **Annex III** high-risk obligations deferred to **2 Dec 2027** (Annex I embedded systems to 2 Aug 2028), per provisional agreement of 7 May 2026 | [Debevoise Data Blog, May 2026](https://www.debevoisedatablog.com/2026/05/22/eu-ai-act-high-risk-ai-systems-eu-commission-publishes-draft-guidance/) | More runway than the original Aug 2026 date, but the direction is fixed |
| Article 27 **Fundamental Rights Impact Assessment** applies to deployers that are public bodies or private orgs providing public services, using Annex III systems | [artificialintelligenceact.eu Art. 26](https://artificialintelligenceact.eu/article/26/) | **TenderShield sells to bidders, not contracting authorities.** A contractor-side bid-risk tool is very likely outside Annex III. `assumption:` this holds — confirm with counsel before any EU launch, and never sell an award-evaluation product to an authority without redoing this analysis |

**Standing rule:** if TenderShield is ever sold to a *contracting authority* for evaluating bids,
the EU AI Act analysis must be redone from scratch. That is a different product with a different
risk classification.

---

## PART B — THE DEFENSIBILITY THESIS

### B.1 The wrong frame

"What can our AI do that other AI can't" has no durable answer. Any prompt, any pattern set, any
extraction pipeline is reproducible by a competent team in weeks. Model capability is a rising tide
that lifts every competitor equally, and the frontier labs ship the capability itself.

### B.2 The right frame

**Defensibility comes from the parts that are not AI.** There are exactly four, and every feature in
Part C belongs to one of them:

| # | Moat class | Why it holds | TenderShield's instance |
|---|---|---|---|
| **1** | **Proprietary data an LLM has never seen and cannot retrieve** | Training corpora do not contain parsed, joined, normalized award graphs. Retrieval cannot reconstruct them | Employer Behaviour Graph (Part C.1) |
| **2** | **Deterministic computation at a scale LLMs fail at** | LLMs cannot reliably do arithmetic over 5,000 rows, cannot guarantee reproducibility, cannot cite a cell | BOQ engine, risk-to-price, cashflow, DSR benchmarking (C.2–C.5) |
| **3** | **Accountability a model cannot carry** | Reproducibility, version pinning, named professional sign-off, immutable audit trail. A chatbot cannot be a party to a dispute record | Provenance chain + sign-off (C.7) |
| **4** | **Position in a workflow** | Once a firm encodes its playbook and its bid history lives in the system, leaving costs more than the subscription | Playbooks, pack SDK, outcome history (C.8, Part D) |

### B.3 The claims we will be able to make

Each is verifiable by the customer, and structurally impossible for a general-purpose assistant:

1. *"Every number in this report was computed, not generated."*
2. *"We checked 4,847 BOQ rows and found 23 arithmetic defects, with cell references."*
3. *"This employer has awarded 47 comparable works; L1 averaged 11.3% below estimate."*
4. *"Your rates sit 8% below the state Schedule of Rates on these 14 items."*
5. *"This contract needs ₹4.2 Cr peak working capital in month 7."*
6. *"We found 6 contradictions across the NIT, SCC and Addendum 3, and here is which governs."*
7. *"Reproducible on re-run — rulepack v2026.07.1, model and prompt hash-pinned."*
8. *"Reviewed and signed by a named professional, with an audit trail admissible in a dispute."*

Not one is "our AI is smarter." Every one is falsifiable, which is what makes it a moat rather
than marketing.

### B.4 The anti-goal

**Do not build "upload any document and ask questions."** That is the Document Crunch/Trimble
position, it is being consolidated by better-capitalized incumbents, and it is the one product a
frontier model replaces for free. Every feature in this document must answer: *which of the four
moat classes does this belong to?* If the answer is "none", it does not get built.

---

## PART C — VALUE FEATURES

Ranked by (moat strength × revenue impact) ÷ build cost. Each carries **Why**, **How**, and
**What-if** as required.

### C.1 Employer Behaviour Graph — `marketdata` module ★ highest priority

**Moat class:** 1 (proprietary data)

**Why.** Today the product says "this clause is risky." That is an opinion any model can produce.
With the graph it says: *"this clause is risky, this employer has used it in 34 tenders, L1 lands
11.3% below estimate here, they retendered 6 of the last 40, and award takes 94 days."* That is a
different product. It connects clause to consequence, and it is the only asset in the plan that
compounds daily without customers.

**How.**
1. Harvest Award of Contract records + tender metadata from CPPP, state portals, GeM (India);
   Etimad API (Saudi); OCDS registry + TED (rest).
2. Normalize into OCDS-shaped records (`CorpusTender`, `CorpusAward`) — see `specs/modules/marketdata.md`.
3. Resolve employer identity into an **employer-family hierarchy** (`CPWD → circle → division`),
   because behaviour is a property of the *awarding division*, not the ministry.
4. Compute per-employer aggregates: bidder count distribution, L1-to-estimate spread, award latency,
   retender rate, repeat-winner concentration.
5. Join to risk findings at report time via `employer_family` (the column already exists on
   `Opportunity`).

**What-if.**
- *Portal blocks harvesting* → degrade to per-state adapters and slower cadence; the graph is
  additive, never a hard dependency (`CLAUDE.md` §2 — modules degrade gracefully).
- *Employer identity resolution is noisy* → publish confidence with every aggregate; suppress any
  statistic below a minimum sample size (`assumption:` n ≥ 12) rather than showing a weak number.
- *A portal's terms prohibit automated access* → that source is dropped. Legality of harvest is
  checked per source before an adapter ships, and recorded in the adapter's docstring.

### C.2 Risk-to-Price engine — `pricing-intel` module ★

**Moat class:** 2 (deterministic)

**Why.** The single largest gap between what the product outputs and what an estimator needs. A risk
register says "escalation barred — critical." The estimator has to convert that into a number. Doing
that conversion *for* them is the difference between an interesting report and a tool that touches
the bid. It is also the natural place to charge more.

**How.** Deterministic, never LLM. Each risk pattern gains a `price_impact` block:
`basis` (percent of contract value / per-unit / lump sum), `formula`, and `inputs` drawn only from
verified extracted facts (duration, retention %, payment days, LD rate) plus public indices
(WPI, RBI series) — never from model output. Output: a **bid loading sheet** — one row per accepted
finding, each with a rupee figure and the formula shown.

**What-if.**
- *A loading is wrong and a contractor underbids* → this is the highest-liability feature in the
  product. Mitigation is non-negotiable: every loading shows its formula and inputs, is marked
  indicative, is gated behind reviewer approval like every other artifact (Build Doc §11.4), and is
  never auto-applied to rates.
- *Indices unavailable for a jurisdiction* → the loading is omitted with an explicit "no index
  series configured for <jurisdiction>", never silently defaulted.

### C.3 Working-capital & cashflow model — `cashflow` module

**Moat class:** 2

**Why.** The number that actually decides bid/no-bid for a mid-market contractor is not risk
severity, it is *"can I fund this?"* Retention + payment days + mobilization advance + BG commission
+ milestone profile produce a month-by-month funding curve. No general assistant can compute this
because it requires the extracted contractual facts in structured form.

**How.** Deterministic model over verified facts: payment terms (days, trigger), retention % and
release schedule, mobilization advance and recovery, PBG/EMD amounts and validity, milestone dates
from the timeline module. Output: peak funding requirement, month of peak, and total financing cost
at a user-supplied cost of capital.

**What-if.**
- *Facts missing (no milestone dates)* → produce the model with an explicit assumptions block
  listing every substituted default; never silently assume.
- *User's cost of capital unknown* → require it as an input; do not guess.

### C.4 Schedule-of-Rates benchmarking — extends `boq`

**Moat class:** 2

**Why.** CPWD DSR and state SORs are public. Comparing tender BOQ rates against the published
schedule tells a contractor whether the employer's estimate is inflated or starved *before* they
price a single item. Immediately verifiable by the user, uniquely Indian, and pure arithmetic.

**How.** Version the DSR/SOR as rulepack data (`rulepacks/<pack>/rates/<authority>/<year>.yaml`),
match BOQ items to schedule items by code where present and normalized description otherwise,
report per-item and weighted-portfolio variance. Match confidence is published per row; unmatched
items are reported as unmatched, never force-matched.

**What-if.**
- *Description matching is unreliable* → report only code-matched items as high confidence and put
  description-matched items in a separate "indicative" band. Precision over coverage.

### C.5 Contradiction engine — extends `crossref`

**Moat class:** 2

**Why.** NIT says bid validity 90 days, SCC says 120, Addendum 3 says 180. RAG-based competitors
fail here because they retrieve chunks and reason locally. TenderShield already extracts facts into
a structured graph with provenance — so the contradiction pass runs over *facts*, not text, and is
deterministic.

**How.** For each canonical fact type (validity, EMD, submission datetime, LD rate, DLP, retention),
collect every extracted instance across documents, group by type, and flag disagreement. Apply the
document precedence order from the rulepack (addendum > SCC > GCC > NIT, jurisdiction-configurable)
to name the governing instance. Every side of a contradiction keeps its citation.

**What-if.**
- *Precedence differs by employer* → precedence is rulepack data, not code, and is overridable per
  employer family.
- *False contradictions from extraction noise* → require both instances to pass quote verification
  before a contradiction is raised.

### C.6 Outcome capture — `outcomes` module (cheap, do early)

**Moat class:** 1

**Why.** Build Doc §1.1(9) specifies it and it was never built: `Opportunity` has `status` but no
bid result. Without it there is no private outcome layer on top of the public graph, and no
correction loop. It is a handful of columns and one form — the cheapest moat increment available.

**How.** Record bid submitted/won/lost/declined, quoted value, L1 value where known, and post-award
which findings materialized. Feed into: (a) the accuracy dashboard, (b) per-employer private
aggregates that overlay the public graph, (c) the eval gold set.

**What-if.**
- *Users do not fill it in* → auto-prefill from the public award record by matching tender ID, and
  ask for one-click confirmation. Never require manual entry as the only path.

### C.7 Reproducibility & accountability chain — extends `findings`, `export`

**Moat class:** 3

**Why.** Enables claims 7 and 8 in §B.3, and is the precondition for selling to any firm with a
governance function. Also the liability shield.

**How.** Every finding stores `rulepack_version`, `model_id`, `prompt_hash`, `document_hash`,
`engine_version`. Deterministic findings (BOQ, dates, severity) must be byte-identical on re-run —
enforced by a test. Exports carry the full chain; sign-off records the named professional.

**What-if.**
- *Model deprecated, old finding not reproducible* → store the finding payload immutably and mark it
  `reproducible: false` with the reason. Never silently re-derive under a different model.

### C.8 Pack SDK + playbook encoding — see Part D

**Moat class:** 4

### C.9 Correction loop (close the gap identified in the audit)

**Moat class:** 1

**Why.** `review/service.py` captures `false_positive` and `rejected`; `analytics/service.py` counts
them. Nothing feeds back. Build Doc §11.5 calls the correction loop the compounding moat; today it
is a dashboard.

**How.** Aggregate corrections per pattern per employer family; when a pattern's false-positive rate
on a family exceeds a threshold with sufficient n, emit a `pattern.correction_suggested` event and
surface it in the admin console as a **proposed** rulepack overlay. Never auto-mutate a rulepack —
propose, human approves, version bumps (Build Doc §2.4 governance).

**What-if.**
- *Corrections encode one firm's idiosyncrasy* → overlays are scoped to the workspace by default;
  promotion to the shared pack requires review and a minimum number of distinct workspaces.

---

## PART D — DOMAIN-AGNOSTIC ARCHITECTURE

### D.1 The principle

**Agnostic engine, deep packs, data graph per vertical.** The engine already knows nothing about
construction: the risk engine matches patterns, the BOQ engine does arithmetic, the extractors find
dates and quotes. Domain knowledge lives entirely in `rulepacks/`.

Verified in the current codebase:
- All five risk patterns are **contract-generic** — payment, LD, escalation, DLP/retention,
  termination live in the GCC/SCC and apply to any works contract regardless of trade.
- Two of three trade checklists are already **MEP, not civil** (`electrical.yaml`, `hvac.yaml`).
- The BOQ unit map normalizes `kg`, `t`, `nos`, `m` alongside `cum`/`sqm` — mechanical units.
- `doc_types.yaml` is procurement-generic (NIT/GCC/SCC/BOQ/spec/addendum).
- `trade:` is a first-class field; adding a trade is **one YAML file, zero code**.

### D.2 The generalization ladder

| Rung | Domain | Cost | Gate |
|---|---|---|---|
| 0 | Civil works (now) | — | — |
| 1 | MEP trades: plumbing/public health, fire-fighting, structural steel, lifts | 1 YAML each | None — ship |
| 2 | Supply-and-erection / equipment contracts | New **patterns**: customs & GST variation, split delivery/erection LD, performance-guarantee tests, free-issue material, O&M tail | A paying customer asks |
| 3 | O&M / AMC / facilities | New pattern family: SLA penalties, response times, spares | Rung 2 validated |
| 4 | Services & manpower | Different BOQ shape (rate-only schedules) | Rung 3 validated |
| 5 | Any priced-schedule agreement (PPAs, O&G service contracts, leases) | New pack + new graph | Explicit business decision |

### D.3 The trap to avoid

Full domain-agnosticism collapses the product into "AI reads contracts" — the position with no
moat (§B.4). The defensible construction is: **the engine generalizes, the packs do not, and the
data graph is per-vertical by design.** The graph being hard to generalize is a feature; it is what
stops a generalist from following.

### D.4 Pack SDK — turning agnosticism into distribution

Rather than authoring every pack in-house, ship the ability to author packs:
- **Schema + validator + test harness** so a QS consultancy can write and verify a pack.
- **Customer playbooks** — a firm encodes its own acceptable terms; switching cost becomes real.
- **Pack marketplace** — consultancies author, TenderShield revenue-shares. This turns the Build
  Doc's P3 advisor channel into a platform rather than a services motion.

---

## PART E — GEOGRAPHIC SEQUENCING

### E.1 The order and the reasoning

| Rank | Market | Role | Rationale |
|---|---|---|---|
| **1** | **India** | Build the engine and the data | Enormous volume; ~4.9 M public award records; free rulepack sources (CPWD, GFR, MoF Manual, CAG); cheapest iteration. Accept low willingness to pay — India is where the asset is built, not where the margin is made |
| **2** | **Saudi** | First revenue expansion | [One unified portal (Etimad) with an official API](https://apiportal.etimad.sa/en/api_products/TendersInquiryService) and 283,000+ public tender records; Vision 2030 pipeline; FIDIC-shaped so the GCC pack transfers; high willingness to pay |
| **3** | **UAE** | Second expansion | Strong money but fragmented — federal MoF platform, Dubai eSupply (40+ entities), Abu Dhabi separate; less open award data. Enter after Saudi proves the GCC pack |
| **4** | **Europe** | Deferred | Best data infrastructure in the world (TED/eForms/OCDS) and the worst product fit — 24 languages, national contract forms per country, entrenched incumbents, EU AI Act overhead from Dec 2027. Enter only if pulled by a customer |

### E.2 The bridge nobody exploits

**Indian contractors are Gulf contractors.** Mid-market and large Indian firms bid in both markets
with the same commercial teams. Land them in India, follow them to Riyadh and Dubai on the same
login and the same playbook.

This resolves the India pricing problem without abandoning India: the same customer is monetized at
Gulf rates on their Gulf tenders. CAC for the GCC entry approaches zero because the relationship
already exists.

**Requirement this creates:** multi-jurisdiction must be a property of the *opportunity*, not the
*workspace*. One workspace must hold Indian and Saudi tenders simultaneously, each resolving its own
rulepack and currency. This is a data-model constraint to honor from the first Phase-16 commit.

### E.3 Currency and residency

Money stays in **minor units** (`CLAUDE.md` §4). Multi-currency requires an explicit `currency` on
every monetary value — never an implicit default. Data residency per Build Doc §1.3: India
ap-south-1, GCC me-central-1, UK eu-west-2.

---

## PART F — BUSINESS MODEL

### F.1 Existing lanes (Build Doc §0.4, unchanged)

- Free: 1 full tender review per organisation, watermarked
- Snapshot (per-tender): ₹7,500
- Pro: ₹24,999/mo — 10 reviews, 10 seats
- Scale: ₹74,999/mo — 40 reviews, baseline lock, API, SSO
- Overage: ₹4,999 (Pro) / ₹3,499 (Scale)

### F.2 New lane — **Express Report** (pay-per-report, no subscription)

**The requirement.** A visitor arrives, uploads a tender, gets it analysed, pays for the report,
downloads it, and leaves. No subscription, no sales conversation, minimal account friction.

**Why this matters commercially.** The Build Doc's `paygo` plan already exists in `PLAN_LIMITS`, but
it still assumes signup → workspace → project → upload. That funnel is built for a *customer*. The
Express lane is built for a *stranger*, and strangers are the entire top of the funnel that
currently does not exist (there is not even a `/pricing` page in `frontend/app/`).

**Flow.**
1. Landing → upload (no account; email captured only for delivery and receipt)
2. Processing → **teaser result**: deadline wall in full (this is the trust-builder and it is cheap),
   plus finding counts by severity, BOQ defect count, and two full findings with citations
3. Paywall → Razorpay [Payment Link / guest checkout](https://razorpay.com/us/payment-links/), no
   account required; Stripe for GCC/UK
4. Verified webhook → unlock full report + email the PDF (**webhook is the only billing truth**,
   Build Doc §15)
5. Lazy account creation via magic link so the buyer can return; the Express purchase converts into
   a workspace if they do

**Price ladder (`assumption:` — validate in the first 100 transactions):**

| Product | Scope | Indicative price |
|---|---|---|
| Deadline & Compliance Snapshot | Single document; deadlines, EMD, eligibility, missing-doc checklist | ₹1,499 |
| Express Risk Report | Full pack; risk register + BOQ defects + contradictions | ₹4,999 |
| Express Bid Pack | Adds clarification letter, assumptions register, bid loading sheet | ₹9,999 |

**The invariant conflict, and its resolution.** Build Doc §11.4 gates export on reviewer approval.
An Express buyer has no reviewer. Resolution — the *intent* of §11.4 is that nobody relies on
unreviewed output unknowingly, so:
- Express exports are a distinct `unreviewed` variant, watermarked
  **"INDICATIVE — NOT REVIEWED BY A QUALIFIED PROFESSIONAL"** on every page
- An explicit click-through acknowledgment is required before payment and is recorded in the audit
  log with timestamp and IP
- Risk-to-price loadings (C.2) are **excluded** from Express tiers — the highest-liability output
  requires a reviewer, full stop
- The disclaimer is in the emailed PDF, not only the web view

**Anti-abuse.** Rate-limit by email + IP + document hash; dedupe identical `document_hash` so the
same tender cannot farm repeated free teasers under different emails; cap teaser generation per IP
per day; require email verification before the teaser renders if the abuse rate warrants it.

**What-if.**
- *Express cannibalizes Pro* → it should, for small contractors, and that is fine: they were never
  going to buy Pro. Monitor the ratio; if Pro accounts downgrade to Express, gate Express to
  ≤ 3 reports per email per quarter and route the fourth to a subscription offer.
- *Chargebacks on a report already delivered* → deliver only after webhook confirmation, keep the
  full provenance chain, and cap Express at a value where dispute cost is tolerable.

### F.3 Other revenue lanes worth building

| Lane | Mechanism | Moat class |
|---|---|---|
| **Market Intelligence subscription** | The Employer Behaviour Graph sold standalone — employer scorecards, L1 benchmarks, competitor win-pattern reports. Buyers include firms that never upload a tender | 1 |
| **Advisor / white-label** | Consultancy multi-client workspaces, per-client usage billing, their logo on the Bid Review Pack | 4 |
| **Pack marketplace revenue share** | Third-party authored packs (Part D.4) | 4 |
| **API / ERP integration** | Scale tier and above; the integration itself is switching cost | 4 |

---

## PART G — PROFITABILITY MODEL

### G.1 The honest position

Per-tender cost is **not currently known** because it is not instrumented. Any margin figure quoted
before instrumentation is fiction. The first Phase-16 task in this area is therefore measurement,
not optimization.

### G.2 Cost drivers to instrument

Emit per-review, tagged with `opportunity_id`, `rulepack_version` and `model_id`:

| Driver | Metric |
|---|---|
| LLM inference | Input tokens, output tokens, cached tokens, calls, per pattern and per stage |
| OCR | Pages OCR'd, CPU-seconds, fallback rate |
| Storage | Bytes stored per opportunity, retention period |
| Compute | Worker seconds per stage |
| Delivery | Email/WhatsApp per notification |

**Target metric:** *fully-loaded cost per completed tender review*, reported p50 and p95, broken down
by pack and document count. Every pricing decision in §F.2 is provisional until this number exists.

### G.3 The architectural lever

The retrieval-first design (Build Doc §6.3 — anchor queries retrieve, then one *bounded* LLM
judgment per pattern) means cost scales with **pattern count**, not document length. This is the
single most important cost property of the system and must be protected: any change that sends whole
documents to a model breaks the unit economics of a 1,500-page pack. Guard it with a test that fails
if per-review token count exceeds a configured ceiling.

### G.4 Levers, in order of leverage

1. **Prompt caching** on the rulepack/pattern preamble — the same pattern text is sent for every
   tender. (Load the `claude-api` skill before implementing; do not size this from memory.)
2. **Rules-first everywhere possible** — classification and deadline extraction are already
   rules-first; keep expanding the deterministic share, which is free and also the moat.
3. **Model tiering** — cheap model for classification and retrieval ranking, strong model only for
   bounded clause judgment.
4. **Deduplicate by `document_hash`** — the same CPWD GCC appears in thousands of tenders. Cache
   extraction results per document hash across workspaces (findings stay workspace-scoped; only the
   *extraction* is shared, and only for documents whose hash matches a known public standard form).

> ⚠️ Lever 4 touches tenant isolation. Extraction caching may only key on documents already
> identified as **public standard forms** (CPWD GCC, FIDIC, WB SBD) via an allowlist of hashes.
> Never cache across tenants on customer-supplied documents. Cross-tenant leakage is
> company-ending (`CLAUDE.md` §4).

---

## PART H — RISKS, WHAT-IFS, KILL CONDITIONS

| # | Risk | Mitigation | Kill condition |
|---|---|---|---|
| 1 | **Accuracy never validated** — the product ships confident and wrong | The scale harness (`specs/eval-at-scale.md`) measures structural correctness on 1,000+ tenders without human labels; a 50-tender human gold set covers judgment | Critical-clause recall < 75% on the gold set after two tuning rounds |
| 2 | **Trust is binary** (Build Doc §12.1) | Quote verification, validators, reproducibility chain, unreviewed-export watermarking | Any invented quote reaching a customer |
| 3 | **Incumbent expansion** — Trimble/Document Crunch enters India | Moat classes 1 and 4: they cannot buy the Indian award graph or the encoded playbooks | Incumbent ships an India pack with employer-family baselines before we do |
| 4 | **Data source revocation** — a portal blocks harvesting or changes terms | Per-source adapters, graceful degradation, legality reviewed per adapter before ship | Both CPPP and state portals close public award access |
| 5 | **Scope reflex** (Build Doc §12.6 — the standing warning) | Every Phase-16 task maps to a moat class in §B.2. Anything that maps to none is cut | — |
| 6 | **Express lane liability** | Watermarking, acknowledgment logging, loadings excluded from unreviewed tiers | A dispute where an unreviewed Express report is relied on as professional advice |
| 7 | **Cost per review exceeds price** | §G.2 instrumentation before any pricing commitment; token ceiling test | Fully-loaded p95 cost > 25% of the lowest Express tier |
| 8 | **Multi-country dilution** — three markets, none served well | India is the only market with a full pack until its exit gate passes; Saudi/UAE ship the FIDIC pack only | Saudi work starting before the India accuracy gate is green |

---

## Appendix — Requirement traceability

Every Phase-16 task in `tasks/backlog.md` references a section of this document. Every new spec in
`specs/` cites both this document and the Build Doc section it derives from. Anything invented
beyond a cited source is marked `assumption:` in the spec, per `CLAUDE.md` §3.

*End of document — v1.0.*
