# Remaining Gaps & Roadmap Tracker

**Sourced from:** `FEATURE_COVERAGE.md` audit against `TenderShield_AI_Architecture_and_Market_Research.pdf`
**Created:** 2026-08-02
**Backlog phase:** Phase 22 — Gap closure roadmap (`tasks/backlog.md`)

## How to use this document

This tracker lists every capability currently marked **Partial** or **Missing** in the feature-coverage audit. Each entry has a task ID, requirement reference, acceptance criteria, priority, and status. Items marked **P3** align with PDF §9.3 (deliberately postponed) and should not block an internal pilot.

## Legend

- **P0** - fix immediately (blocks core workflow or is a tiny UI gap).
- **P1** - needed for a controlled pilot / paid tender-review flow.
- **P2** - needed for general availability / enterprise sales.
- **P3** - future / research-heavy, per the PDF extended/deferred list.

## Task table

| ID | Theme | Title | Priority | Status | Requirement | Spec / Target File | Acceptance Criteria | Notes |
|---|---|---|---|---|---|---|---|---|
| TS-301 | Frontend UI | Change / variation inbox and confirmation workflow UI | P1 | todo | Research Doc §4.F, §5.3; FEATURE_COVERAGE.md §F | frontend/app/opportunities/[id]/changes/ | - New tab/page /opportunities/{id}/changes lists change events. - User can confirm event, link impacts, trigger notice draft. - Playwright test covers signal -> confirm -> view notice deadline. | Backend endpoints already exist; only UI missing. |
| TS-302 | Frontend UI | Claims workspace UI | P1 | todo | Research Doc §4.G, §5.3; FEATURE_COVERAGE.md §G | frontend/app/opportunities/[id]/claims/ | - Tab/page /opportunities/{id}/claims with claim list, chronology, quantum, evidence checklist, responses/negotiations/settlement. - Calls all /api/claims endpoints. - E2E test: event -> draft claim -> settlement. | All /api/claims routes implemented. |
| TS-303 | Frontend UI | Commercial Control Tower dashboards UI | P1 | todo | Research Doc §4.H, §12.2; FEATURE_COVERAGE.md §H | frontend/app/controltower/ or /analytics/controltower | - Pages for exposure, dashboard, portfolio, forecast, response-times, clause-trends, executive-summary. - Charts/cards consume all GET /api/controltower/* endpoints. - Tests assert data rendering. | Backend complete; no frontend routes exist. |
| TS-304 | Frontend UI | Subcontract management UI | P2 | todo | Research Doc §13 Subcontract control; FEATURE_COVERAGE.md §I | frontend/app/opportunities/[id]/subcontracts/ | - Create/list subcontracts, view flow-down check, scope gaps, notice calendar, payment exposure. - Uses /api/subcontract/* endpoints. - E2E for subcontract creation + payment exposure. | Backend subcontract/ implemented. |
| TS-305 | Frontend UI | Integration source configuration UI | P2 | todo | Research Doc §4.I; FEATURE_COVERAGE.md §I | frontend/app/settings/integrations/ | - UI to add adapter source (SharePoint/OneDrive, Procore, Autodesk, Aconex, ERP, Schedule). - Test connection/preview import and map to opportunity. - Calls /api/integrations/sources and /import. | Backend adapters parse payloads; live connectors handled separately (TS-333). |
| TS-306 | Frontend UI | Public API key management UI | P2 | todo | Research Doc §4.I; FEATURE_COVERAGE.md §I | frontend/app/settings/api-keys/ | - Generate, list, revoke public API keys; set scopes; view signature callback logs. - Calls /api/public_api/keys and /signatures status endpoints. - Tests for key lifecycle. | Backend public_api/ implemented after PR #108. |
| TS-307 | Frontend UI | Admin / Advisor multi-client workspace UI | P2 | todo | Research Doc §3.3 Advisor Edition, §8.3; FEATURE_COVERAGE.md §I | frontend/app/advisor/ and admin workspace switcher | - Advisor role can switch between managed client workspaces. - Per-client usage and review queue. - Admin page supports workspace impersonation/separation. | Backend advisor/ module exists but needs UI. |
| TS-308 | Frontend UI | Plan dashboard navigation link | P0 | todo | Research Doc §4 analytics; plan-dashboard spec | frontend/components/nav/ | - Add a visible nav item linking to /plan. - Existing /plan page loads and functions. - One-line E2E check. | Page exists but is not linked. |
| TS-309 | Frontend UI | Pricing / rate benchmark / cashflow results UI | P2 | todo | Research Doc §4.C rate build-up; pricing-intel spec | frontend/app/opportunities/[id]/pricing/ | - Tab showing loadings, rate benchmark variance, cashflow curve. - Calls /api/pricing/opportunities/{id}/loading, /rate-benchmark, /cashflow. - Tests for render with sample payloads. | Backend pricing/ implemented. |
| TS-310 | Ingestion | DOCX upload and text extraction | P1 | todo | Research Doc §4.A bulk upload; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/extract.py | - extract_upload() accepts .docx and returns plain text. - Handles DOCX in multipart upload and async Celery path. - Unit test with sample DOCX. | Use python-docx or docx2txt. |
| TS-311 | Ingestion | Image (PNG/JPG/TIFF) upload and standalone OCR | P2 | todo | Research Doc §4.A OCR; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/ocr.py | - Upload .png/.jpg/.jpeg/.tiff and run RapidOcrProvider directly. - Store as document kind image, return OCR text and ocr_status. - Test with scanned image. | Currently OCR only runs inside PDF rasterization. |
| TS-312 | Ingestion | ZIP bulk package upload | P2 | todo | Research Doc §4.A bulk upload; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/router.py | - Accept .zip upload, validate contents, register each file under opportunity. - Recursively classify each file and enqueue processing. - Security: size limits, path traversal sanitization, tests. | Build on existing validate_and_store and process_document tasks. |
| TS-313 | Ingestion | Exported model schedule ingestion (CSV/IFC) | P3 | todo | Research Doc §4.A exported model schedules; FEATURE_COVERAGE.md §A | backend/app/modules/integrations/adapters.py ScheduleAdapter + new ingestion route | - Accept .ifc or model-schedule CSV; extract activity/quantity data. - Map to schedule activities and optionally BOQ items. - Tests for IFC parsing and CSV schedule. | IFC parsing is heavy; start with CSV and IFC basic geometry. |
| TS-314 | Ingestion | Automatic addendum comparison and duplicate detection | P2 | todo | Research Doc §4.A version detection, addendum comparison; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/service.py | - Detect supersedes relationships automatically from filename/headers. - Compare new revision text to previous, surface changed clauses/BOQ rows. - Duplicate SHA/file-name detection and warnings. - Unit tests. | Document.supersedes FK already exists. |
| TS-315 | Ingestion | Language detection and multilingual extraction assistance | P3 | todo | Research Doc §8.1 localization; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/doc_text.py | - Detect document language; preserve original text. - Optional translated summary for Hindi/regional languages, never replacing source. - Tests for EN/HIN documents. | India-first requirement; do not overwrite contractual text. |
| TS-316 | Ingestion | Defined-term glossary and linking | P2 | todo | Research Doc §4.A defined-term linking; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/segment.py + new glossary model | - Extract defined terms into a glossary table. - Link clause text to definitions; API returns terms for an opportunity. - Tests for glossary extraction and linking. | Cross-references already captured. |
| TS-317 | Risk & BOQ | Clause deviation scoring against playbook/standard | P2 | todo | Research Doc §4.B clause deviation comparison; FEATURE_COVERAGE.md §B | backend/app/modules/comparison/ or new risk/deviation.py | - Compare extracted clauses against org standard/playbook and produce deviation score per clause. - API endpoint and UI column in risk register. - Tests with sample playbook. | crossref provides search/diff but not scoring. |
| TS-318 | Risk & BOQ | BOQ cross-check against drawing schedules | P2 | todo | Research Doc §4.C cross-check BOQ vs drawings; FEATURE_COVERAGE.md §C | backend/app/modules/boq/engine.py | - Ingest drawing-schedule CSV and compare quantities/descriptions to BOQ. - Flag mismatches with source_page from drawing row. - Unit test with sample drawing schedule. | BOQ scope_gaps() uses spec text only today. |
| TS-319 | Risk & BOQ | Missing-scope suggestions from historical patterns | P3 | todo | Research Doc §4.C historical patterns; FEATURE_COVERAGE.md §C | backend/app/modules/boq/engine.py + outcomes/ | - Aggregate approved outcomes and reviewer edits per trade. - Suggest missing scope items for new opportunities based on historical patterns. - Configurable confidence threshold; tests. | Requires outcome dataset to be meaningful. |
| TS-320 | Risk & BOQ | Rate build-up templates and sensitivity UI | P2 | todo | Research Doc §4.C rate build-up/sensitivity; FEATURE_COVERAGE.md §C | frontend/app/opportunities/[id]/pricing/ + backend/pricing | - UI templates for rate build-up (base cost + loading + margin). - Sensitivity slider/scenario for escalation/contingency. - Persist templates per workspace; tests. | Backend pricing/loading.py and cashflow.py available. |
| TS-321 | Drawing Intelligence | Drawing register, title-block extraction, revision and superseded controls | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | new backend/app/modules/drawings/ | - Parse drawing PDFs, extract title block (project, sheet, revision, date). - Store Drawing entities with revision chain and superseded flag. - API + tests. | PDF §9.3 defers drawing intelligence; keep P3. |
| TS-322 | Drawing Intelligence | Drawing overlay and region-level change detection | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/compare.py | - Raster compare two drawing revisions, highlight changed regions. - Return change regions with confidence; never auto-claim entitlement. - Tests with sample drawing pairs. | Computer-vision heavy; P3. |
| TS-323 | Drawing Intelligence | Drawing symbol and count assistance | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/vision.py | - Detect common symbols and counts in supported drawing types. - Returns suggestions, not final quantities. - Tests. | P3. |
| TS-324 | Drawing Intelligence | Drawing-to-BOQ link | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/ + boq/ | - User can select a drawing region and link to a BOQ item; persisted with provenance. - API and UI support. - Tests. | P3. |
| TS-325 | Drawing Intelligence | Drawing confidence heatmap | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/heatmap.py | - Render heatmap overlay of model confidence for extracted regions/counts. - Include cannot determine states. - Tests. | P3. |
| TS-326 | Drawing Intelligence | IFC / model quantity import | P3 | todo | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/ifc.py | - Parse IFC for element quantities and classification. - Import as candidate BOQ lines or schedule activities. - Tests. | P3. |
| TS-327 | Change & Claims | Live change signal ingestion from RFIs, emails, meeting minutes, site instructions, daily reports | P2 | todo | Research Doc §4.F; FEATURE_COVERAGE.md §F | backend/app/modules/change/signals.py + notifications/email adapters | - Poll or webhook ingest emails/RFIs/site instructions into change_sources. - Classify signals into candidate events with confidence. - Integration tests with sample payloads; email polling behind feature flag. | Current adapters normalize JSON only. |
| TS-328 | Change & Claims | Delay-event critical-path and programme links | P3 | todo | Research Doc §4.G delay-event register; FEATURE_COVERAGE.md §G | backend/app/modules/change/delay_analysis.py | - Import P6/MS Project schedule, compute impacted activities for a delay event. - Show delay window and affected path; no auto entitlement. - Tests. | ScheduleAdapter parses activities; CPM logic not yet built. |
| TS-329 | Control Tower | Portfolio clause trends, recurring omission patterns and loss-reason analytics | P2 | done | Research Doc §4.H; FEATURE_COVERAGE.md §H | backend/app/modules/controltower/service.py + frontend | - Aggregate findings and outcomes across projects to show clause-level trends and top loss reasons. - Endpoint /api/controltower/clause-trends returns full analytics. - UI chart and tests. | outcomes/ records outcomes but cross-project analytics are shallow. |
| TS-330 | Governance | Document-class ACL | P2 | done | Research Doc §4.I role-based access by document class; FEATURE_COVERAGE.md §I | backend/app/modules/auth/acl.py + settings UI | - Extend RBAC to restrict read/write per document kind. - Apply to ingestion/export/change/claims endpoints. - Tests for denied access. | Workspace/project roles exist; document-class dimension missing. |
| TS-331 | Governance | Custom branded report templates | P2 | done | Research Doc §4.I export to customer templates; FEATURE_COVERAGE.md §I | backend/app/modules/export/models.py + settings UI | - Workspace can create/select templates with title/footer/watermark/colour/logo. - Export renderer uses default or selected template. - Tests. | Export supports static PDF/DOCX/XLSX, not configurable templates. |
| TS-332 | Governance | Data residency, encryption at rest and retention controls | P2 | todo | Research Doc §11.2 security baseline; FEATURE_COVERAGE.md §I | backend/app/core/config.py + storage | - Storage-level encryption at rest (SSE-S3 or customer KMS). - Per-workspace retention policy and legal-hold flag. - Audit and tests. | Tenant isolation (RLS) in place; encryption/retention are policy/config only. |
| TS-333 | Live Integrations | Live CDE/ERP connector sync (OAuth + polling/webhooks) | P2 | todo | Research Doc §4.I; FEATURE_COVERAGE.md §I | backend/app/modules/integrations/connectors/ | - Implement OAuth flows and webhook/polling for Procore, Autodesk, Aconex, SharePoint/OneDrive, ERP. - Map real API payloads to existing adapters. - Staging credentials and integration tests. | Existing adapters only normalize static payloads. Existing blocked tasks TS-035/036/037/079 cover email/SMS/payments; this covers CDE/ERP. |

## Priority themes and recommended order

### P0 (do first)
- **TS-308** Plan dashboard nav link - zero-cost discoverability fix.

### P1 (pilot readiness)
- Frontend surfaces for **change/variation (TS-301)**, **claims (TS-302)**, and **control tower (TS-303)** so the full five-stage workflow is operable from the browser.
- **TS-310 DOCX upload** because many tender packs include DOCX schedules.

### P2 (general availability / enterprise)
- Subcontract, integration, public API, admin/advisor, and pricing UIs.
- Document-class ACL, custom templates, encryption/retention, live CDE/ERP connectors.
- Clause deviation scoring, BOQ vs drawing schedules, portfolio analytics.

### P3 (research / deferred)
- All drawing-intelligence tasks (TS-321-TS-326).
- Model schedule IFC parsing, delay CPM, historical scope patterns, multilingual extraction.

## Dependency map

- UI tasks (TS-301-TS-309) depend only on existing backend APIs.
- **TS-327** live signal ingestion depends on notification/integrations credentials (TS-035/TS-079) and the integrations source UI (TS-305).
- **TS-319** historical scope suggestions depends on outcomes being recorded (TS-265/TS-269 already done).
- **TS-322-TS-326** drawing intelligence depend on a drawing parser not yet built.

## Tracking

Update this file when a gap moves to in-progress or done. Mirror status in `tasks/backlog.md` under the **Gap closure roadmap** phase.