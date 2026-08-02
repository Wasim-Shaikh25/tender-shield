# TenderShield Feature Coverage Audit

**Against:** `TenderShield_AI_Architecture_and_Market_Research.pdf` (28 pages, dated 20 July 2026)  
**Audited:** 2026-08-02 by Devin  
**Branch:** `devin/feature-coverage-audit`  
**Task:** TS-300  

## Summary

| Layer | Verdict |
|---|---|
| Backend module coverage for PDF §4 capability architecture | **~85% implemented / backend-only** |
| Frontend UI for the same capabilities | **~55% exposed** (opportunity detail + dashboards only) |
| End-to-end workflows (pre-bid → baseline → change → claim) | **Backend wired, UI partial** |
| Roadmap phases mapped in `tasks/backlog.md` | **Phase 17–21 marked done**, 4 Phase-1/1.5 tasks blocked on live provider credentials |
| Test suite | **580 passed, 4 skipped** (`backend/.venv/bin/pytest -q`) |
| Task tracker | **98% complete**, 4 blocked (SMS/Email/Stripe/Razorpay live keys) |

Overall: **the five stages described in the research doc are represented in the backend**, but several are API-only and need a frontend surface before end users can operate them.

## Evidence collected

- Backend test run: `580 passed, 4 skipped` on `devin/feature-coverage-audit` (same as `main` after PR #108).
- Task tracker: `python3 scripts/task_tracker.py --validate` reports Phase 17, 18, 19, 20, 21 all 100% done; 4 earlier tasks blocked only on live credentials.
- Module inventory: 32 backend modules under `backend/app/modules/` with specs in `specs/modules/`.
- Router inventory: see the route tables in the per-section evidence below.

## A. Tender Intake & Document Intelligence

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Bulk upload for PDF, XLSX, CSV, TXT, MD | **Implemented** | `backend/app/modules/ingestion/router.py` `/opportunities/{id}/upload`, `ingestion/extract.py` `extract_upload()` |
| Bulk upload for DOCX, images, ZIP, model schedules | **Missing / not supported** | `extract_upload()` only handles `.pdf`, `.xlsx/.xlsm`, `.csv`, `.txt`, `.md` |
| Resumable/large-file upload (TUS) | **Implemented** | `backend/app/modules/ingestion/tus.py` included in router |
| Document classification (rules-first) | **Implemented** | `backend/app/modules/ingestion/classify.py` `classify_text()` + `missing_documents()` |
| Automatic addendum comparison / duplicate detection | **Partial** | `RegisterDocumentBody` has `supersedes` (UUID FK in `Document`) but no automatic diff/dup detection |
| OCR for scanned PDFs | **Implemented** | `backend/app/modules/ingestion/ocr.py` `RapidOcrProvider` + `RapidTableProvider` |
| OCR for standalone images | **Missing** | Only image-PDF rasterization is handled |
| Language detection / multilingual extraction | **Missing** | Not found in ingestion pipeline |
| Table reconstruction from scans | **Implemented** | `RapidTableProvider` in `ocr.py` |
| Clause segmentation | **Implemented** | `backend/app/modules/ingestion/segment.py` `segment_clauses()` with `[pN]` markers and cross-ref extraction |
| Defined-term linking | **Partial** | Cross-references captured, no explicit defined-term glossary entity |
| Deadline calendar | **Implemented** | `backend/app/modules/ingestion/deadlines.py`, endpoints in `ingestion/router.py`, tested by `tests/test_deadlines.py` |

## B. Tender Risk Firewall

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Risk taxonomy (payment, retention, LD, etc.) | **Implemented** | Rule-packs under `rulepacks/in-works/`; `backend/app/modules/rulepacks/` loader |
| Pattern engine / absence detection | **Implemented** | `backend/app/modules/risk/engine.py`, `classifier.py`, `severity.py` |
| Clause deviation comparison against playbook/standard | **Partial** | `crossref` module provides search/diff; dedicated deviation scoring not exposed in UI |
| Risk-to-cost mapping | **Implemented** | `backend/app/modules/pricing/loading.py` `compute_loadings()` |
| Bid/no-bid score | **Implemented** | `backend/app/modules/qualification/` and `comparison/` produce bid-readiness/recommendation scores |
| Clarification-question builder | **Implemented** | `backend/app/modules/drafting/generator.py` `_clarification()` and artifacts API |
| Risk register with owner, mitigation, pricing allowance, residual risk, approval | **Implemented** | `backend/app/modules/findings/` stores all findings + `review` workflow for accept/edit/reject + `pricing` loading |

## C. BOQ Assurance

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Normalize inconsistent BOQ formats | **Implemented** | `backend/app/modules/boq/service.py` + `ingestion/tables.py` `boq_table_to_csv()` |
| Duplicate rows, blank rates, arithmetic, unit, quantity-outlier checks | **Implemented** | `backend/app/modules/boq/engine.py` `run_checks()` using DuckDB, tested by `tests/test_boq.py` |
| Cross-check BOQ descriptions vs specifications | **Partial** | `boq/engine.py` `scope_gaps()` uses `SpecTextIndex`; drawing-schedule cross-check not implemented |
| Missing-scope suggestions from trade checklists | **Implemented** | `scope_gaps()` consumes rulepack trade checklists |
| Missing-scope suggestions from historical patterns | **Missing** | No historical-outcomes graph feeding back into BOQ scope suggestions |
| Assumption register & exclusions builder | **Implemented** | `backend/app/modules/drafting/generator.py` `_assumptions()` + `/drafting/artifacts` endpoint |
| Rate build-up templates & sensitivity scenarios | **Partial** | `pricing/loading.py` and `pricing/cashflow.py` exist; UI templates not built |
| Human audit trail for edited quantities/rates | **Implemented** | `findings` review states + `core/audit.py` event log |

## D. Drawing & Revision Intelligence

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Drawing register, title-block extraction, revision ID, superseded controls | **Missing** | No drawing-specific parser or register |
| Overlay comparison / region-level change detection | **Missing** | Not implemented |
| Symbol/count assistance | **Missing** | Not implemented |
| Drawing-to-BOQ link | **Missing** | Not implemented |
| Confidence heatmap / “cannot determine” states | **Missing** | Not implemented |
| IFC/model quantity import | **Missing** | Not implemented |

> PDF §9.3 explicitly postpones general-purpose BIM authoring, clash detection, and universal automated takeoff from arbitrary drawings. Section D is therefore **deferred**, not a release blocker.

## E. Baseline Lock & Handover

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Freeze awarded contract, accepted BOQ, drawings, clarifications, assumptions, exclusions | **Implemented** | `backend/app/modules/baseline/router.py` `/freeze`, `models.py`, `compare_award.py`; hash-sealed artifacts |
| Project commercial handover pack | **Implemented** | `backend/app/modules/baseline/handover_views.py`, `/handover` and `/handover/export` |
| Tender risks → project controls / watchlist | **Implemented** | `backend/app/modules/baseline/watchlist.py`, `/watchlist` endpoints |
| Notice rules, correspondence addresses, authorized reps | **Implemented** | `backend/app/modules/baseline/notice_register.py`, `/notice-register`, `standards/` for org overrides |
| Approval matrix | **Implemented** | `backend/app/modules/auth/approval.py` `approval_matrix` capability |
| Cost codes mapped to BOQ / variation categories | **Implemented** | `backend/app/modules/baseline/cost_codes.py`, `/cost-codes` endpoints, tested by `tests/test_baseline_phase17_cost_codes.py` |
| Baseline adoption telemetry | **Implemented** | `backend/app/modules/baseline/adoption.py`, `analytics/router.py` `/baseline-adoption` |

## F. Change & Variation Detection

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Compare new revisions/specs/instructions against baseline | **Implemented** | `backend/app/modules/change/baseline_diff.py`, `/opportunities/{id}/diff` |
| Capture change signals from RFIs, emails, meeting minutes, site instructions, daily reports | **Partial** | `change/signals.py`, `change/email_inbox.py` and integration adapters ingest RFI/email/meeting shapes; live email polling / site-report parsing not wired |
| Potential-variation inbox | **Implemented** | `backend/app/modules/change/inbox.py`, `/opportunities/{id}/inbox` |
| Link affected BOQ items, cost codes, schedule activities, subcontract packages | **Implemented** | `backend/app/modules/change/impacts.py`, `/events/{id}/impacts`, plus `change/models.py` |
| Site confirmation workflow (changed / not changed / clarification only / contractor / client / unknown) | **Implemented** | `change/router.py` `/events/{id}/confirmations`, `change/models.py` `ConfirmationStatus` |
| Notice deadline countdown & escalation rules | **Implemented** | `change/notice_deadline.py`, `change/notice_alerts.py`, `/events/{id}/notice-deadline`, tested by `tests/test_change_notice_deadline.py` / `test_change_notice_alerts.py` |

## G. Claims & Notice Workspace

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Contract-specific notice templates populated with verified facts | **Implemented** | `backend/app/modules/drafting/generator.py`, `drafting/validators.py` no-invented-quotes/numbers validators, `/drafting/artifacts` |
| Chronology builder from approved correspondence/revisions | **Implemented** | `backend/app/modules/claims/router.py` `/claims/{id}/chronology`, `timeline/` module |
| Evidence checklist (instruction, baseline, revised scope, labor, plant, material, schedule, photos, approvals) | **Implemented** | `backend/app/modules/evidence/completeness.py`, `/claims/{id}/checklist`, tested by `tests/test_evidence_completeness.py` |
| Quantum workspace (quantity × rate × daywork) with reviewer sign-off | **Implemented** | `backend/app/modules/claims/router.py` `/claims/{id}/quantum/line-items`, `claims/models.py` |
| Delay-event register & links to programme records | **Partial** | `/opportunities/{id}/delay-register` exists; schedule import in `integrations/adapters.py` `ScheduleAdapter` provides activity import, but no critical-path delay analysis |
| Draft interim particulars, variation proposal, EOT narrative, claim package | **Implemented** | `claims/router.py` `/claims/{id}/drafts/{kind}` + `drafting/generator.py` |
| Issue → response → negotiation → settlement tracking | **Implemented** | `claims/router.py` `/responses`, `/negotiations`, `/settlement` |

## H. Commercial Control Tower

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| At-risk revenue, unnotified change, submitted/certified/rejected value, ageing, cash exposure | **Implemented** | `backend/app/modules/controltower/service.py` `exposure_for_opportunity()`, `/exposure` |
| Project-level deadlines + evidence-health dashboard | **Implemented** | `controltower/router.py` `/dashboard`, `analytics/router.py` `/deadline-dashboard`, `/boq-defect-summary` |
| Risk-adjusted forecast at completion | **Implemented** | `controltower/router.py` `/forecast` |
| Client/consultant response-time analytics | **Implemented** | `controltower/router.py` `/response-times` |
| Portfolio clause trends, recurring omission patterns, loss reasons | **Partial** | `controltower/router.py` `/clause-trends`; full cross-project loss-reason analytics rely on recorded outcomes, which exist in `outcomes/` but are not surfaced in a dedicated UI |
| Executive summaries with source links and drill-down | **Implemented** | `controltower/router.py` `/executive-summary` |

## I. Collaboration, Governance & Integrations

| Feature from PDF | Status | Evidence / Notes |
|---|---|---|
| Role-based access by organization, project, document class | **Partial** | Workspace/project roles (`auth/rbac.py`, `auth/router.py`); document-class ACL not yet granular |
| Immutable event log, version history, evidence provenance | **Implemented** | `backend/app/core/audit.py`, `findings/store.py`, `baseline/models.py` hash-sealed snapshots |
| Human approvals before notices/claims issued | **Implemented** | `review/gate`, `auth/approval.py`, artifact `approve` endpoints |
| Integration adapters (SharePoint/OneDrive, Procore, Autodesk, Aconex, ERP, scheduling) | **Backend adapters implemented, live connectors not** | `backend/app/modules/integrations/adapters.py` has `SharepointOnedriveAdapter`, `ProcoreAdapter`, `AutodeskAdapter`, `AconexAdapter`, `ErpAdapter`, `ScheduleAdapter`; they normalize JSON/CSV/XML payloads but there are no live OAuth/API clients |
| Open API + export to DOCX/XLSX/PDF/custom templates | **Partial** | `public_api/` module, `export/render.py` supports DOCX/XLSX/PDF; customer-branded/custom templates not yet configurable |
| Data residency, encryption at rest, retention, tenant isolation | **Partial** | Tenant isolation via Postgres RLS (`core/db.py`, migrations `FORCE ROW LEVEL SECURITY`); encryption/retention controls are config placeholders rather than implemented features |

## End-to-end workflows

| Workflow | Status | Evidence |
|---|---|---|
| 5.1 Pre-bid (upload → classify → clauses/deadlines → BOQ → risk → review → export) | **Implemented** | `tests/test_ingestion.py`, `tests/test_risk.py`, `tests/test_boq.py`, `tests/test_review.py`, `tests/test_export.py` |
| 5.2 Award & baseline (import award → compare → freeze → handover → watchlist → notice rules) | **Implemented** | `tests/test_baseline_phase17*.py`, `backend/app/modules/baseline/` |
| 5.3 Change-to-claim (signal → event → confirm → notice deadline → draft → evidence → claim → outcome) | **Implemented** | `tests/test_change*.py`, `tests/test_claims.py`, `tests/test_evidence*.py` |

## Five product phases vs. repo phases

| PDF Phase | Repo Phase | Status | Notes |
|---|---|---|---|
| 0. Discovery (interviews, post-mortems) | Phase 0 + eval harness | **Done** | `evals/` scaffold, `scripts/eval*.py`, `tests/test_eval*.py` |
| 1. Tender Risk (risk, deadlines, BOQ, clarifications) | Phase 1 / Phase 1.5 | **Done** | Core modules `ingestion`, `risk`, `boq`, `drafting`, `review`, `export` |
| 2. Baseline & Handover | Phase 17 | **Done** | `baseline/` 100% complete per task tracker |
| 3. Variations (change, notice, evidence) | Phase 18 | **Done** | `change/` 100% complete |
| 4. Claims & Evidence Workspace | Phase 19 | **Done** | `claims/`, `evidence/`, `outcomes/` 100% complete |
| 5. Commercial Control Tower & Portfolio | Phase 20 | **Done** | `controltower/`, analytics metrics 100% complete |
| Integrations, Subcontract Control, Advisor Edition | Phase 21 | **Backend done, UI/integrations partial** | `integrations/`, `subcontract/`, `advisor/`, `public_api/` exist; live connectors and front-end surfaces remain |

## Features explicitly postponed in the PDF

These are **not missing by accident**; the research doc marks them out of scope for the focused launch:

- General-purpose BIM authoring / clash detection
- Universal automated takeoff from arbitrary drawings
- Open materials marketplace and logistics operation
- Unverified “live market rates”
- Autonomous external notice sending
- Final legal opinions, entitlement decisions, final QS certification
- Full scheduling/critical-path analysis engine

## Frontend coverage gaps

The backend implements the full five-stage chain, but the Next.js UI currently exposes only:

- Opportunities list + detail (`frontend/app/opportunities/`)
- Risk / BOQ / Artifacts / Handover / Audit tabs inside opportunity detail
- Analytics dashboard (`frontend/app/analytics/`)
- AI plan dashboard (`frontend/app/plan/`) — not linked in nav
- Assistant chat (`frontend/app/assistant/`)
- Billing, team, settings, support, help

**Missing front-end surfaces:**

- Change/variation inbox and event confirmation workflow
- Claims workspace (chronology, quantum, negotiations, settlement)
- Commercial Control Tower dashboards
- Subcontract management
- Integration source configuration UI
- Public API key management
- Admin/Advisor multi-client views

## Blocked / credential-dependent tasks

Only four `tasks/backlog.md` entries remain blocked, all requiring live third-party credentials:

- TS-035: SES/Resend/MSG91 email/SMS send adapters
- TS-036: MSG91 phone OTP + Google OIDC
- TS-037: Stripe/Razorpay live provider tests
- TS-079: Real email/SMS delivery for MFA/OTP

## Verdict

**The five product stages from the research PDF are present in the backend code and tested.** Phase 17–21 (Baseline, Variations, Claims, Control Tower, Integrations/Subcontract/Advisor) are all represented by modules with passing tests and `tasks/backlog.md` status `done`. The main remaining work is:

1. **Frontend surfaces** for change, claims, control tower, subcontract, integrations, and public API management.
2. **Live provider connections** for email/SMS/OTP, payments, and external CDE integrations.
3. **Drawing intelligence** remains deliberately out of scope per PDF §9.3.
