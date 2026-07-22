# Product Overview — Spec

**Status:** agreed
**Requirement refs:** Doc §0, §1, §10, §12
**Task refs:** TS-003

## Purpose

TenderShield's launch wedge is **Tender Risk + BOQ Assurance**: ingest the tender
pack → build the commercial baseline → surface risk clauses, deadline traps, BOQ
defects and scope gaps with exact citations → generate bid-decision artifacts
(risk register, clarification letter, assumptions & exclusions register, deadline
calendar, Bid Review Pack) — before bid submission.

## Scope fences (binding, Doc §0.2, §12.6)

v1 does **not** include: drawing/CV takeoff, BIM, bid marketplace, live pricing,
autonomous notice sending, CPM scheduling, legal opinions, enterprise integrations,
mobile capture, GCC/UK packs. Only Phase-1 scope exists until three firms pay.

## Personas (Doc §0.3)

P1 mid-market GC commercial head (India, primary) · P2 specialty/small contractor
owner · P3 QS/contracts consultancy · P4 EPC commercial team (Phase 3+).

## Business model (Doc §0.4)

One-time free full review per org (watermarked) → paid: paygo ₹7,500/tender,
Pro ₹24,999/mo (10 reviews), Scale ₹74,999/mo (40 reviews). Razorpay (IN) +
Stripe (GCC/UK) behind one interface.

## Non-functional requirements (Doc §1.3)

- Upload → deadline wall + doc checklist: **< 3 min p95** (stream results).
- Full risk register + BOQ report: **< 25 min p95** (800-page pack, 5k-row BOQ).
- Resumable chunked uploads; ZIP ingestion; processing continues offline.
- Data residency ap-south-1 (IN); no training on customer data; 99.5% availability.

## Product invariants (Doc §6, §11.4, §12.1)

1. Numbers never come from the LLM (BOQ math, date math, severity = code).
2. Every extracted fact has `source_page` + verbatim quote, verified before display.
3. Artifact validators: no invented quotes / uncited clauses / invented numbers.
4. Org isolation (RLS) everywhere; export blocked until human review completes.
5. Findings UI labels tri-state: extracted fact / deterministic check / AI suggestion.

## Phase gates (Doc §10)

- **Phase 0 exit:** 5 patterns end-to-end on 3 real tenders with plausible cited findings.
- **Phase 1 exit:** deadline F1 ≥ 0.95; QS acceptance ≥ 70%; validated-only patterns
  shown; 10 real tenders end-to-end; 3 paid conversions.
- **Kill gates:** <40% second-tender conversion; finding acceptance <50% after two
  eval cycles; register/workbench non-adoption.
