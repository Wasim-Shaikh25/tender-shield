# TenderShield AI — Contractor Commercial Intelligence
### Full Product, Architecture & Production Build Document (India-first · GCC · UK)

**Document version:** 1.0 · 22 July 2026
**Status:** Build blueprint — engineering-ready. Companion to the "TenderShield AI — Product & Market Research" doc (20 Jul 2026); this document turns that strategy into an executable system.
**Disclaimer:** Product/engineering document, not legal, quantity-surveying, or investment advice. Every generated finding, register, and letter requires review by a qualified professional (estimator / QS / contracts manager) before commercial use. The software must enforce this (§11.4).

---

## TABLE OF CONTENTS

- **Part 0 — Scope Decision (read first):** the wedge, what we're NOT building, personas, business model (free→paid), the AI assistant
- **Part 1 — Product Specification:** core user journey, feature matrix by phase, non-functional requirements
- **Part 2 — Contract Rule-Packs (the moat):** India/GCC/UK pack structure, risk patterns, governance
- **Part 3 — System Architecture:** high-level diagram, canonical data model (SQL), processing pipeline
- **Part 4 — Tech Stack (locked):** every layer and the rationale
- **Part 5 — Authentication & Authorization:** email/Google/OTP, rotating refresh tokens, RBAC, RLS (with code)
- **Part 6 — The AI Pipeline:** classify → extract → deterministic checks → draft, with anti-hallucination validators
- **Part 7 — Freemium, Metering & Billing:** plan limits, race-safe enforcement, provider abstraction
- **Part 8 — The AI Assistant ("Ask TenderShield"):** grounded customer-facing assistant
- **Part 9 — Frontend Structure:** routes, workbenches, UX principles
- **Part 10 — Phase-Wise Delivery Plan:** Phases 0–6 with exit and kill gates
- **Part 11 — Production & Operations:** deployment, data protection (DPDP/PDPL/GDPR), security, eval ops, SLOs, DR
- **Part 12 — Risks & Honest Warnings**
- **Part 13 — 30-Day Action Checklist**
- **Part 14 — Domain-Expertise Strategy:** build-first-from-public-sources, validate-later
- **Part 15 — Payment & Checkout (end-to-end):** pricing page, paywall, Razorpay + Stripe, GST invoicing, billing management
- **Part 16 — Internal Admin Console + Analytics & Monitoring:** support console, payment logging, health & business dashboards
- **Part 17 — Super-Admin AI Assistant ("Ops Copilot"):** propose-not-execute investigator over logs
- **Part 18 — Release Readiness: Is This a Complete Product?** honest assessment of what's spec'd vs. what's built

---

## PART 0 — SCOPE DECISION (READ FIRST)

### 0.1 What we are building (the wedge)

Per the research doc's recommendation, the launch product is **Tender Risk + BOQ Assurance** only:

> **Ingest the tender pack (NIT/RFP, GCC/SCC, specs, BOQ, addenda) → build the commercial baseline graph → surface risk clauses, deadline traps, BOQ defects and scope gaps with exact citations → generate the bid-decision artifacts (risk register, clarification letter, assumptions & exclusions register, deadline calendar, bid review pack) — before bid submission.**

| Stage | Trigger (input) | Generated artifacts (output) | Deadline that creates urgency |
|---|---|---|---|
| **Pre-bid (launch)** | Tender package: NIT/RFP, contract conditions, specs, BOQ (Excel/PDF), addenda | Risk register · clarification-question letter · BOQ defect report · assumptions/exclusions register · deadline calendar · exportable Bid Review Pack | Clarification cut-off & bid submission dates (days away, immovable) |
| **Baseline lock (P2)** | Award letter, negotiated contract, accepted BOQ | Frozen baseline graph + commercial handover pack + notice-rule register | Project start; tender knowledge evaporates at handover |
| **Change & notice (P3)** | Revised drawings/specs, site instructions, RFIs, emails, minutes | Potential-variation inbox · notice drafts populated with verified facts · evidence checklist | Contractual notice windows (7/14/28 days under most forms) |
| **GCC pack (P4)** | FIDIC-based tenders (UAE/KSA/Qatar) | Same artifacts; FIDIC sub-clause deadline engine; bilingual EN/AR output | FIDIC 20.1-style time-bars |
| **UK pack (P5)** | JCT/NEC tenders & contracts | Same artifacts; NEC early-warning / compensation-event engine | NEC 8-week CE notification bars |

### 0.2 What we are explicitly NOT building in v1
Straight from the research doc's "postponed" list, now binding:
- **No drawing/CV takeoff.** No blueprint quantity extraction, no symbol counting, no overlay diff. Drawings are stored, registered, and human-linked only. (Drawing intelligence is gated behind the research doc's rule: *"Do not build drawing intelligence until users consistently trust text/BOQ findings."*)
- No BIM authoring/clash detection, no bid-management marketplace, no live material pricing, no autonomous notice sending, no scheduling/CPM engine, no legal opinions.
- No enterprise integrations (Procore/Aconex/SAP) in v1 — upload/export first, APIs in Phase 3.
- Web-first; mobile evidence capture comes with Phase 3 (site workflows), not before.

### 0.3 Primary personas

| Persona | Description | Why they pay |
|---|---|---|
| **P1: Mid-market GC commercial head (India)** — PRIMARY | ₹50–1,000 Cr turnover; bids 5–30 tenders/month across CPWD/state PWD/private; 2–6 person estimation team | A missed LD/escalation/payment-term trap costs lakhs-to-crores; team reviews 500-page packs in days they don't have |
| **P2: Specialty/small contractor owner** | Electrical/HVAC/civil sub; bids on GeM/CPPP; no contracts team — the owner IS the contracts team | ₹5–15k per-tender review replaces a consultant they can't afford and a risk they can't see |
| **P3: QS / contracts consultancy** | Reviews tenders and drafts claims for many contractor clients | 10x throughput per reviewer; white-label reports billed to clients |
| **P4: EPC commercial team (later)** | High document volume, governance needs | Portfolio risk, SSO, APIs — Phase 3+ |

### 0.4 Business model (one-time free → paid, as required)

- **Free tier:** **1 full tender review** per organisation — complete experience (risk register + BOQ report + clarification letter), watermarked "DRAFT — TenderShield", export enabled. The wow moment is the conversion event; contractors bid constantly, so the second tender arrives within days.
- **Paid (India pricing, aligned to the research doc's hypotheses):**
  - **Per-tender (Snapshot):** ₹7,500/tender — pay-as-you-go for small contractors; no subscription.
  - **Pro (firm):** ₹24,999/mo — 10 tender reviews/mo, 10 seats, playbook customization, white-label Bid Review Pack, deadline calendar with WhatsApp alerts.
  - **Scale:** ₹74,999/mo — 40 reviews/mo, baseline-lock module, API, SSO, priority OCR.
  - **Overage:** ₹4,999/review (Pro), ₹3,499 (Scale).
  - GCC/UK mirrors via Stripe (AED 349/tender, AED 2,499/mo · £79/tender, £549/mo — validate in discovery).
- **Rails:** Razorpay (India: UPI, netbanking, e-mandates) + Stripe (GCC/UK) behind one billing interface (§7).
- **Advisor edition** (P3): consultancy multi-client workspaces, per-client usage billing — the research doc's partner-channel motion.

### 0.5 The AI Assistant ("Ask TenderShield")
In-app assistant grounded ONLY in: (a) the org's uploaded tender/contract documents, (b) the contract rule-pack, (c) generated work products. Typical turns: "what's our total LD exposure cap?", "which BOQ items does the escalation bar affect?", "draft a sharper version of clarification #4", "list every deadline before 30 Aug". It can invoke internal tools (regenerate a register row, filter BOQ defects, list deadlines) and refuses general questions. Architecture §8.

---

## PART 1 — PRODUCT SPECIFICATION

### 1.1 Core user journey (India, happy path)

1. **Sign up** (email+password / Google / phone OTP) → create Organisation → set contractor profile (trades, typical employer types, states) → optional: upload company **playbook** (their standard acceptable terms; else start from the pack's default playbook).
2. **Create Opportunity → upload tender pack** (multi-file: PDFs, Excel BOQ, ZIP from CPPP/GeM download). System classifies every file (NIT/RFP, GCC, SCC, specs, BOQ, drawings, addenda, forms), flags **missing expected documents** (e.g., SCC referenced but absent), and detects addendum supersessions.
3. **Instant deadline & summary wall (< 3 min):** submission date/time, pre-bid meeting, clarification cut-off, bid validity, EMD/security amounts and form, milestone dates — each with page-level citation and a confirm chip.
4. **Risk extraction:** clause segmentation → obligation extraction → deviation comparison against the playbook → risk register rows, each with: category (payment, LD, escalation, indemnity, termination, ground conditions, price-variation, arbitration seat…), severity, exact quoted text + page, affected BOQ trades, and a suggested pricing/mitigation note.
5. **BOQ assurance (deterministic, NOT LLM):** normalize the BOQ (Excel or table-extracted PDF) into canonical items → arithmetic checks (rate×qty≠amount, subtotal/carry-forward errors), unit inconsistencies, duplicate items, blank rates, quantity outliers vs. document-internal cross-references → cross-check item descriptions against spec sections → **scope-gap suggestions** from trade checklists in the rule-pack ("no dewatering item despite basement excavation in scope").
6. **Artifact generation:** clarification-question letter (quoting exact source text, numbered, employer-format), assumptions & exclusions register, risk register export, one-page bid/no-bid summary with explainable factor scores (weights user-controlled).
7. **Review workbench:** estimator/commercial reviewer accepts/edits/rejects each finding; every acceptance is logged; export is blocked until review completes (§11.4).
8. **Export Bid Review Pack** (DOCX/PDF/XLSX) — the artifact that circulates to the MD before bid sign-off.
9. **Outcome capture:** bid won/lost/declined + reasons; post-award, which risks materialized. This outcome graph across tenders is the moat the research doc named.

### 1.2 Feature matrix by phase

| Feature | P1 MVP | P2 | P3 | P4 GCC | P5 UK |
|---|---|---|---|---|---|
| Auth (email/Google/OTP), orgs, roles, RLS | ✅ | | | | |
| Tender pack upload, classification, missing-doc checklist | ✅ | +addendum diff view | | ✅ | ✅ |
| Deadline extraction + calendar + email alerts | ✅ | +WhatsApp | | +business-day/Hijri holidays | ✅ |
| Clause/obligation extraction + risk register w/ citations | ✅ (top 25 risk patterns) | +full taxonomy, custom playbooks | | +FIDIC pack | +JCT/NEC pack |
| BOQ normalization + defect checks | ✅ (Excel + digital-PDF tables) | +scanned-BOQ OCR hardening | | | |
| Scope-gap suggestions (trade checklists) | 3 trades | +8 trades | | | |
| Clarification letter + assumptions register + bid/no-bid score | ✅ | +tone/format variants | | +bilingual AR | ✅ |
| Review workbench + audit log + Bid Review Pack export | ✅ | +multi-reviewer approval chain | | | |
| Freemium metering + Razorpay | ✅ | +Stripe | | ✅ | ✅ |
| AI Assistant (grounded) | basic Q&A | +tools (regenerate, filter) | +cross-tender queries | | |
| Baseline lock + handover pack | | ✅ | | | |
| Change/variation inbox + notice drafts | | | ✅ | ✅ | ✅ |
| GSP-style portal pulls / integrations / API / SSO | | | ✅ | | |

### 1.3 Non-functional requirements
- **Time-to-first-value:** upload → deadline wall + doc checklist in **< 3 min p95** (packs are 200–1,500 pages; stream results as they land, don't block on full completion).
- **Full risk register + BOQ report:** < 25 min p95 for a 800-page pack + 5,000-row BOQ.
- **Low-bandwidth reality (India-first):** resumable chunked uploads (tus protocol), ZIP ingestion, processing continues offline with email/WhatsApp "your review is ready".
- **Data residency:** India ap-south-1 · GCC me-central-1 · UK eu-west-2. Tender documents are competitively sensitive — residency and isolation are sales requirements, not compliance box-ticks.
- **No training on customer data;** zero-retention LLM agreement; stated in-product.
- **Availability 99.5%;** the deadline calendar + document vault are the criticality core.

---

## PART 2 — CONTRACT RULE-PACKS (THE MOAT)

A rule-pack is versioned data + code + tests — not prompt text. The research doc's "contract and jurisdiction packs" made concrete:

```
rulepacks/
  in-works/                        # India public/private works (launch)
    pack.yaml                      # version, effective dates, reviewer sign-off
    doc_types.yaml                 # NIT, GCC, SCC, BOQ, specs, addendum schemas
    deadlines.py                   # submission/validity/EMD calculators
    risk_patterns/                 # the top-N codified risk patterns
      payment_terms.yaml           #  - extended payment (>60/90/120d), pay-when-paid
      liquidated_damages.yaml      #  - LD % per week + cap presence/absence
      price_escalation.yaml        #  - escalation barred / formula-based (10CA...)
      emd_security.yaml            #  - EMD %, PBG %, retention, defect liability
      time_extension.yaml          #  - EOT grounds, notice periods
      ground_conditions.yaml       #  - unforeseen-conditions risk transfer
      termination_risk.yaml        #  - termination-for-convenience compensation
      arbitration_seat.yaml        #  - seat/venue, institutional vs ad-hoc
      deviation_limits.yaml        #  - quantity-variation limits (±25% etc.)
      taxes_gst.yaml               #  - inclusive/exclusive, RA-bill GST handling
      ...
    playbooks/
      default_contractor.yaml      # acceptable-term thresholds; org-overridable
    boq/
      canonical_schema.yaml        # item, unit normalization map (cum/m3/CuM...)
      checks.yaml                  # arithmetic tolerances, outlier z-thresholds
      trade_checklists/            # scope-gap knowledge
        civil_structure.yaml       # excavation→dewatering→anti-termite→backfill...
        electrical.yaml
        hvac.yaml
    templates/
      clarification_letter.j2
      risk_register.j2
      assumptions_exclusions.j2
      bid_review_pack.j2
    references/                    # citable, retained as text for retrieval
      gfr_2017_extracts.yaml       # General Financial Rules — reference only
      works_manual_2025.yaml       # MoF Manual for Procurement of Works (2nd ed.)
    tests/                         # golden tenders + expected findings
  gcc-fidic/   (P4: FIDIC Red/Yellow 1999+2017 sub-clause engine, time-bars,
                bilingual output, UAE/KSA holiday + business-day calendars)
  uk-jct-nec/  (P5: NEC4 early-warning/CE clocks, JCT relevant-events, points
                of difference engine)
```

### 2.1 India pack — launch depth
- **Top-25 risk patterns first** (per the research doc's 10-day prototype logic: 15–20 high-value patterns beat 200 shallow ones). Each pattern = detection spec (anchor phrases + LLM classification prompt + negative examples) + severity logic + playbook comparison + suggested clarification text + affected-trade mapping.
- **Employer-flavor awareness:** CPWD GCC, MES, NHAI/MoRTH, railways, state PWDs, and private-developer forms differ systematically. The pack stores per-employer-family default expectations so deviation detection is against the *right* baseline ("this NHAI tender deletes the standard escalation clause" is the finding, not "escalation clause exists").
- **Temporal law/manual versioning:** packs carry `effective_from/to`; a tender is evaluated against the pack version matching its NIT date.
- **BOQ unit normalization map** is deceptively valuable: `Cum/cum/m3/CuM/M³`, `Rmt/RM/m`, `MT/tonne/Ton`, `Sqm/m2/SqM` — real Indian BOQs mix all of these in one sheet.

### 2.2 GCC pack (P4) — key differences to encode
- FIDIC sub-clause deadline engine (e.g., 1999 Red Book 20.1 28-day claim bar; 2017 editions' 20.2 regime) as deterministic date math with calendar packs (Fri/Sat vs Sat/Sun weekends by country, public holidays).
- Bilingual artifact generation (EN primary, AR courtesy translation flagged "non-binding translation").
- Particular-conditions deviation detection vs the FIDIC baseline is the core value — GCC employers amend FIDIC heavily and bury the amendments.

### 2.3 UK pack (P5)
- NEC4: early-warning register generation, 8-week compensation-event notification clocks, Z-clause deviation detection vs unamended NEC.
- JCT: relevant events/matters mapping, amendment-schedule comparison.
- Letters are prose-heavy; extraction evals need extra golden coverage (same lesson as any prose-form jurisdiction).

### 2.4 Rule-pack governance
- Every change = PR + golden-tender tests + sign-off by the named domain reviewer (retained QS/contracts manager for India; FIDIC-experienced QS for GCC; UK QS for P5).
- Generated artifacts embed pack version (`pack: in-works@2026.07.1`); audit can trace any finding to the pattern version that produced it.
- Reviewer rejections in production feed pattern refinement weekly — the correction loop IS the compounding asset.

---

## PART 3 — SYSTEM ARCHITECTURE

### 3.1 High-level architecture

```
                       ┌──────────────────────────────────────────────┐
                       │               CLIENT (Next.js)               │
                       │ Opportunity board · Upload · Risk Workbench  │
                       │ BOQ Workbench · Assistant · Billing · Admin  │
                       └───────────────┬──────────────────────────────┘
                                       │ HTTPS (JWT)
                       ┌───────────────▼──────────────────────────────┐
                       │         API GATEWAY / BFF (FastAPI)          │
                       │   authn/authz · rate-limit · usage metering  │
                       └──┬─────────┬──────────┬──────────┬───────────┘
                          │         │          │          │
             ┌────────────▼──┐ ┌────▼──────┐ ┌─▼────────┐ ┌▼──────────────┐
             │ Ingestion Svc │ │ BOQ Engine│ │ Risk &   │ │ Assistant Svc │
             │ classify·OCR· │ │ (determin-│ │ Drafting │ │ (RAG over org │
             │ split·extract │ │ istic:    │ │ Svc (LLM │ │ corpus + rule │
             │ (Celery)      │ │ DuckDB)   │ │ orchestr)│ │ pack)         │
             └───────┬───────┘ └────┬──────┘ └─┬────────┘ └┬──────────────┘
                     │              │          │           │
       ┌─────────────▼──────────────▼──────────▼───────────▼───────────────┐
       │                          DATA LAYER                                │
       │  PostgreSQL 16 (+pgvector) · Redis (queues/cache/limits)          │
       │  S3 vault (KMS, per-org prefix) · Append-only audit (PG + S3 lock)│
       └───────────────────────────────────────────────────────────────────┘
       External: Claude API · Textract/Google Vision OCR · Razorpay+Stripe
                 SES/Resend · MSG91 (OTP/WhatsApp) · tusd (resumable upload)
```

**Deliberate choices:**
- **Modular monolith** (`app/ingestion`, `app/boq`, `app/risk`, `app/drafting`, `app/assistant`, `app/billing`, `app/auth`); split OCR workers first when scale demands.
- **Page-streamed processing:** a 1,200-page pack is processed page-window by page-window; findings appear in the UI as they're produced (Redis pub/sub → SSE). Perceived speed is a feature.
- **Deterministic BOQ engine** is pure Pandas/DuckDB, bit-reproducible, zero LLM. Arithmetic findings must never be "AI opinions".
- **pgvector** for retrieval; corpus per opportunity is bounded.

### 3.2 Canonical data model (PostgreSQL — the baseline graph)

```sql
CREATE TABLE orgs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  country TEXT NOT NULL CHECK (country IN ('IN','AE','SA','QA','GB')),
  plan TEXT NOT NULL DEFAULT 'free',          -- free|paygo|pro|scale
  free_review_used BOOLEAN NOT NULL DEFAULT FALSE,   -- one-time free flag
  playbook JSONB NOT NULL DEFAULT '{}'::jsonb,       -- org term thresholds
  billing_provider TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT UNIQUE NOT NULL,
  phone TEXT UNIQUE,
  password_hash TEXT, google_sub TEXT UNIQUE,
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  mfa_totp_secret TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE org_members (
  org_id UUID REFERENCES orgs(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','admin','estimator','reviewer','viewer')),
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE opportunities (                   -- one tender being pursued
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id),
  title TEXT NOT NULL,
  employer TEXT, employer_family TEXT,         -- cpwd|nhai|state_pwd|railways|private|other
  jurisdiction TEXT NOT NULL DEFAULT 'IN',
  contract_form TEXT,                          -- cpwd_gcc|fidic_red_99|nec4_ecc|custom...
  value_band TEXT,
  status TEXT NOT NULL DEFAULT 'reviewing',    -- reviewing|reviewed|bid|won|lost|declined
  rulepack_version TEXT,
  submission_due TIMESTAMPTZ, clarification_due TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES orgs(id),
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,        -- nit|rfp|gcc|scc|spec|boq|drawing|addendum|form|award|other
  filename TEXT NOT NULL, s3_key TEXT NOT NULL, sha256 TEXT NOT NULL,
  pages INT, ocr_status TEXT NOT NULL DEFAULT 'pending',
  supersedes UUID REFERENCES documents(id),    -- addendum chains
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  uploaded_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clauses (                          -- segmented contract text
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  clause_ref TEXT,                              -- "GCC 25.2", "SCC 14(iii)"
  heading TEXT, text TEXT NOT NULL,
  page_from INT, page_to INT,
  defined_terms TEXT[], cross_refs TEXT[]
);

CREATE TABLE findings (                         -- risk register rows
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,        -- risk_clause|boq_defect|scope_gap|deadline|missing_doc
  category TEXT NOT NULL,    -- payment|ld|escalation|emd|termination|arith|unit|dup|...
  severity TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low','info')),
  title TEXT NOT NULL, detail TEXT NOT NULL,
  clause_id UUID REFERENCES clauses(id),
  source_page INT, source_quote TEXT,           -- provenance, verbatim ≤200 chars
  boq_item_ids UUID[],                          -- affected BOQ rows
  affected_trades TEXT[],
  suggested_action TEXT,                        -- clarification / price allowance / decline
  pattern_id TEXT, pattern_version TEXT,        -- rule-pack traceability
  amount_exposure NUMERIC(16,2),
  review_status TEXT NOT NULL DEFAULT 'proposed',  -- proposed|accepted|edited|rejected
  reviewed_by UUID REFERENCES users(id), review_note TEXT
);

CREATE TABLE boq_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  src_sheet TEXT, src_row INT,                  -- provenance into the uploaded file
  item_code TEXT, description TEXT NOT NULL,
  unit_raw TEXT, unit_canon TEXT,
  qty NUMERIC(18,3), rate NUMERIC(16,2), amount NUMERIC(18,2),
  trade TEXT, spec_refs TEXT[],
  checks JSONB NOT NULL DEFAULT '{}'::jsonb     -- {"arith_ok":true,"dup_of":null,...}
);

CREATE TABLE deadlines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL,
  opportunity_id UUID NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,     -- submission|prebid_meeting|clarification|validity|emd|milestone
  due_at TIMESTAMPTZ NOT NULL,
  source_page INT, source_quote TEXT,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,     -- confirm-chip state
  alerts_sent JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE artifacts (                         -- generated outputs, versioned
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  opportunity_id UUID NOT NULL REFERENCES opportunities(id),
  kind TEXT NOT NULL,     -- clarification_letter|risk_register|assumptions|bid_pack
  version INT NOT NULL,
  body JSONB NOT NULL,    -- structured sections w/ evidence_refs[] + citations[]
  model_meta JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',  -- draft|reviewed|approved|exported
  reviewed_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (opportunity_id, kind, version)
);

CREATE TABLE outcomes (
  opportunity_id UUID PRIMARY KEY REFERENCES opportunities(id),
  result TEXT NOT NULL,           -- won|lost|declined|cancelled
  decline_reason TEXT,            -- risk_based|capacity|price|other
  margin_note TEXT,
  risks_materialized UUID[],      -- which findings actually bit, post-award
  recorded_by UUID, recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usage_events (
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL REFERENCES orgs(id),
  event TEXT NOT NULL,            -- review_started|artifact_generated|assistant_msg|ocr_pages
  qty INT NOT NULL DEFAULT 1, ref_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (           -- append-only; no UPDATE/DELETE grants
  id BIGSERIAL PRIMARY KEY,
  org_id UUID, actor_user_id UUID,
  action TEXT NOT NULL, object_type TEXT, object_id UUID,
  detail JSONB, at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE doc_chunks (          -- assistant retrieval
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page INT, chunk_ix INT, clause_ref TEXT,
  text TEXT NOT NULL, embedding VECTOR(1024)
);
CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops);

-- RLS on every org-scoped table (identical pattern):
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON findings
  USING (org_id = current_setting('app.org_id')::uuid);
```

**RLS is non-negotiable.** Tender documents reveal a contractor's bidding intent and pricing posture; a cross-tenant leak between two contractors bidding the same NHAI package is company-ending. `SET LOCAL app.org_id` per request-transaction, enforced in the auth dependency (§5).

### 3.3 Processing pipeline (sequence)

```
Upload (tus resumable, ZIP-aware) → S3 → /documents event →
  [Celery] classify_task    → per-file doc-type (rules-first, LLM fallback)
                              missing-doc checklist vs pack's expected set
  [Celery] ocr_task         → Textract (tables mode for BOQ PDFs); GVision fallback
  [Celery] deadline_task    → anchor-regex + LLM extraction → deadline rows
                              (streamed to UI immediately — the <3 min promise)
  [Celery] clause_task      → segmentation → clauses rows w/ refs + defined terms
  [Celery] risk_task        → per risk-pattern: candidate clauses (hybrid retrieval)
                              → LLM classification vs pattern spec + playbook
                              → findings rows (quote-verified, else confidence-low)
  [Celery] boq_task         → normalize → deterministic checks → boq_items +
                              findings(kind='boq_defect')
  [Celery] scopegap_task    → trade checklist × spec/BOQ cross-refs → findings
User works the Risk/BOQ workbenches (accept/edit/reject) →
"Generate artifacts" → metering check (free/paid §7) →
  [Celery] draft_task       → clarification letter, assumptions register, bid pack
                              → validators (quotes exist, no invented numbers,
                                citations resolve, all critical findings addressed)
Reviewer approves → export renderer (docxtpl/WeasyPrint/openpyxl) → audit log
Outcome recorded → learning loop (pattern precision dashboard, §11.5)
```

---

## PART 4 — TECH STACK (LOCKED)

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | **Next.js 15 + TypeScript + Tailwind + shadcn/ui** | SSR marketing + app in one repo; fast iteration |
| Backend | **Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic** | Python owns document/LLM tooling; Pydantic v2 contracts |
| Jobs | **Celery + Redis**; SSE for streaming findings | Boring and reliable; packs process in parallel windows |
| DB | **PostgreSQL 16 + pgvector** (RDS) | RLS + JSONB + vectors, one system |
| Files | **S3 + SSE-KMS**; tusd for resumable uploads; Object Lock audit bucket | 1GB tender ZIPs on patchy site connections |
| BOQ engine | **Pandas + DuckDB + openpyxl** | 50k-row BOQs in seconds, SQL-testable checks |
| OCR | **AWS Textract** (TABLES mode) primary, **Google Vision** fallback | Scanned BOQ tables are the hard 20% |
| LLM | **Claude API** — Sonnet-class: clause/risk extraction & drafting; Haiku-class: classification, assistant routing | Long context (whole GCC in one window), structured output, zero-retention |
| Export | Jinja2 → **docxtpl** (DOCX), WeasyPrint (PDF), openpyxl (XLSX registers) | Bid Review Pack must look like the contractor's own letterhead |
| Auth | Custom FastAPI (§5) — argon2id, RS256 JWT, rotating refresh | Trust-critical; no vendor lock |
| Payments | **Razorpay** (IN) + **Stripe** (GCC/UK) behind one interface | §7 |
| Comms | SES/Resend · **MSG91** OTP + WhatsApp BSP | Deadline alerts on WhatsApp get read on site |
| Infra | AWS ECS Fargate · RDS · ElastiCache · CloudFront · Terraform · GitHub Actions | §11 |
| Monitoring | Sentry + Prometheus/Grafana + Loki JSON logs | §11.6 |

---

## PART 5 — AUTHENTICATION & AUTHORIZATION

Requirements: email+password (argon2id) · Google OAuth (OIDC) · phone OTP (MSG91) — India SMEs are phone-first. JWT access **15 min RS256** + **rotating refresh 30 days** (httpOnly Secure cookie) with **reuse detection** that revokes the whole token family. Org-scoped RBAC: `owner > admin > estimator > reviewer > viewer`. TOTP MFA optional (mandatory for owner/admin on Pro+). Rate limits: 5 failed logins/15 min → captcha; OTP 3 sends/10 min, 5 verify attempts.

```python
# app/auth/security.py
from datetime import datetime, timedelta, timezone
import uuid, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher(time_cost=3, memory_cost=64*1024, parallelism=2)
ACCESS_TTL, REFRESH_TTL, ALGO = timedelta(minutes=15), timedelta(days=30), "RS256"

def hash_password(pw): return ph.hash(pw)
def verify_password(pw, hashed):
    try: ph.verify(hashed, pw); return True
    except VerifyMismatchError: return False

def mint_access(user_id, org_id, role, priv_key, kid):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "org": org_id, "role": role,
                       "iat": now, "exp": now + ACCESS_TTL,
                       "iss": "tendershield", "aud": "tendershield-api",
                       "jti": str(uuid.uuid4())},
                      priv_key, algorithm=ALGO, headers={"kid": kid})
```

```python
# app/auth/refresh.py — rotation + reuse detection
import hashlib, secrets
def new_refresh():
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()

async def rotate(db, raw):
    row = await db.get_refresh(hashlib.sha256(raw.encode()).hexdigest())
    if not row or row.revoked or row.expires_at < utcnow():
        raise AuthError("invalid_refresh")
    if row.used_at is not None:                      # replay → stolen token
        await db.revoke_family(row.family_id)
        await audit(db, "auth.refresh_reuse_detected", user=row.user_id)
        raise AuthError("reuse_detected")
    await db.mark_used(row.id)
    raw2, h2 = new_refresh()
    await db.insert_refresh(user_id=row.user_id, family_id=row.family_id,
                            token_hash=h2, expires_at=utcnow()+REFRESH_TTL)
    return raw2
```

```python
# app/auth/deps.py — request auth + RLS binding + RBAC
ROLE_RANK = {"viewer":0,"reviewer":1,"estimator":2,"admin":3,"owner":4}

async def current_principal(request, db=Depends(get_db)) -> Principal:
    claims = jwt.decode(extract_bearer(request), pub_key_for(request),
                        algorithms=["RS256"], audience="tendershield-api",
                        issuer="tendershield")
    await db.execute(text("SET LOCAL app.org_id = :o"), {"o": claims["org"]})  # RLS
    return Principal(user_id=claims["sub"], org_id=claims["org"], role=claims["role"])

def require(min_role):
    async def guard(p=Depends(current_principal)):
        if ROLE_RANK[p.role] < ROLE_RANK[min_role]:
            raise HTTPException(403, "insufficient_role")
        return p
    return guard
# @router.post("/opportunities/{id}/artifacts/approve")
# async def approve(id: UUID, p=Depends(require("reviewer"))): ...
```

OTP (Redis-backed, hash-stored, 5-min TTL, capped attempts) and Google OIDC (verify iss/aud/email_verified; link only verified emails) follow the standard patterns; frontend keeps the access token in memory only, silent-refresh on 401, org-switcher re-mints with the new `org` claim.

---

## PART 6 — THE AI PIPELINE (CLASSIFY → EXTRACT → CHECK → DRAFT)

### 6.1 Document classification (rules-first)

```python
# app/ingestion/classify.py
ANCHORS = {
  "nit":      [r"NOTICE\s+INVITING\s+TENDER", r"\bNIT\s*No"],
  "gcc":      [r"GENERAL\s+CONDITIONS\s+OF\s+CONTRACT"],
  "scc":      [r"SPECIAL\s+CONDITIONS\s+OF\s+CONTRACT", r"PARTICULAR\s+CONDITIONS"],
  "boq":      [r"BILL\s+OF\s+QUANTIT", r"SCHEDULE\s+OF\s+QUANTIT"],
  "addendum": [r"\bADDENDUM|\bCORRIGENDUM"],
}
def classify_rules(first_pages_text: str) -> str | None:
    for label, pats in ANCHORS.items():
        if any(re.search(p, first_pages_text, re.I) for p in pats):
            return label
    return None          # → Haiku-class LLM classifier on first 3 pages
```
Government packs use fixed headers — rules catch most files cheaply; the LLM handles private-developer packs and mangled scans. Excel files skip OCR entirely (openpyxl direct).

### 6.2 Deadline extraction (the <3-minute promise)

```python
DEADLINE_SCHEMA = {"type":"object","properties":{"deadlines":{"type":"array",
  "items":{"type":"object","properties":{
    "kind":{"enum":["submission","prebid_meeting","clarification","validity",
                    "emd","completion_milestone","other"]},
    "due_at":{"type":"string"},          # ISO 8601 w/ time if stated
    "description":{"type":"string"},
    "source_page":{"type":"integer"},
    "source_quote":{"type":"string","maxLength":200}},
  "required":["kind","due_at","source_page","source_quote"]}}}}

SYSTEM = """Extract every date/deadline from this tender document.
Rules: 1) JSON only, match schema. 2) Every deadline MUST carry source_page
and a verbatim source_quote. 3) NEVER infer a date not printed. 4) Keep
stated local time; do not convert. 5) If ambiguous (e.g., '15 days from
NIT'), return the formula in description and due_at null."""
```
`verify_quotes()` (fuzzy ≥0.85 match on the cited page) gates every extraction; failures render as low-confidence confirm chips, never silent facts. Relative-date formulas ("21 days from pre-bid") are resolved by the deterministic `deadlines.py` calculator once anchor dates are confirmed — date arithmetic never comes from the LLM.

### 6.3 Risk-pattern engine (retrieval → classify → verify)

```python
# app/risk/engine.py — one pattern, one bounded LLM judgment
async def run_pattern(pattern: RiskPattern, opp: Opportunity) -> list[Finding]:
    # 1) candidate clauses via hybrid search (anchors + embeddings), capped
    cands = await retrieve_clauses(opp.id, pattern.anchor_queries, k=12)
    if not cands: return [maybe_absence_finding(pattern, opp)]   # e.g. "no escalation clause AT ALL"
    # 2) LLM classifies each candidate against the pattern spec + org playbook
    out = await llm.complete(system=PATTERN_SYSTEM,
        user=render(pattern.judgment_prompt,
                    clauses=cands,
                    playbook=opp.org.playbook.get(pattern.id, pattern.default_playbook),
                    employer_family=opp.employer_family),
        json_schema=PATTERN_FINDING_SCHEMA, temperature=0)
    findings = [to_finding(f, pattern) for f in parse(out).findings]
    # 3) verification gates
    for f in findings:
        verify_quote(f, opp)                      # verbatim quote on cited page
        f.severity = pattern.severity_rules(f)    # severity is RULE logic, not LLM vibes
    return findings
```

Key design decisions:
- **One pattern = one focused judgment**, not "find all risks in 800 pages" — precision comes from narrow questions with codified context.
- **Severity is deterministic** (e.g., LD without cap = critical; 90-day payment = high for private employer, medium for government per playbook) so two identical tenders always score identically.
- **Absence detection** is first-class: the missing escalation clause on a 3-year project is the most expensive finding in the product.

### 6.4 Deterministic BOQ engine (numbers NEVER from the LLM)

```python
# app/boq/checks.py
import duckdb

UNIT_CANON = {"cum":"m3","cu.m":"m3","m³":"m3","cft":"ft3","rmt":"m","rm":"m",
              "sqm":"m2","sq.m":"m2","mt":"t","tonne":"t","nos":"nos","no.":"nos"}

def normalize(df):                    # from openpyxl/Textract table extraction
    df["unit_canon"] = (df.unit_raw.str.strip().str.lower()
                          .map(UNIT_CANON).fillna(df.unit_raw.str.lower()))
    df["amount_calc"] = (df.qty * df.rate).round(2)
    return df

CHECKS_SQL = """
SELECT src_row, item_code, description,
  amount, amount_calc,
  abs(amount - amount_calc) > 1.0                       AS arith_error,
  rate IS NULL OR rate = 0                              AS blank_rate,
  count(*) OVER (PARTITION BY lower(trim(description)), unit_canon) > 1
                                                        AS possible_duplicate,
  qty > quantile_cont(qty, 0.99) OVER (PARTITION BY unit_canon) * 3
                                                        AS qty_outlier
FROM boq
"""

def run_checks(con: duckdb.DuckDBPyConnection) -> list[BoqDefect]:
    rows = con.execute(CHECKS_SQL).fetchall()
    defects = [make_defect(r) for r in rows
               if r.arith_error or r.blank_rate or r.possible_duplicate or r.qty_outlier]
    totals = con.execute("SELECT sum(amount), sum(amount_calc) FROM boq").fetchone()
    if abs(totals[0] - totals[1]) > 1.0:
        defects.append(grand_total_defect(*totals))     # the classic carry-forward error
    return defects
```

```python
# app/boq/scope_gaps.py — trade checklist cross-reference
def scope_gaps(boq_df, spec_text_index, checklist: TradeChecklist) -> list[Finding]:
    gaps = []
    for item in checklist.items:      # e.g. {"key":"dewatering","triggers":["basement","below ground water table"],"boq_patterns":["dewater","well point"]}
        triggered = any(spec_text_index.contains(t) for t in item.triggers)
        present   = boq_df.description.str.contains("|".join(item.boq_patterns),
                                                    case=False).any()
        if triggered and not present:
            gaps.append(Finding(kind="scope_gap", category=item.key,
                severity=item.severity,
                title=f"No BOQ item for {item.label}",
                detail=f"Spec indicates {item.label} is required "
                       f"(trigger: '{item.matched_trigger}') but no BOQ line covers it.",
                source_page=spec_text_index.page_of(item.matched_trigger),
                suggested_action="Raise clarification or price as assumption"))
    return gaps
```
This is the "omissions & trap identifier" from your original concept — implemented as auditable rules over cross-referenced text, not an LLM guess. The checklists are pure domain knowledge — **drafted first from public sources (Part 14.1) and validated by the QS at the Phase-1 checkpoint** (Part 14.2), not authored by a hired expert on day one.

### 6.5 Artifact generation (facts injected, prose generated, everything gated)

```python
# app/drafting/clarification.py
async def generate_clarification_letter(opp, accepted_findings, pack) -> Artifact:
    facts = build_fact_table(accepted_findings)        # ONLY source of quotes/refs/amounts
    sections = []
    for i, f in enumerate(facts.clarifiable(), 1):
        prose = await llm.complete(system=LETTER_SYSTEM,   # formal Indian tender-query register
            user=render(pack.template("clarification_item"),
                        n=i, finding=f, employer=opp.employer),
            temperature=0.2)
        sections.append(validate(prose, facts))
    return assemble_letter(opp, sections, pack)

def validate(prose, facts):
    for q in find_quoted_text(prose):
        if not facts.has_quote(q):        raise DraftError(f"invented quote: {q[:60]}")
    for ref in find_clause_refs(prose):
        if not facts.has_clause(ref):     raise DraftError(f"uncited clause: {ref}")
    for amt in find_currency_amounts(prose):
        if not facts.has_amount(amt, tol=0.5): raise DraftError(f"invented number: {amt}")
    return prose
```

Three validators — **no-invented-quotes, no-uncited-clauses, no-invented-numbers** — are the product's spine. A clarification letter that misquotes GCC 25.2 to an employer's engineer torches the contractor's credibility and yours. These gates regenerate on failure and hard-fail to human review after 2 attempts.

The **bid/no-bid score** is a transparent weighted sum over accepted findings (weights editable per org), rendered with its factor table — explicitly NOT an ML black box, per the research doc's explainability stance.

---

## PART 7 — FREEMIUM, METERING & BILLING

```python
# app/billing/metering.py
PLAN_LIMITS = {
  "free":  {"reviews_total": 1, "seats": 2},
  "paygo": {"reviews_total": None, "seats": 3},       # pay per review
  "pro":   {"reviews_month": 10, "seats": 10},
  "scale": {"reviews_month": 40, "seats": 25},
}

async def authorize_review(db, org) -> Grant:
    async with db.advisory_lock(f"meter:{org.id}"):
        if org.plan == "free":
            if org.free_review_used:
                raise PaywallError(code="free_exhausted",
                    upsell={"paygo_price_inr": 7500, "plans": ["pro"]})
            await db.mark_free_used(org.id)
            return Grant(kind="free_first_review", watermark=True)
        if org.plan == "paygo":
            return Grant(kind="paygo", requires_payment=True)   # checkout before processing
        used = await db.count_usage(org.id, "review_started", month=current_month())
        if used >= PLAN_LIMITS[org.plan]["reviews_month"] and not await db.has_topups(org.id):
            raise PaywallError(code="quota_exhausted",
                               upsell={"topup_price_inr": overage_price(org)})
        return Grant(kind="plan", watermark=False)
```

- A "review" is metered at **risk/BOQ processing start** (that's where our OCR+LLM cost is), not at export. Re-processing addenda on an already-metered opportunity is free — punishing corrigenda would poison trust.
- Free-tier abuse: one free org per verified phone; disposable-email blocklist; the free review is complete (banner watermark only) — crippled trials die in contractor WhatsApp groups, and those groups are the GTM.
- **Provider abstraction** (Razorpay India / Stripe GCC-UK): webhooks are the sole billing truth, HMAC-verified, idempotent by event-id; GST invoice (SAC 998313) auto-issued for Indian payments; per-tender paygo uses order-based checkout, subscriptions use e-mandates (Razorpay) / Billing (Stripe).

---

## PART 8 — THE AI ASSISTANT ("ASK TENDERSHIELD")

Design rules (identical discipline to §6):
- **Grounded-only:** org documents + rule-pack references + work products. General questions → polite refusal.
- **Tools, not vibes:** `search_docs(query, opportunity_id)`, `list_deadlines(days)`, `filter_findings(category, severity)`, `boq_query(sql_safe_filter)`, `rulepack_lookup(topic)`, `regenerate_artifact_section(artifact_id, section, instruction)` — "tighten clarification #4" performs a versioned edit, never mutates an approved artifact.
- **Citations mandatory:** every factual sentence carries `[doc:<id> p<page>]` or `[pack:<ref>]`; uncited output is blocked by the same validator family as §6.5.
- **Escalation honesty:** "should we bid?" returns the factor table + the org's own score weights + a mandatory "commercial judgment call — review with your team" banner; logged distinctly.

```python
# app/assistant/agent.py (core loop identical to the pattern in §6; scoped by RLS)
ASSISTANT_SYSTEM = """You are TenderShield's assistant for tender review work.
- Answer ONLY from tool results; if nothing relevant returns, say so.
- Cite every factual claim: [doc:<id> p<page>] or [pack:<ref>].
- Legal/commercial conclusions are presented as considerations, never certainties.
- Refuse questions unrelated to this workspace's tenders and contracts."""
```
Metering: free tier 20 messages total; paid fair-use 300/mo soft cap; per-turn token budget alarms (§11.6).

---

## PART 9 — FRONTEND STRUCTURE

```
apps/web (Next.js 15, App Router)
  app/
    (marketing)/           # landing, pricing, /free-tender-check lead magnet
    (auth)/login signup otp forgot
    (app)/
      opportunities/       # board: every live tender, days-to-submission, status
      opportunities/[id]/
        overview           # deadline wall + doc checklist + confirm chips
        risks              # risk workbench: register grouped by category,
                           #   clause popover w/ highlighted source page
        boq                # BOQ workbench: defect table → click-through to row,
                           #   scope-gap panel, unit-normalization review
        artifacts          # clarification letter, assumptions, bid pack (versioned)
        export
      assistant/  billing/  team/  playbook/
  components/ui  lib/api.ts (OpenAPI codegen)
```

UX principles (the "don't make me think" thesis, applied):
- The opportunity board is a **countdown wall** — red < 3 days to submission, amber < 7.
- Findings render as **cards with the quoted clause inline**; one tap opens the source PDF page with the span highlighted (PDF.js) — trust by inspection.
- Estimators think in **money**: every risk card leads with exposure amount where computable (LD/week × cap, retention %, EMD).
- BOQ defects sort by rupee impact, not row order.
- Empty states teach: "Upload the GCC too — 60% of traps live in conditions, not the NIT."

---

## PART 10 — PHASE-WISE DELIVERY PLAN (WITH EXIT CRITERIA)

> **Domain-expertise strategy (founder's decision, recorded):** We are **building the engine first from public sources**, then bringing in a qualified reviewer to validate before any output is sold as reliable. We are NOT hiring or retaining a QS on day one. See **Part 14** for exactly which sources seed the rule-packs now, and precisely when and how the human validator enters. The phases below reflect that sequencing.

### Phase 0 — Bootstrap corpus from public sources (Weeks 1–3) · light build
- **Seed the rule-packs from free/published material** (Part 14.1): CPWD Works Manual & GCC, MoF Manual for Procurement of Works (2nd ed. 2025), GFR 2017, FIDIC/NEC/JCT clause structures, and the dispute-driver taxonomy already in the research doc (HKA CRUX, Arcadis/CMAA). This gives ~50–60% of the risk-pattern scaffolding and the "normal vs dangerous" first-draft thresholds **without a hired expert**.
- Collect **8–12 real tenders** (mix of won/lost) from your own network / design-partner contractors (offer: free lifetime Pro). Public reports teach categories; real tenders teach what these documents actually look like.
- Draft the **first 5 risk patterns + 3 trade checklists** yourself, cited to the public sources above, each carrying a `confidence: unvalidated` flag and a `source` reference in the pack YAML.
- **Exit gate:** the 5 patterns run end-to-end against 3 real tenders and produce plausible, cited findings. (No expert sign-off required yet — that's Phase 1's gate.)

### Phase 1 — MVP build + first validation pass (Weeks 4–15)
- **Build scope:** auth/orgs/RLS · resumable upload + classification + missing-doc checklist · deadline wall (streamed) · top-25 risk patterns w/ playbook comparison · BOQ engine (Excel + digital-PDF tables) · 3 trade checklists · clarification letter + assumptions register + bid/no-bid score · review workbench · Bid Review Pack export · audit log · free-tier + Razorpay (paygo + Pro) · email alerts.
- **The validation checkpoint (mid-Phase-1, ~Week 10):** once the engine produces real output, engage **one experienced QS/contracts manager on a short paid retainer** (a few hours/week or a fixed per-tender fee — NOT a hire) to grade the output on 8–10 real tenders. Their corrections: (a) flip pack patterns from `unvalidated` → `validated`, (b) fix wrong thresholds/severities, (c) seed the eval gold set (§11.5). This is the cheapest possible expert engagement and it happens only after there's something concrete to react to.
- Team: 2 full-stack + you; QS on retainer from ~Week 10.
- **Exit gates:** deadline-extraction F1 ≥ 0.95 on gold set; QS-validated patterns accepted **≥70%** of the time on held-out tenders; **all patterns shown to paying users are `validated`** (unvalidated ones stay hidden or clearly labelled "beta — unverified"); 10 real tenders end-to-end; **first 3 paid conversions**; documented critical-false-negative process.

> **Why validation is gated to Phase 1, not skipped:** public reports get the scaffolding right but cannot answer "is *this* clause dangerous in *this* tender," and cannot grade your engine's output (Part 14.2). You can build and even demo without the QS; you should not let a contractor *rely* on an output that no qualified person has validated. The retainer is small, late, and outcome-focused — but not optional before real reliance.

### Phase 2 — Reviewer depth & stickiness (Weeks 17–26)
- Custom playbooks UI, multi-reviewer approval chain, addendum-diff view, scanned-BOQ OCR hardening, +8 trade checklists, WhatsApp alerts, white-label exports, employer-family baselines (CPWD/NHAI/state PWD/private).
- **Exit gates:** one firm reviews ≥8 tenders/month; review time p50 < 30 min on ≤400-page packs; ≥2 firms expand seats.

### Phase 3 — Baseline lock + variations + data moat (Weeks 27–44)
- Award-vs-tender comparison, baseline freeze (hashes), commercial handover pack, potential-variation inbox (text sources: revised specs, instructions, correspondence — still no drawing CV), notice-deadline countdowns, notice drafts, outcome analytics ("pattern win-rates", "risks that materialized"), API + SSO, Advisor edition for QS consultancies.
- **Exit gate:** ₹10–15L MRR equivalent; ≥5 projects using baseline weekly; ≥5 real change events documented pre-completion (the research doc's bar).

### Phase 4 — GCC pack (Quarter 4+)
- FIDIC sub-clause deadline engine, particular-conditions deviation detection, bilingual EN/AR artifacts, business-day/holiday calendars, Stripe AED, 3 committed UAE/KSA design partners BEFORE build (same Phase-0 playbook), claims/QS-consultancy channel per the research doc's GCC entry strategy.

### Phase 5 — UK pack
- NEC4 EW/CE clocks + Z-clause deviation, JCT amendment comparison, accountant/QS channel, Stripe GBP.

### Phase 6 — Gated experiments (only if 1–3 healthy)
- Drawing intelligence (title-block/revision registers first, region-diff later) — gated by the research doc's rule: only after text/BOQ trust is proven.
- Integrations marketplace (Procore/Aconex/SharePoint adapters), private clause library exchange, mobile site-evidence capture.

**Standing kill/continue gates (verbatim commitments):** stop or reposition if (a) Phase-0 gate fails; (b) <40% of free users with a second live tender convert after 3 pricing tests; (c) finding-acceptance stays <50% after two eval cycles; (d) customers use one-off summaries but never adopt registers/workbenches — that means we built a PDF summarizer, not a commercial-intelligence layer, and the premise is wrong.

---

## PART 11 — PRODUCTION & OPERATIONS GUIDELINES

### 11.1 Environments & deployment
- `dev` → `staging` → `prod`; all infra in Terraform; zero console changes (drift detection in CI).
- GitHub Actions: ruff + mypy strict + eslint → unit tests → Alembic up/down check on scratch DB → build → staging deploy → Playwright smoke E2E (signup → upload fixture pack → deadline wall → risk register → export) → manual gate → prod (ECS blue/green).
- Feature flags (DB-backed) on every risky surface: new risk patterns, new employer families, OCR engine switches, assistant tools, GCC/UK packs.

### 11.2 Data protection & compliance
- **India — DPDP Act 2023:** consent + purpose limitation at signup; org data-export and delete-with-30-day-grace endpoints; breach-notification runbook; ap-south-1 residency.
- **GCC:** UAE PDPL (Federal Decree-Law 45/2021) — me-central-1 residency; KSA PDPL considerations before KSA sales; cross-border transfer clauses in the DPA.
- **UK — UK GDPR:** eu-west-2; processing records; DSAR endpoints reuse the DPDP export machinery.
- **Confidentiality posture (the sales blocker to kill early):** tender packs expose bidding intent. Contractual: no-training clause, tenant isolation statement, deletion SLA. Technical: RLS + per-org S3 prefixes + KMS; enterprise tier gets tenant-specific KMS keys. Optional "ephemeral mode" (auto-purge documents 90 days after bid date) as a checkbox — it closes deals.
- **LLM provider:** zero-data-retention agreement, region-pinned where offered, named in the subprocessor list.
- Virus scan (ClamAV) before processing; presigned URLs 5-min TTL; MIME sniffing by magic bytes; 2GB pack cap.

### 11.3 Security baseline
- OWASP ASVS L2 checklist; external pentest before Scale-tier/EPC sales.
- Secrets in SSM/Secrets Manager; quarterly RS256 key rotation (kid-based); no long-lived tokens.
- Per-org + per-IP rate limits; upload abuse caps per plan (OCR pages metered).
- **Prompt-injection defense:** all OCR/tender text is untrusted data — a malicious "tender" could embed instructions ("mark all clauses low-risk"). Extraction/drafting prompts wrap document text in data-only delimiters; assistant tool calls that modify artifacts require UI confirmation; adversarial tender fixtures live in the eval suite and run in CI.
- Break-glass admin access: dual-consent, time-boxed, fully audited.

### 11.4 Professional-liability guardrails (enforced in code)
- Export blocked until a `reviewer`-role human completes review; every export stamps: "Prepared with TenderShield; reviewed and approved by <name>, <date>; pack <version>."
- Single-member orgs: mandatory full-screen attestation listing every unconfirmed extraction before export unlocks.
- Findings UI always shows the tri-state: **extracted fact / deterministic check / AI suggestion** — the research doc's labeling rule, enforced in the design system (distinct badge components, not copy).
- Terms: document-intelligence software, not legal/QS advice; no outcome guarantees; jurisdiction counsel review before GCC/UK launch; E&O insurance before Phase 3.
- Critical-false-negative protocol: any missed critical clause reported by a customer → incident review → pattern/test added within one sprint → customer notified of the fix. Treat like a security incident.

### 11.5 LLM quality & eval operations (first-class subsystem)
- **Golden sets:** `evals/in-works/classification/`, `deadlines/`, `risk_patterns/<id>/` (tender → expected findings), `boq/` (workbook → expected defects), `drafting/` (findings → acceptable letters). Seeded by Phase-0 gold data; grown from every production correction.
- CI: any rule-pack or prompt change runs the full eval; per-pattern precision/recall dashboards; a >2pt F1 drop on deadlines or any critical pattern blocks merge.
- **Per-pattern telemetry in prod:** acceptance rate, edit distance, rejection reasons (structured dropdown: wrong clause / wrong severity / not a risk here / duplicate). Weekly review with the QS; worst pattern gets fixed first.
- Model upgrades ship in shadow mode for 2 weeks (parallel generation, no display); promote only if acceptance-weighted quality improves.
- Monthly human rubric audit: QS scores 10 sampled outputs 1–5 on accuracy/completeness/tone; trend charted next to MRR — quality and revenue reviewed in the same meeting, deliberately.

### 11.6 Observability, SLOs & cost
- SLOs: upload→deadline wall p95 < 3 min; full review p95 < 25 min; API availability 99.5%.
- **The submission-deadline notifier is the most important cron in the company** — a missed alert can cost a customer a bid. Dual-path email+WhatsApp, delivery receipts checked, failures page on-call at CRITICAL.
- Dashboards: queue depth, OCR fallback rate, tokens-per-review (unit economics as a graph), validator rejection rate, per-pattern precision, paywall hits.
- Cost guardrails: per-review token budget with alerts; large-pack sampling strategy (process GCC/SCC/NIT fully; specs processed by relevance-ranked sections with a "process everything" paid override).

### 11.7 Backup & DR
- RDS PITR + nightly snapshots (35-day retention); S3 versioning + cross-region replication; quarterly restore drill (RTO 4h / RPO 15 min, documented).
- **Deadline continuity:** each org's upcoming-deadlines digest is emailed daily — if the platform ever goes down, yesterday's digest is already in their inbox.

---

## PART 12 — RISKS & HONEST WARNINGS

1. **Trust is binary.** One misquoted clause or hallucinated deadline in front of an MD ends the account and the referral chain. The three validators (§6.5), quote verification (§6.2), and the critical-false-negative protocol (§11.4) are the product, not hardening.
2. **The space is consolidating.** Document Crunch → Trimble (agreement Apr 2026) proves the category and arms an incumbent. Your defensible ground is exactly what they aren't doing: India-first employer-family packs (CPWD/NHAI/state PWD), per-tender pricing for the mid-market, and the contractor-side outcome graph. Speed through Phases 0–3 matters; a US feature war does not.
3. **Arched.ai adjacency (India):** strong on tender *discovery* across portals; your wedge is the *review/assurance/artifact* layer. Watch for their expansion; consider partnership before rivalry.
4. **OCR quality ceiling:** scanned BOQs and 10th-generation photocopies will produce garbage extractions. The product must degrade honestly — "pages 40–55 unreadable, upload Excel BOQ" beats confident nonsense. Measure OCR-fallback and unreadable rates from day one.
5. **Long sales cycles at the top, price sensitivity at the bottom:** the research doc's answer stands — per-tender paygo wedge for small contractors, founder-led sales to mid-market, advisor channel for leverage. Do not chase EPC enterprise deals before Phase 3 governance exists.
6. **Your scope reflex (standing warning).** Six phases are written here; only Phase 1 exists until three firms pay. No drawing CV, no marketplace, no integrations, no GCC pack before their gates are green. The MCP project, the 11-idea list, and the original 14-module TenderShield architecture all show the same pattern — the gates in Part 10 are the counterweight. Hold to them.

---

## PART 13 — 30-DAY ACTION CHECKLIST

1. **Week 1:** sign the QS/contracts-manager advisor; open conversations with 8 contractors (your network + industry associations); draft the pilot offer (₹25k/quarter, includes the QS's review of outputs).
2. **Week 2:** collect the first 10 closed tenders + outcomes; hand-annotate gold findings for 3 of them yourself — you will learn the domain faster than any document can teach, and the annotations become the first eval set.
3. **Week 3:** repo + CI + Terraform skeleton + auth module (§5) + resumable upload → classification path on real packs.
4. **Week 4:** deadline extraction on the gold set, measure F1; demo the deadline wall + doc checklist to the 3 committed firms; sign pilots.
5. **Then, in value order:** risk patterns (the five from interviews first) → BOQ engine → clarification letter → billing. Not the assistant, not the score, not the GCC pack.

*End of document — v1.0. Revisions should be driven by Phase-0 findings and pilot feedback, not by feature additions.*

---

## PART 14 — DOMAIN-EXPERTISE STRATEGY (BUILD FIRST, VALIDATE LATER)

**Founder decision recorded:** build the engine now from public sources; bring in a qualified reviewer to validate before any output is relied on commercially. No expert hire on day one. This part documents exactly how that works so the plan is self-contained.

### 14.1 What we build from FREE / public sources (no expert needed)

These seed ~50–60% of the rule-pack scaffolding immediately:

| Source (public) | What it gives the product |
|---|---|
| **CPWD Works Manual + CPWD GCC** | The baseline "standard" clauses for Indian government civil works — the reference a tender's clause is *compared against* to detect deviations/deletions |
| **MoF Manual for Procurement of Works, 2nd ed. (2025)** + **GFR 2017** | Procedural rules, standard timelines, EMD/security norms — reference material for deadline and security-form patterns |
| **FIDIC / NEC4 / JCT clause structures** (published outlines) | Baseline forms for the GCC/UK packs (Phases 4–5); particular-conditions deviation is measured against these |
| **Dispute-driver research** (HKA CRUX 2025, Arcadis/CMAA 2025, cost-overrun studies — all in the research doc) | The empirical taxonomy of *which categories* cause the most money loss → prioritized list of risk patterns to build first (payment, escalation, LD, ground conditions, scope) |
| **Law-firm / QS-consultancy published alerts** ("top FIDIC particular-condition traps" etc.) | Concrete examples of dangerous clause wording — raw material for pattern detection specs and negative examples |
| **State PWD standard tender documents** (published on portals) | Employer-family baselines (NHAI/MoRTH, railways, state PWDs) |

**How they enter the codebase:** every risk pattern and trade checklist created this way carries, in its pack YAML, a `source:` field (the public document + section) and a `confidence: unvalidated` flag. Nothing is invented by the LLM; if a threshold isn't supported by a cited source, it's marked as an assumption to be checked.

```yaml
# rulepacks/in-works/risk_patterns/price_escalation.yaml (Phase-0, pre-validation)
id: price_escalation_barred
category: escalation
severity_rule: "critical if project_duration_months > 18 else high"
source: "Derived from CPWD GCC clause 10CA (escalation) + HKA CRUX 2025 (price
         volatility a top-5 dispute driver)"
confidence: unvalidated        # flips to 'validated' at Phase-1 checkpoint
default_playbook:
  acceptable: "escalation formula present for contracts > 18 months"
  flag_when: "escalation clause deleted or 'firm price' stated for long-duration works"
```

### 14.2 What public sources CANNOT do (why the human still enters)

Two gaps no report closes:

1. **Last-mile contextual judgment.** A report says "payment terms are a common dispute driver." It cannot say "90-day payment is normal for *this* government employer but dangerous for *this* private developer given *this* retention stack." That tacit calibration lives in a practitioner's head and is exactly what contractors currently pay QS consultants for — which is *why it's a product* and not a downloadable PDF.
2. **Ground truth to grade the engine.** Even with perfect public inputs, someone qualified must look at *your product's actual output on a real tender* and say "correct call" / "you missed the big one." No document can score your engine. This is the irreducible role — and it's why validation can't be skipped entirely, only *sequenced late*.

### 14.3 When and how the validator enters (minimal, late, outcome-focused)

- **Timing:** mid-Phase-1 (~Week 10), only once the engine produces real output. Not day one.
- **Engagement model (cheapest that works):** short **paid retainer** — a few hours/week, or a fixed fee per tender reviewed. **Not a hire, not equity necessarily.** A practicing QS or a semi-retired contracts manager reviewing 8–10 tenders is enough to validate the top-25 patterns.
- **What they actually do:** grade output on real tenders → their corrections (a) flip patterns `unvalidated → validated`, (b) fix thresholds/severities, (c) become the eval gold set (§11.5). Structured, bounded, reactive to concrete output — the highest-leverage possible use of expert hours.
- **The product-level rule that makes this safe:** patterns carry a validation state, and **only `validated` patterns are shown to paying users as reliable findings.** Unvalidated patterns are hidden or badged "beta — unverified, confirm independently." So you can build and ship the *validated core* while the long tail matures. Liability (§11.4) is covered because every relied-upon finding traces to a validated pattern + a human reviewer's approval on that tender.

### 14.4 Can the founder be the expert?

If you have construction-contracts / estimation / QS background yourself, you *are* substantially the validator — you'd draft patterns from the public sources and only spot-check against an external reviewer occasionally, collapsing 14.3 into a lighter touch. If you're coming purely as a builder, you need the one retained reviewer as described. Either way: **no research budget, no full-time hire — one qualified human in the loop, engaged late and cheaply.** Design-partner contractors reviewing outputs provide a rougher parallel signal but validate rather than author, and are not a full substitute for the ground-truth grading in 14.2.

### 14.5 Summary of the sequencing

```
Phase 0 (Wk 1-3): build rule-packs from PUBLIC sources → patterns = 'unvalidated'
Phase 1 build (Wk 4-9): engine produces real output on real tenders
Phase 1 validation (Wk ~10): retained QS grades output → patterns → 'validated',
                              corrections seed eval gold set
Phase 1 gate: only 'validated' patterns shown as reliable; 3 paid conversions
Ongoing: production reviewer-corrections keep flipping/refining patterns —
         the correction loop is the compounding moat (§11.5)
```

*This part supersedes any earlier "retain a QS in Phase 0" phrasing. The engine is built first; the expert validates before commercial reliance, on a small late retainer — not before.*

---

## PART 15 — PAYMENT & CHECKOUT (END-TO-END: UI + FLOW + CODE)

This part completes the money path: pricing page → paywall trigger → checkout (Razorpay India / Stripe GCC-UK) → activation → GST receipt → self-serve billing management. The backend logic in §7 is the source of truth for limits and webhooks; this part adds the screens, the click-by-click flows, and the integration code.

### 15.1 The money path (single diagram)

```
Marketing /pricing ─┐
                    ├─► User hits a paywall (free review used, or paygo tender,
In-app upgrade CTA ─┘   or monthly quota exhausted)  [§7.1 PaywallError]
        │
        ▼
  CHECKOUT MODAL  (picks provider by org.country: IN→Razorpay, AE/SA/QA/GB→Stripe)
        │
        ├─ paygo (per-tender):  create ORDER  → provider checkout → pay
        └─ subscription (Pro/Scale): create SUBSCRIPTION/e-mandate → authorize
        │
        ▼
  provider redirect/callback (client)   ── NEVER trusted for activation ──┐
        │                                                                 │
        ▼                                                                 ▼
  PENDING screen ("confirming payment…")            WEBHOOK (server, signed)  ← truth
        │                                                    │
        │  client polls GET /billing/status                 ├─ verify HMAC (§7.2)
        │                                                    ├─ idempotent by event id
        ▼                                                    ├─ activate plan / mark
  SUCCESS screen  ◄──────────────────────────────────────── │   review paid, add credits
  (plan active / tender unlocked) + emailed GST receipt      └─ write audit + usage_event
```

**Golden rule (restated, because it's the #1 payments bug):** the success redirect from Razorpay/Stripe **never** activates anything. Only the verified webhook does. The client just polls status until the webhook has flipped it. This prevents both "user closed the tab and lost their plan" and "user forged a success URL."

### 15.2 Pricing page (marketing, `/pricing`)

Content, India view (currency auto-switches by geo/IP → INR/AED/GBP; user can override):

| | **Free** | **Pay-per-tender** | **Pro** | **Scale** |
|---|---|---|---|---|
| Price | ₹0 | ₹7,500 / tender | ₹24,999 / mo | ₹74,999 / mo |
| Tender reviews | 1 (one-time) | unlimited, pay each | 10 / mo | 40 / mo |
| Seats | 2 | 3 | 10 | 25 |
| Risk register + BOQ checks + clarification letter | ✅ | ✅ | ✅ | ✅ |
| Custom playbook, white-label pack | — | — | ✅ | ✅ |
| Baseline lock + variations (Phase 3) | — | — | — | ✅ |
| API + SSO | — | — | — | ✅ |
| WhatsApp deadline alerts | — | — | ✅ | ✅ |
| Overage | — | — | ₹4,999/review | ₹3,499/review |

UX rules:
- **Primary CTA differs by tier:** Free → "Start free" (signup); Paygo → "Review a tender"; Pro/Scale → "Start Pro" (checkout).
- Annual toggle (2 months free) for Pro/Scale — Stripe/Razorpay both support annual price IDs.
- GST note: "Prices exclusive of 18% GST. GST invoice issued on payment." (Indian buyers expect this and it must be true.)
- Trust row under the table: "No card required for free review · Cancel anytime · Data never used for training · Hosted in India (ap-south-1)."
- FAQ accordion: what counts as a review, do addenda cost extra (no — §7), refund policy, is my tender data private.

### 15.3 Paywall component (in-app trigger)

When the API returns `PaywallError` (§7.1), the client renders a contextual paywall — copy chosen by the error `code` so the message matches the moment:

```tsx
// components/billing/PaywallModal.tsx
const COPY: Record<string, {title: string; sub: string; cta: string}> = {
  free_exhausted: {
    title: "You've used your free tender review",
    sub: "Unlock this tender now for ₹7,500, or go Pro for 10 reviews a month.",
    cta: "Unlock this tender",
  },
  quota_exhausted: {
    title: "You've hit your monthly reviews",
    sub: "Add a top-up review, or move up a plan for more headroom.",
    cta: "Add a review",
  },
  paygo_payment_required: {
    title: "Review this tender",
    sub: "Pay-per-tender: ₹7,500. Full risk register, BOQ checks and clarification letter.",
    cta: "Pay & review",
  },
};

export function PaywallModal({ code, orgCountry, onClose }: PaywallProps) {
  const c = COPY[code] ?? COPY.paygo_payment_required;
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>{c.title}</DialogTitle>
        <p className="text-muted-foreground">{c.sub}</p>
        <PlanMiniTable country={orgCountry} highlight={code === "free_exhausted" ? "pro" : "paygo"} />
        <Button onClick={() => startCheckout({ code, orgCountry })}>{c.cta}</Button>
        <button className="text-sm underline" onClick={onClose}>Not now</button>
      </DialogContent>
    </Dialog>
  );
}
```

The paywall is a conversion surface, not a wall: it always states exactly what they get, shows the cheaper paygo option next to the plan, and lets them dismiss (dismissals are logged — a spike means pricing is wrong).

### 15.4 Checkout — backend endpoints

```python
# app/billing/routes.py
from fastapi import APIRouter, Depends, Request
router = APIRouter(prefix="/billing")

@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, p=Depends(require("admin")), db=Depends(get_db)):
    """Creates a provider order (paygo) or subscription (Pro/Scale).
       Returns provider-specific handles for the client SDK. Activates NOTHING."""
    org = await db.get_org(p.org_id)
    provider = provider_for(org.country)          # Razorpay (IN) | Stripe (AE/SA/QA/GB)
    if body.kind == "paygo":
        amount = price_paygo(org.country)         # in minor units (paise/fils/pence)
        order = await provider.create_order(
            org=org, amount=amount, currency=cur(org.country),
            notes={"org_id": str(org.id), "kind": "paygo",
                   "opportunity_id": str(body.opportunity_id)})
        await db.insert_payment_intent(org.id, provider.name, order.id,
                                       kind="paygo", ref=body.opportunity_id,
                                       amount=amount, status="created")
        return CheckoutResponse(provider=provider.name, order=order.public_handle())
    else:  # subscription
        sub = await provider.create_subscription(
            org=org, plan=body.plan, period=body.period,   # monthly|annual
            notes={"org_id": str(org.id), "plan": body.plan})
        await db.insert_payment_intent(org.id, provider.name, sub.id,
                                       kind="subscription", plan=body.plan,
                                       status="created")
        return CheckoutResponse(provider=provider.name, subscription=sub.public_handle())

@router.get("/status")
async def billing_status(p=Depends(require("viewer")), db=Depends(get_db)):
    """Client polls this after checkout until webhook flips state."""
    org = await db.get_org(p.org_id)
    return {"plan": org.plan,
            "pending": await db.has_pending_intent(org.id),
            "last_event_at": await db.last_billing_event_at(org.id)}
```

### 15.5 Razorpay integration (India) — client + webhook

**Client (Next.js), order/paygo flow:**
```tsx
// lib/checkout/razorpay.ts
export async function startRazorpay(order: RazorpayHandle, onDone: () => void) {
  await loadScript("https://checkout.razorpay.com/v1/checkout.js");
  const rzp = new (window as any).Razorpay({
    key: order.keyId,                       // public key id only
    order_id: order.orderId,
    amount: order.amount, currency: order.currency,
    name: "TenderShield",
    description: order.description,          // "Tender review — <opportunity title>"
    prefill: { email: order.email, contact: order.phone },
    theme: { color: "#0F172A" },
    handler: () => {                        // fires on client success
      // DO NOT unlock here. Go to pending screen; server webhook decides.
      window.location.href = `/billing/pending?ref=${order.orderId}`;
    },
    modal: { ondismiss: onDone },
  });
  rzp.open();
}
```
For **subscriptions** Razorpay uses `subscription_id` + UPI Autopay / card e-mandate; the client opens the same checkout with `subscription_id` instead of `order_id`. Recurring charges then arrive as `subscription.charged` webhooks.

**Webhook (server) — the only thing that activates a plan:**
```python
# app/billing/webhooks_razorpay.py
@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db=Depends(get_db)):
    body = await request.body()
    sig = request.headers["X-Razorpay-Signature"]
    expected = hmac.new(RZP_WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(400, "bad signature")

    evt = json.loads(body)
    event_id = evt["id"]
    if await db.webhook_already_processed(event_id):       # idempotency
        return {"ok": True}

    typ = evt["event"]
    async with db.tx():
        if typ == "order.paid":                            # paygo success
            order = evt["payload"]["order"]["entity"]
            org_id = order["notes"]["org_id"]
            await db.credit_paygo_review(org_id,
                    opportunity_id=order["notes"].get("opportunity_id"))
            await db.record_usage(org_id, "review_paid", ref=order["id"])
        elif typ in ("subscription.activated", "subscription.charged"):
            sub = evt["payload"]["subscription"]["entity"]
            org_id = sub["notes"]["org_id"]
            await db.activate_plan(org_id, plan=sub["notes"]["plan"],
                                   period_end=to_dt(sub["current_end"]))
        elif typ in ("subscription.halted", "subscription.cancelled"):
            await db.downgrade_to_free_at_period_end(evt["payload"]["subscription"]["entity"]["notes"]["org_id"])
        await db.mark_webhook_processed(event_id)
        await audit(db, action=f"billing.{typ}", detail={"event_id": event_id})
    await enqueue_gst_receipt(evt)                         # §15.8
    return {"ok": True}
```

### 15.6 Stripe integration (GCC / UK) — client + webhook

**Client:** use Stripe Checkout (hosted) for lowest PCI burden — redirect, don't embed.
```tsx
// lib/checkout/stripe.ts
export async function startStripe(session: { url: string }) {
  window.location.href = session.url;      // Stripe-hosted Checkout page
}
```
Server creates the session (mode `payment` for paygo, `subscription` for Pro/Scale), with `success_url=/billing/pending?ref={CHECKOUT_SESSION_ID}` and `cancel_url=/pricing`.

**Webhook:**
```python
# app/billing/webhooks_stripe.py
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers["Stripe-Signature"]
    try:
        evt = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, "bad signature")

    if await db.webhook_already_processed(evt["id"]):
        return {"ok": True}
    async with db.tx():
        t = evt["type"]; obj = evt["data"]["object"]
        if t == "checkout.session.completed" and obj["mode"] == "payment":
            await db.credit_paygo_review(obj["metadata"]["org_id"],
                    opportunity_id=obj["metadata"].get("opportunity_id"))
        elif t in ("customer.subscription.created","customer.subscription.updated"):
            await db.activate_plan(obj["metadata"]["org_id"],
                    plan=obj["metadata"]["plan"],
                    period_end=to_dt(obj["current_period_end"]),
                    status=obj["status"])          # active|past_due|canceled
        elif t == "customer.subscription.deleted":
            await db.downgrade_to_free_at_period_end(obj["metadata"]["org_id"])
        elif t == "invoice.payment_failed":
            await db.flag_past_due(obj["metadata"].get("org_id"))   # dunning (§15.9)
        await db.mark_webhook_processed(evt["id"])
    return {"ok": True}
```

### 15.7 Post-checkout screens
- **`/billing/pending`** — spinner + "Confirming your payment with the bank… this takes a few seconds." Polls `GET /billing/status` every 2s (max 60s). On flip → success. On timeout → "Taking longer than usual — we'll email you the moment it's confirmed, and your tender will unlock automatically." (Webhooks sometimes lag; never dead-end the user.)
- **`/billing/success`** — green check, "Pro is active" / "Tender unlocked", primary button back to the exact opportunity they were paying to review (deep-link preserved via `opportunity_id` in metadata). Receipt-emailed line.
- **`/billing/cancelled`** — soft landing back to pricing, "No charge was made," paygo option surfaced again.

### 15.8 GST invoicing (India — must be correct, it's a tax product)
On every successful Indian payment, auto-generate a GST invoice: seller entity + GSTIN; SAC **998313** (confirm with your CA); 18% GST (CGST+SGST if buyer same-state, else IGST, from buyer GSTIN state); sequential statutory invoice number; buyer legal name + GSTIN captured at checkout; PDF emailed + stored.
```python
# app/billing/gst_invoice.py
async def issue_gst_invoice(org, payment):
    seller_state = SELLER_STATE_CODE
    buyer_state  = org.gstin[:2] if org.gstin else None
    intra = buyer_state == seller_state
    base = payment.amount_ex_gst
    lines = ([("CGST", 9), ("SGST", 9)] if intra else [("IGST", 18)])
    inv = build_invoice(number=await next_invoice_no(), seller=SELLER, buyer=org,
                        sac="998313", base=base, taxes=lines, total=payment.amount)
    pdf = render_invoice_pdf(inv)                           # WeasyPrint
    await store_and_email(org, pdf, inv)
```

### 15.9 Billing management (self-serve, `/billing`)
- **Current plan card:** plan, renewal date, reviews used/remaining (live from `usage_events`), seats used.
- **Change plan:** upgrade (immediate, prorated) / downgrade (period end); both providers re-emit webhooks that flip `org.plan`.
- **Payment method:** via provider portals — Stripe Billing Portal / Razorpay update-mandate. Don't build card-storage UI (PCI scope).
- **Invoices/receipts:** list + download.
- **Cancel:** at period end, keeps access until then, downgrades to Free (data + past artifacts stay readable). One-question exit survey.
- **Dunning (past_due):** banner + 3 retry emails over 7 days; grace before downgrade; never delete data on non-payment.

### 15.10 Testing & go-live checklist for payments
- Provider **test mode** end-to-end in staging: success, failure, user-abandon, delayed webhook, duplicate webhook (idempotency), tampered signature (must 400).
- Nightly reconciliation: provider settlements vs `payment_log` applied total; alert on mismatch.
- Amounts always in **minor units**; never float rupees.
- Webhook endpoint public but signature-gated, rate-limited, returns 200 fast (heavy work enqueued).
- Refund path: admin → provider API → reversed usage credit → audit. Refund policy on pricing page.
- Before first real charge: PCI SAQ-A posture (hosted checkout), pricing/T&Cs/refund/cancellation pages live, GST registration + SAC confirmed with CA, sequential gap-free invoice numbers verified.

*Part 15 completes the money path with the webhook as the single source of truth throughout.*

---

## PART 16 — INTERNAL ADMIN CONSOLE + ANALYTICS & MONITORING

This is the back-office you operate the business from: customer support, payment operations, system-health monitoring, and business analytics. It is a **separate application** from the customer product, with its own hardened auth, because it is the single most dangerous surface in the system — a compromised admin sees every contractor's tender data. Nothing here bypasses the audit log.

### 16.1 Why a separate admin app (not an `is_admin` flag)
- **Blast radius:** staff auth compromise must not equal customer-app compromise. Separate app, separate domain, network-restricted.
- **Different threat model:** staff get SSO + mandatory MFA + IP allowlist; customers don't.
- **No direct DB access for anyone.** Every read/write against customer data goes through the admin API, which enforces staff-RBAC and writes an audit row. "Just run a quick SQL on prod" is banned.

```
admin.tendershield.internal  (Next.js, VPN/IP-allowlisted, not public DNS)
        │  staff SSO (Google Workspace / Okta) → short-lived staff JWT
        ▼
  ADMIN API (FastAPI, staff-only guard)
        │  staff-RBAC · every action → admin_audit_log · reason-string required
        ▼
  same PostgreSQL — admin queries bypass org RLS via a dedicated
  SECURITY DEFINER role that is itself fully logged
```

### 16.2 Staff auth & roles (hardened)
```python
# app/admin/auth.py
STAFF_ROLES = {
  "support":   0,   # read customer data, resend receipts, open/close tickets
  "billing":   1,   # + refunds, manual plan changes, invoice re-issue
  "ops":       2,   # + feature flags, retry webhooks/jobs, rule-pack validate
  "superadmin":3,   # + staff management, impersonation approval, data deletion
}

async def current_staff(request: Request) -> Staff:
    claims = verify_staff_sso_jwt(request)          # Okta/Google Workspace OIDC
    require_mfa(claims)                             # hard fail if amr lacks mfa
    require_ip_allowlisted(request.client.host)     # office/VPN CIDR only
    return Staff(id=claims["sub"], email=claims["email"], role=claims["staff_role"])

def staff_require(min_role: str):
    async def guard(s: Staff = Depends(current_staff),
                    reason: str = Header(..., alias="X-Action-Reason")):
        if STAFF_ROLES[s.role] < STAFF_ROLES[min_role]:
            raise HTTPException(403, "insufficient_staff_role")
        request_ctx.set_reason(reason)              # captured into admin_audit_log
        return s
    return guard
```
```sql
CREATE TABLE admin_audit_log (          -- append-only, separate from customer audit_log
  id BIGSERIAL PRIMARY KEY,
  staff_id UUID NOT NULL, staff_email TEXT NOT NULL,
  action TEXT NOT NULL, target_org_id UUID, target_user_id UUID, target_object TEXT,
  reason TEXT NOT NULL, before JSONB, after JSONB,
  ip INET, at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 16.3 Support console (address people's issues)
- **Org/user search** — by email, phone, GSTIN, org name, payment id, notice/opportunity id. One fuzzy box.
- **Org 360 view** — plan, usage, seats, signup, last activity, open tickets, recent payments, recent errors — one page.
- **Opportunity drill-in (read-only default)** — see what the customer sees: processing status, per-page OCR success/failure, findings produced, where a job is stuck.
- **Guided fixes** — buttons for common tickets: re-run OCR, re-queue stuck job, resend deadline alert, resend GST receipt, extend free review, grant goodwill credit — each audited, not a raw DB edit.
- **Ticket panel** — lightweight or embedded from a helpdesk; linked to the org.

### 16.4 Safe impersonation ("view as customer")
- **Read-only by default.** Write-impersonation requires `superadmin` approval + logged customer consent.
- **Time-boxed** (max 30 min), **reason mandatory**, **banner shown**, **every action tagged** `impersonated_by` in both audit logs.
- Customer notified: "TenderShield support accessed your workspace on <date> to resolve ticket #<id>."
```python
@admin_router.post("/orgs/{org_id}/impersonate")
async def impersonate(org_id: UUID, mode: str,           # 'read'|'write'
                      s=Depends(staff_require("support" if mode=="read" else "superadmin"))):
    if mode == "write":
        await require_customer_consent(org_id)
    token = mint_impersonation_token(org_id, staff=s, mode=mode, ttl_min=30)
    await admin_audit(s, "impersonation.started", target_org_id=org_id, after={"mode": mode})
    await notify_customer_of_access(org_id, s, mode)
    return {"token": token, "expires_in": 1800}
```

### 16.5 Payment operations + payment logging system
```sql
CREATE TABLE payment_log (              -- append-only financial event ledger
  id BIGSERIAL PRIMARY KEY,
  org_id UUID NOT NULL,
  provider TEXT NOT NULL,               -- razorpay|stripe|internal
  provider_event_id TEXT,               -- dedup/trace to provider dashboard
  event_type TEXT NOT NULL,             -- order.paid|subscription.charged|refund|
                                        -- chargeback|manual_credit|plan_change|invoice_issued|
                                        -- payment_failed|webhook_received|webhook_verify_failed
  amount_minor BIGINT, currency TEXT,   -- minor units; NULL for non-money events
  status TEXT NOT NULL,                 -- received|verified|applied|failed|reversed
  ref_kind TEXT, ref_id UUID,
  raw JSONB NOT NULL,                   -- full provider payload (PII-redacted where needed)
  actor TEXT, reason TEXT,
  at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON payment_log (org_id, at DESC);
CREATE INDEX ON payment_log (provider, provider_event_id);
```
Every webhook writes a `payment_log` row *before* it acts (`status='received'`), then updates to `verified`/`applied`/`failed` — so even signature-failed and duplicate webhooks are captured (fraud/debugging). Customer audit log records the *effect*; payment_log records the *money*.

Payment ops screens: **transaction viewer** (filter, drill to raw, link to provider dashboard); **refund** (`billing` role, reason mandatory, reverses usage credit, audited); **manual plan change / credit**; **reconciliation dashboard** (nightly provider-settlement vs `payment_log` applied total, per day, mismatch-alert list — the single most important financial-integrity screen); **failed-payment/dunning queue**; **GST invoice register** with sequential-number gap detection.

### 16.6 Analyser dashboard — system performance & health
- Request latency (p50/p95/p99) per endpoint; error rate; availability vs 99.5% SLO.
- **Job queue health** — depth + age per Celery queue (OCR, recon, risk, drafting); alarm on queue age > threshold.
- **Pipeline funnel timing** — upload→deadline-wall p95 (<3 min promise), full-review p95 (<25 min) tracked live.
- **OCR health** — success vs fallback vs unreadable rate.
- **LLM health & cost** — tokens per review (unit economics as a graph), latency, error/timeout, validator-rejection rate (§6.5).
- **Webhook health** — received vs verified vs failed, processing lag.
- **Infra** — DB connections/CPU, Redis memory, ECS health, error-budget burn.
- **Deadline-notifier watchdog (highest criticality):** every scheduled alert must have a delivery receipt; any missed send pages on-call at CRITICAL.

### 16.7 Analyser dashboard — business analytics
- **Acquisition:** signups, activation (signup→first review), source.
- **Conversion:** free→paid, paygo vs subscription mix, **second-tender conversion** (§7 key metric), time-to-convert.
- **Revenue:** MRR/ARR/ARPU, paygo revenue, expansion, by geography.
- **Retention/churn:** logo + revenue churn, cohorts, cancel reasons, past-due recovery.
- **Product usage:** reviews/org/month, feature adoption, export rate.
- **Quality (§11.5):** per-pattern acceptance/rejection, edit-distance trend, extraction F1 on live gold set — quality and revenue on one board.
- **Kill-gate tiles:** the Part 10 gates (second-tender conversion <40%, finding-acceptance <50%) rendered as live tiles that turn red when breached — the gates become a dashboard.

### 16.8 Alerting policy
| Severity | Examples | Response |
|---|---|---|
| **CRITICAL (page)** | deadline-notifier failure · reconciliation mismatch · webhook verify-failure spike · availability <99% · DB down | Immediate |
| **HIGH (Slack + notify)** | OCR queue age >15 min · draft p95 > SLO · validator-rejection spike · dunning surge | Same-day |
| **WARN (Slack)** | token spend above budget · unreadable-OCR rising · error-budget burn | Daily review |

### 16.9 Admin console — build sequencing
- **Phase 1 (with MVP):** support search + org 360 (read-only), payment_log + transaction viewer, resend receipt / re-run OCR / re-queue buttons, basic Grafana health board, refund via provider dashboard (manual).
- **Phase 2:** safe impersonation, reconciliation dashboard, dunning queue, rule-pattern validate/reject UI, business-analytics board with kill-gate tiles.
- **Phase 3:** native analyser dashboards, cohort/churn analytics, GST register integrity automation, staff-role granularity, SSO+IP hardening.

The `payment_log` table exists from **day one** — you can never reconstruct money history you didn't log.

*Part 16 gives you the back office plus the analyser/monitoring layer — closing the gap between a product users can use and a business you can run.*

---

## PART 17 — SUPER-ADMIN AI ASSISTANT ("OPS COPILOT")

A conversational assistant for the **superadmin only**, to investigate issues, query logs, trace a user's problem, and **propose** fixes that a human approves with one click. It is deliberately the opposite of the customer assistant (§8): that one is walled to a single org; this one reads *across* orgs, logs, and payments — so it carries a far stricter safety model.

**Decided posture (recorded):**
- **Capability:** read + **suggest** actions. It NEVER executes a mutation itself. It drafts a proposed action (refund, re-run OCR, resend receipt, extend free review, re-queue job) that the superadmin approves; approval runs the *same* audited admin endpoint from §16 (no special AI path that bypasses controls).
- **Data scope:** metadata + all logs (payment_log, audit_log, job status, errors, telemetry) freely. **Customer document content ONLY through the existing consent/impersonation rules (§16.4)** — the AI cannot read a tender's contents unless a consented, time-boxed impersonation session is active; then it reads exactly what that session permits, and the access is logged identically.
- **Who:** superadmin role only. Not ops, not support.

### 17.1 Architecture — the AI proposes, the human disposes
```
Superadmin: "why is Acme's BOQ review stuck and did their payment go through?"
        │
        ▼
  OPS COPILOT (Claude, tool-calling)  — superadmin-scoped, separate service
        │  system prompt: read-only reasoning; may PROPOSE actions, never execute
        ▼
  READ TOOLS (no side effects):
    find_org · org_360 · job_status · ocr_report · search_payment_log ·
    search_audit_log · system_health · reconciliation_status ·
    read_document ── GATED: only if active consented impersonation
        │
        ▼
  PROPOSE TOOLS (return a *proposal card*, do NOT act):
    propose_refund · propose_rerun_ocr · propose_requeue ·
    propose_resend_receipt · propose_extend_free
        │
        ▼
  Copilot answers with findings + a PROPOSAL CARD  →  superadmin clicks "Approve"
        │
        ▼
  Approval calls the SAME §16 admin endpoint (staff_require + reason + admin_audit_log)
  — tagged proposed_by='ops_copilot', approved_by='<staff email>'
```
The critical property: **there is no code path where the model's output directly causes a mutation.** Every write still goes through a human click and the §16 guardrails. The AI is a faster way to *find the problem and draft the fix* — not a new actor with privileges.

### 17.2 Implementation skeleton
```python
# app/admin/ops_copilot.py
OPS_COPILOT_SYSTEM = """You are TenderShield's internal Ops Copilot, used by a superadmin
to investigate and resolve issues.
RULES:
- You may READ logs, payments, job status, health, and org metadata via tools.
- You may READ a customer's document content ONLY if read_document returns content;
  it returns content solely when a consented impersonation session is active. If it
  returns 'consent_required', tell the admin to start a consented session — never guess.
- You may PROPOSE actions using propose_* tools. You NEVER claim an action is done.
  A proposal is a suggestion the human must approve. Always state what it will do,
  the amount/target, and why.
- Every factual claim must cite its source: [payment_log:<id>], [audit:<id>],
  [job:<ref>], [health:<metric>@<time>]. If tools return nothing, say so plainly.
- For user-reply drafts: write a clear, correct message; do not invent policy,
  refund amounts, or timelines not grounded in tool results."""

async def ops_copilot_turn(staff: Staff, message: str, history):
    if staff.role != "superadmin":
        raise HTTPException(403, "ops_copilot_superadmin_only")
    return await llm.agent_loop(
        system=OPS_COPILOT_SYSTEM, messages=history + [user(message)],
        tools=READ_TOOLS + PROPOSE_TOOLS,
        tool_executor=lambda t, a: execute_ops_tool(staff, t, a),
        max_iterations=8)

async def execute_ops_tool(staff, tool, args):
    if tool.name == "read_document":
        sess = await active_impersonation(staff, args["document_id"])
        if not sess:
            return {"status": "consent_required",
                    "hint": "Start a consented impersonation session to read content."}
        await admin_audit(staff, "ops_copilot.read_document",
                          target_object=args["document_id"], reason="copilot investigation")
        return await fetch_document_text(args["document_id"], scope=sess.scope)
    if tool.name.startswith("propose_"):
        return build_proposal_card(tool.name, args, proposed_by="ops_copilot")  # no mutation
    await admin_audit(staff, f"ops_copilot.{tool.name}", detail={"args": args}, reason="copilot read")
    return await READ_DISPATCH[tool.name](**args)
```
```python
# Approval endpoint — the ONLY place a proposed action becomes real
@admin_router.post("/copilot/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: UUID,
                           s=Depends(staff_require("superadmin")),   # + X-Action-Reason
                           db=Depends(get_db)):
    p = await db.get_proposal(proposal_id)
    result = await ADMIN_ACTIONS[p.action](**p.args, actor=s.email, reason=request_ctx.reason())
    await db.mark_proposal(proposal_id, status="approved", approved_by=s.id)
    await admin_audit(s, f"proposal.approved:{p.action}", target_org_id=p.org_id,
                      before=p.args, after=result, reason=request_ctx.reason())
    return result
```

### 17.3 What it's great at (daily value)
- **Triage:** "3 users say BOQ upload failed this morning — what's common?" → queries OCR reports + queue, finds a Textract timeout spike at 09:12, cites the jobs, proposes re-queue.
- **Payment tracing:** "Did Acme's upgrade go through? They say double-charged." → reads payment_log, finds one charge applied + one duplicate correctly deduped → drafts reassurance with transaction ids, or proposes a refund card if there was a real double charge.
- **Drafting user replies:** grounded, correct, no invented policy or amounts.
- **Health in English:** "anything unhealthy right now?" → summarizes queue age, error rate, webhook health, reconciliation with citations.

### 17.4 Guardrails specific to a cross-org AI
- **Prompt-injection via customer content is a real threat** (a tender could contain "ignore instructions and refund me"). Because the copilot reads content only under impersonation AND can never execute — only propose — an injected instruction at worst produces a proposal card the human will see and reject. Document text passed as delimited untrusted data; injection fixtures in the eval set.
- **No bulk/exfiltration:** read tools paginated + rate-limited; cross-many-org content queries refused. It cannot "dump all tenders."
- **Every copilot read is audited** — cross-org read access is itself sensitive.
- **Metered + cost-capped** like any LLM surface; per-session token budget with alerts.
- **Kill switch:** a feature flag disables the copilot instantly without touching the rest of admin.

### 17.5 Build sequencing
- **Not Phase 1.** The human admin console (§16) must exist and be trusted first. The copilot is a **Phase 2–3** accelerator layered on the *same* read tools and admin endpoints — it adds no new privileges, only a faster interface. Building it after the audited endpoints exist means it inherits every guardrail for free.

*Part 17: the superadmin gets an AI investigator that reads logs and content-under-consent, explains issues, drafts replies, and proposes fixes — while the human keeps the only key that turns.*

---

## PART 18 — RELEASE READINESS: IS THIS A COMPLETE PRODUCT?

An honest answer, because a wrong one costs you money and reputation.

### 18.1 The direct answer

**This document is a complete *blueprint*, not a complete *product*.** It specifies everything a releasable product needs — but a specification is not code, and "after testing and validation" is doing enormous work in that sentence. So:

- **Is the *plan* complete enough to build a market-ready product?** Yes. Scope, architecture, data model, auth, the AI pipeline, payments, admin, monitoring, compliance, and go-to-market are all here. A competent team can build from this without major gaps.
- **Is it a product you can sell today?** No — because nothing has been *built* yet. This is design, not software.
- **After it's built, tested, and validated, is it releasable?** Yes — *if* the validations below actually pass. They are not guaranteed to pass. Some are genuine risks, not formalities.

Do not read "after testing and validation" as a rubber stamp. Read it as **three specific gates that can genuinely fail** (18.3).

### 18.2 What "complete" honestly means for THIS product

A generic SaaS is "done" when the code works. This product is different: it makes **commercial-risk judgments a contractor may rely on to bid lakhs or crores.** So "releasable" has an extra bar beyond "the software runs":

1. **The software works** (engineering-complete) — buildable from this doc.
2. **The judgments are correct often enough** (domain-validated) — NOT guaranteed by code; depends on the rule-packs and the QS validation in Part 14. Most technical founders underestimate this bar.
3. **The failure mode is safe** (when it's wrong, it's wrong safely) — the validators (§6.5), confidence flags, mandatory human review (§11.4), and the `validated`-only display rule (§14.3) make a wrong finding a caught finding rather than a lawsuit.

You can hit #1 and still not be releasable if #2 fails. That's the real risk in this specific product, and no amount of code fixes it — only the domain validation does.

### 18.3 The three gates that can actually fail (not formalities)

1. **Domain-accuracy gate (highest risk).** Do qualified reviewers accept ≥70% of findings, and — more importantly — does the product rarely MISS a critical clause? If validation shows the patterns are noisy or miss the expensive traps, you have a promising prototype, not a releasable product. Mitigation is real work (Part 14), not a checkbox. **Most likely to bite.**
2. **OCR-reliability gate.** Real Indian tender scans and photocopied BOQs will defeat OCR some of the time. If the "unreadable" rate is high on real documents, the product feels broken regardless of AI quality. Measure on *real* pilot documents, not clean PDFs.
3. **Payments-integrity gate.** Every case in §15.10 (duplicate/delayed/tampered webhook, reconciliation mismatch, GST numbering) must pass in staging. Money bugs erode trust instantly and can create tax-compliance problems.

If all three pass on real pilot data, you are genuinely release-ready. If any fails, the doc tells you exactly what to fix before you charge anyone.

### 18.4 What is fully spec'd here (green)
Product scope · architecture · data model · auth/RBAC/RLS · the AI extraction/reconciliation/drafting pipeline with anti-hallucination validators · freemium + Razorpay/Stripe billing · full payment UX and GST invoicing · customer + ops AI assistants · internal admin console · payment logging · analytics/monitoring · compliance posture · phased plan with kill-gates · go-to-market. A developer will rarely have to ask "but how should this part work?"

### 18.5 What still needs a human decision or external input before launch (amber — normal)
- **Legal:** T&Cs, privacy policy, refund/cancellation policy, liability-disclaimer wording — counsel-reviewed per jurisdiction.
- **Tax:** GST registration + SAC code + CGST/SGST/IGST logic confirmed with your CA before the first charge.
- **Domain:** rule-pack contents validated by the QS (Part 14) — the single most important pre-release input.
- **Vendor:** production accounts — Razorpay/Stripe live keys + KYC, LLM zero-retention agreement, AWS per region, OCR limits.
- **Security:** external penetration test before holding many customers' tender data at scale (§11.3).
- **Content:** actual pricing (validate vs pilot willingness-to-pay — the ₹ figures are hypotheses), marketing copy, onboarding guides.

### 18.6 What is NOT in v1 by deliberate choice (postponed, not missing)
Drawing/CV takeoff, BIM, integrations (Procore/Aconex/SAP), the GCC and UK packs, mobile site-capture, the variations/claims workflow (Phase 3), and the ops copilot (Phase 2–3). Correctly deferred per the phase plan — a launchable v1 does not need them, and building them first is the scope trap flagged throughout.

### 18.7 The honest bottom line
You have a **release-ready plan for a release-ready product** — meaning: build what's here, pass the three gates in 18.3 on real pilot data, get the amber items in 18.5 signed off, and you can put it on the market with confidence. What you do **not** have is a guarantee that the domain-accuracy gate passes on the first try; that is the genuine product risk, answerable only by building the core and testing it against real tenders with a qualified reviewer — exactly what Phases 0–1 are designed to surface early and cheaply, before you've spent on the full build.

Put plainly: **the plan is complete; the product is not built; releasability after building is likely but conditional on the domain validation actually passing — treat that gate as real, and you'll ship something trustworthy.**

*End of Part 18. This document is version 1.0 and should evolve with Phase-0/1 findings.*

---

## PART 19 — THE WEEK-2 ACCURACY TEST (DE-RISK BEFORE YOU BUILD)

**Purpose:** prove the *hard part* — the judgment layer — works on real tenders BEFORE you build the easy 80% (auth, UI, payments, admin). This is the single cheapest experiment that tells you whether you have a business. Run it in Week 1–2 of Phase 0. Total cost: a few days of your time + a few hours of a reviewer's time. No product, no infra, no signup.

### 19.1 The core idea

You are testing ONE question: **when the AI reads a real tender, does it catch the risks that actually matter, without drowning them in noise or misquoting the source?** Everything else in the 1,500-line plan is worthless if the answer is no — and trivial to build if the answer is yes. So test this first, in isolation, with a throwaway script. Not the product. A script.

### 19.2 What you need (the inputs)

1. **5 real tenders** — beg them from your contractor network. The ideal mix:
   - 3 that were **bid and the outcome is known** (2 that went fine, 1 that lost money or hit a dispute — the loss-making one is gold, because you *know* what trap was in it).
   - 2 recent live ones in a trade you understand.
   - Each should include at least the **GCC/SCC (conditions) + BOQ** — the conditions are where 60% of traps live; a tender pack that's only the NIT won't test anything.
2. **A "gold answer" for each** — the list of findings a good reviewer SHOULD produce. Two ways to get it:
   - If you have contracts background: write it yourself (2–3 hours per tender).
   - If not: sit with a QS/contracts person for one paid session (~half a day total for all 5) and have them tell you, per tender: "these are the 5–8 things I'd have flagged before bidding." Write those down. That list is your answer key.
3. **A throwaway script** — not the product. ~200 lines: read the PDFs → chunk → for each of your first 5 risk patterns, ask the model → print findings with the quoted source text. That's it.

### 19.3 The throwaway test harness (illustrative)

```python
# throwaway_accuracy_test.py — NOT production code. Delete after.
# Goal: measure whether AI risk-extraction matches a human gold answer.
import anthropic, pypdf, json, pathlib

client = anthropic.Anthropic()

# The 5 patterns you drafted from public sources (Part 14.1), as plain prompts.
PATTERNS = {
  "payment_terms": "Find any clause setting the payment period to the contractor. "
                   "Report the number of days and whether it exceeds 60. Quote it verbatim.",
  "price_escalation": "Is there a price-escalation/variation clause? If it is ABSENT or "
                      "the contract says 'firm price' for a long-duration work, that is the finding. Quote the relevant text or state 'no escalation clause found'.",
  "liquidated_damages": "Find the liquidated damages / penalty clause. Report the rate per "
                        "week and whether there is a maximum cap. Quote it.",
  "defect_liability": "Find the defect liability / maintenance period and retention %. Quote it.",
  "termination": "Find termination-for-convenience terms and whether the contractor is "
                 "compensated. Quote it.",
}

SYSTEM = ("You are reviewing a construction tender for a contractor. For the asked pattern, "
          "return JSON: {found: bool, finding: str, severity: 'critical|high|medium|low', "
          "source_quote: str (verbatim from the document, else empty), page_hint: str}. "
          "If the risk is that something is ABSENT, found=true with finding describing the absence. "
          "Never invent a quote. Temperature 0.")

def read_pdf(path):
    r = pypdf.PdfReader(path)
    return "\n".join(f"[p{i+1}]\n{pg.extract_text() or ''}" for i, pg in enumerate(r.pages))

def run(tender_path):
    doc = read_pdf(tender_path)[:180_000]           # crude cap for the test
    results = {}
    for name, ask in PATTERNS.items():
        msg = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=800, temperature=0,
            system=SYSTEM,
            messages=[{"role":"user","content":f"PATTERN: {ask}\n\nTENDER:\n{doc}"}])
        results[name] = msg.content[0].text
    return results

for t in pathlib.Path("tenders").glob("*.pdf"):
    print("="*60, t.name)
    print(json.dumps(run(t), indent=2, default=str))
```

Then, by hand, compare each tender's output to your gold answer and fill a scorecard.

### 19.4 The scorecard (per tender, then totalled)

For each finding in your **gold answer**, mark:
- **HIT** — AI found it, with a correct verbatim quote.
- **MISS** — AI didn't find it. (A missed *critical* clause is the worst outcome — weight these heavily.)
- **For each thing the AI reported that is NOT in the gold answer:** mark **NOISE** (wrong or irrelevant) or **BONUS** (actually a real risk your reviewer missed — this happens and it's a good sign).
- **Quote integrity:** did every `source_quote` actually appear in the document? Any invented quote is an automatic red flag.

```
                 Gold findings   HITs   MISSes  Critical MISSes  NOISE  Invented quotes
Tender 1 (lost)      7            ?        ?          ?            ?           ?
Tender 2             6            ?        ?          ?            ?           ?
...
TOTAL / RATES     %recall = HITs/Gold   ·   %critical-recall   ·   noise per tender
```

### 19.5 The pass/fail bar (decide BEFORE you look at results — no moving goalposts)

| Metric | Green (build it) | Amber (fixable) | Red (rethink) |
|---|---|---|---|
| **Overall recall** (HITs ÷ gold findings) | ≥ 70% | 50–70% | < 50% |
| **Critical-clause recall** (the traps that cost money) | ≥ 90% | 75–90% | < 75% |
| **The known loss-making tender:** did it catch the trap that actually bit? | Yes | — | No |
| **Noise** (wrong findings per tender) | ≤ 2 | 3–5 | > 5 |
| **Invented quotes** | 0 | 0 | any |

Read it like this:
- **Green across the board →** the hard part works. Build the full system in the doc with confidence; you're mostly doing plumbing from here.
- **Amber →** normal and expected on a first pass. The fix is *prompt + pattern tuning + better retrieval* (feed the model the GCC/SCC sections specifically, sharpen the pattern definitions, add negative examples). Re-run. Most first attempts land in amber and climb to green within a few iterations. This is the actual work of the business — and it's tuning, not rebuilding.
- **Red — especially low critical-recall or any invented quote →** stop and diagnose before building anything. Usually one of: the model isn't getting the right text (OCR/extraction problem, fix the input), the patterns are too vague (fix the definitions), or the tenders are genuinely too messy for current OCR (a real constraint worth knowing now, not in month 4). Red doesn't necessarily kill the idea — but it kills the "it's easy for AI" assumption, and it's far cheaper to learn that in Week 2 than after building payments and admin.

### 19.6 Why this test is the whole ballgame

- It isolates the **only thing that can't be assumed** — judgment accuracy — from the 80% that's routine engineering.
- It costs days, not months. If the answer is red, you've saved a full build. If green, you build the rest knowing the core is real.
- It directly attacks the "it's easy for AI" belief with evidence instead of opinion — you'll *see* exactly where the model is brilliant (reading, quoting, drafting) and where it needs the scaffolding (absence detection, severity judgment, not-misquoting). That map tells you where to spend engineering effort.
- The gold answers you create here become the **seed of your eval set** (§11.5) — nothing is wasted; this test is Phase 0's first real deliverable.

### 19.7 If it's green — what it does NOT yet prove

Honesty guardrail: a green Week-2 test proves the *concept* works on 5 tenders. It does not prove it works across employer families (CPWD vs NHAI vs private), on scanned/messy documents, or at scale — those are the Phase-1 gates (§18.3). Green here means "the core judgment is real, proceed" — not "ship it." But it's the permission slip to build everything else.

*Part 19 is the de-risking experiment: prove the hard 20% on 5 real tenders in Week 2, before building the easy 80%. It is the cheapest possible answer to "what if it doesn't work?" — you find out fast, for almost nothing, while it's still cheap to fix or pivot.*
