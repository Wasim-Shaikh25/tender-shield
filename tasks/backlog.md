# TenderShield — Task Backlog

Derived from `docs/TenderShield_Full_Build_Doc.md`. Rules: `CLAUDE.md` §1,
`.cursor/rules/20-specs-tasks.mdc`. IDs are sequential and never reused.
Statuses: `todo | in-progress | blocked | done`.

Ordering follows the doc's value order (§13.5): rule-packs/risk patterns → BOQ
engine → clarification letter → billing. Phase-2+ work is intentionally absent
until Phase-1 exit gates pass (§10).

## Bootstrap (repo & engineering foundation)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-001 | Repo bootstrap: AI workflow rules (Claude+Cursor), requirement doc, repo map | user request | — | done |
| TS-002 | Task backlog generated from requirements | user request | — | done |
| TS-003 | Spec suite in `specs/` — product overview + per-module specs | user request; Doc §0–§9 | `specs/` | done |
| TS-004 | Backend core: pluggable module framework (loader, service registry, event bus, config) + tests | Doc §3.1 "modular monolith"; user: "pluggable, no hard dependency" | `specs/modules/core.md` | done |
| TS-005 | CI: ruff + pytest on push (GitHub Actions) | Doc §11.1 | — | done |

## Phase 0 — Bootstrap corpus & de-risk (Doc §10 Phase 0, §14, §19)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-006 | Week-2 accuracy test harness (throwaway script + scorecard template) | Doc §19 | `specs/phase0-accuracy-test.md` | done |
| TS-007 | Rule-pack scaffold: `rulepacks/in-works/` structure, pack.yaml + YAML schemas, loader in core | Doc §2 | `specs/modules/rulepacks.md` | done |
| TS-008 | First 5 risk patterns from public sources (payment, escalation, LD, defect liability, termination), `confidence: unvalidated` | Doc §14.1, §19.3 | `specs/modules/rulepacks.md` | done |
| TS-009 | 3 trade checklists (civil_structure, electrical, hvac) | Doc §2, §6.4 | `specs/modules/rulepacks.md` | done |
| TS-010 | Eval/golden-set folder scaffold (`evals/in-works/…`) | Doc §11.5 | — | done |

## Phase 1 — MVP (Doc §10 Phase 1; scope §1.2 column "P1 MVP")

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-011 | `auth` module: email+password (argon2id), RS256 JWT (15 min), rotating refresh + reuse detection | Doc §5 | `specs/modules/auth.md` | done |
| TS-012 | Orgs, org_members, RBAC guard, RLS binding (`SET LOCAL app.org_id`) | Doc §5, §3.2 | `specs/modules/auth.md` | done |
| TS-013 | DB foundation: Base/mixins, RLS helpers, session factory (registry capability), Alembic scaffold w/ pluggable model discovery | Doc §3.2 | `specs/data-model.md` | done |
| TS-013a | Per-module SQLAlchemy models + migrations (0001-0008: auth, ingestion, findings, audit_log, artifacts, billing) — risk + BOQ persist findings, review/drafting/export/billing wired | Doc §3.2 | `specs/data-model.md` | done |
| TS-014 | `ingestion` module: upload → rules-first classification + missing-doc checklist | Doc §6.1, §3.3 | `specs/modules/ingestion.md` | done |
| TS-015 | Deadline extraction (deterministic date parse + quote citation) + deadline wall API + confirm chips | Doc §6.2 | `specs/modules/ingestion.md` | done |
| TS-016 | Clause segmentation → `clauses` rows with refs + defined terms | Doc §3.3 | `specs/modules/ingestion.md` | done |
| TS-017 | `risk` module: pattern engine (retrieve → classify → verify), deterministic severity, absence detection | Doc §6.3 | `specs/modules/risk.md` | done |
| TS-018 | `boq` module: normalization (unit canon map) + deterministic checks (DuckDB) — zero LLM | Doc §6.4 | `specs/modules/boq.md` | done |
| TS-019 | Scope-gap engine: trade checklist × spec/BOQ cross-reference | Doc §6.4 | `specs/modules/boq.md` | done |
| TS-020 | `drafting` module: clarification letter + assumptions register + 3 validators (quotes/citations/numbers) | Doc §6.5 | `specs/modules/drafting.md` | done |
| TS-021 | Review workbench API + append-only audit log + export gating | Doc §1.1(7), §11.4 | `specs/modules/review.md` | done |
| TS-022 | `billing` module: free-tier metering (race-safe), paywall errors, Razorpay orders + webhooks, payment_log | Doc §7, §15, §16.5 | `specs/modules/billing.md` | done |
| TS-023 | Export renderer: Bid Review Pack (DOCX/XLSX; PDF pending) with review-approval stamp + gate | Doc §1.1(8), §11.4 | `specs/modules/drafting.md` | done |
| TS-024 | `assistant` module: grounded Q&A over org corpus, citations mandatory | Doc §8 | `specs/modules/assistant.md` | done |
| TS-025 | Frontend skeleton: Next.js 15 app router, opportunity board + deadline wall | Doc §9 | `specs/frontend.md` | done |

## Phase 1 — Production hardening (infra + money/file path)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-026 | Real file upload (multipart) + text extraction (PDF/XLSX/CSV) → feeds classify/segment/deadlines | Doc §3.3, §6.1 | `specs/modules/ingestion.md` | done |
| TS-027 | Deadline-digest notifications: pluggable sender abstraction + dev console sender + digest logic | Doc §11.6, §11.7 | — | done |
| TS-028 | TOTP MFA (pyotp): enroll (secret+otpauth URI) + verify | Doc §5 | `specs/modules/auth.md` | done |
| TS-029 | GST invoice computation (CGST/SGST vs IGST, sequential numbering) | Doc §15.8 | `specs/modules/billing.md` | done |
| TS-030 | PDF export (reportlab) — completes the DOCX/PDF/XLSX trio, gated + stamped | Doc §1.1(8) | `specs/modules/drafting.md` | done |
| TS-031 | Deploy scaffolding: Postgres docker-compose + backend/frontend Dockerfiles + `.env.example` | Doc §4, §11.1 | — | done |
| TS-032 | Frontend CI (npm build) job in GitHub Actions | Doc §11.1 | — | done |
| TS-033 | tus resumable upload; (Textract NOT required — open-source scanned-table path shipped in TS-039) | Doc §4, §6.1 | `specs/modules/ingestion.md` | todo |
| TS-039 | Scanned-table BOQ via rapid-table (offline ONNX, NO cloud) + HTML→CSV; wired as BOQ-upload fallback | Doc §6.1, §12.4 | `specs/modules/ingestion.md` | done (model download on first use; not sandbox-verified) |
| TS-038 | Local OCR (RapidOCR, offline) + PDF table extraction (pdfplumber) — no cloud; OCR provider interface + honest needs_ocr degradation | Doc §6.1, §12.4 | `specs/modules/ingestion.md` | done |
| TS-034 | Celery + Redis: async page-streamed processing (SSE) | Doc §3.1, §3.3 | — | todo (needs Redis) |
| TS-035 | SES/Resend + MSG91 send adapters behind the notifications interface | Doc §4, §11.6 | — | todo (needs creds) |
| TS-036 | Phone OTP (MSG91) + Google OIDC login | Doc §5 | `specs/modules/auth.md` | todo (needs creds) |
| TS-037 | Stripe (GCC/UK) provider + live Razorpay keys behind the billing interface | Doc §7, §15.6 | `specs/modules/billing.md` | todo (needs creds) |

## Phase 1 — UX & docs

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-040 | In-app Help page: how-to-use walkthrough + honest scope / QS-lifecycle coverage + disclaimer | Doc §0.1–0.2, §11.4 | `specs/frontend.md` | done |

## Phase 2 — Baseline lock (stickiness beyond the bid)

Trigger for building now: product-owner directive (2026-07-24) to build baseline
lock end-to-end. Doc §0.1 (P2 stage), §10 Phase 2/3, §1.2 feature matrix.
NB: the doc gates P2 behind the Phase-1 accuracy gate (§10); this is built as a
config-flagged, fully decoupled module so it ships without disturbing Phase-1.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-041 | `baseline` module: hash-sealed baseline freeze (immutable snapshot of accepted findings + confirmed deadlines + opportunity meta), integrity verify, deterministic notice-rule register (findings + clauses), award-vs-tender delta, commercial handover pack | Doc §0.1 (P2), §10, §1.2 | `specs/modules/baseline.md` | done |
| TS-042 | Frontend: opportunity "Handover" tab — freeze baseline, notice register, award-vs-tender delta, handover pack | Doc §9, §0.1 | `specs/frontend.md` | done |
| TS-046 | Layered contract-standards rulepack (universal base + regional overlay, merged at load) + standards-aware notice register with expected-regime gap detection. The flexibility spine: new market/clause type = a YAML file, no code change. | Doc §0.1, §2 (rule-packs as data), §10 | `specs/modules/rulepacks.md`, `specs/modules/baseline.md` | done |
| TS-047 | `standards` module: org-defined custom notice standards (their own regimes) that either **prevail** over or run **side-by-side** with universal+regional; researched real figures (FIDIC 28/84d, NEC 56d, MSMED 45d) grounding the universal/India packs. Frontend editor + register origin badges. | Doc §10 (custom playbooks), §0.1, §2 | `specs/modules/standards.md` | done |
| TS-043 | Notice-deadline countdowns + alerts driven by the notice-rule register (wire register → deadline/notification path) | Doc §0.1 (P3), §10 | `specs/modules/baseline.md` | todo |
| TS-044 | Award-document ingestion: parse negotiated contract / award letter so the award baseline seals from real award text | Doc §0.1 (P2/P3) | `specs/modules/baseline.md` | todo |
| TS-045 | Handover-pack file export (DOCX/PDF) reusing the export renderer | Doc §1.1(8), §0.1 | `specs/modules/baseline.md` | todo |

## Phase 1.5 — Bid-Decision Extensions

Extends the pre-bid workflow from "what are the risks?" to "should we bid?" while
staying inside the tender-review domain. Full requirements and tracker:
`docs/TenderShield_Phase15_Extensions.md` and `tasks/phase15_tracker.md`.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-054 | Risk Explainability: structured `explanation` object on every risk finding (pattern, evidence, industry reason, suggested reviewer) | Phase 1.5 doc §5 | `specs/modules/risk.md` (update) | done |
| TS-055 | Structured Review Outcomes: add `needs_clarification`/`false_positive` states and rejection reasons to the review workbench | Phase 1.5 doc §5 | `specs/modules/review.md` (update) | done |
| TS-049 | Qualification Compliance Matrix: extract eligibility criteria (turnover, experience, EMD, certifications, etc.) and flag gaps as findings | Phase 1.5 doc §5 | `specs/modules/qualification.md` | done |
| TS-056 | Organization Standards Enforcement: compare findings/org terms against org-published thresholds and create `standard_violation` findings | Phase 1.5 doc §5 | `specs/modules/standards.md` (update) | done |
| TS-052 | Tender Timeline: expand deadline extraction into a milestone calendar (pre-bid, clarification, submission, technical/financial opening, EMD/BG validity, contract signing) | Phase 1.5 doc §5 | `specs/modules/timeline.md` | done |
| TS-048 | Bid / No-Bid Recommendation: deterministic Bid Readiness Score + conditional recommendation artifact consuming accepted findings, qualification, timeline, and org standards | Phase 1.5 doc §5 | `specs/modules/drafting.md` (update) | done |
| TS-053 | Clause Cross-Reference: cross-document citation search for a clause/topic across NIT/GCC/SCC/addenda/BOQ notes | Phase 1.5 doc §5 | `specs/modules/crossref.md` | done |
| TS-051 | Clause Change Detection: diff added/removed/changed clauses between document versions (addendum/corrigendum) | Phase 1.5 doc §5 | `specs/modules/crossref.md` | done |
| TS-050 | Tender Comparison: portfolio dashboard ranking opportunities by risk, BOQ quality, deadline, and bid readiness | Phase 1.5 doc §5 | `specs/modules/comparison.md` | done |
| TS-057 | Internal Accuracy Dashboard: admin-only precision/recall/FP/FN metrics by pattern and review-outcome telemetry | Phase 1.5 doc §5 | `specs/modules/analytics.md` | done |

## Phase 1.5 follow-up — Spec audit fixes (post-audit, 2026-07-26)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-058 | Spec: `findings` module (shared findings store, `Finding` contract, review columns) | spec audit | `specs/modules/findings.md` (new) | done |
| TS-059 | Spec: `export` module (Bid Review Pack DOCX/XLSX/PDF renderer, review gate, watermark) | spec audit; Doc §1.1(8), §6.5 | `specs/modules/export.md` (new) | done |
| TS-060 | Spec: `health` module (health/capabilities endpoint, module load report) | spec audit; Doc §11.1 | `specs/modules/health.md` (new) | done |
| TS-061 | Spec: `notifications` module (digest sender abstraction, dev console adapter) | spec audit; Doc §11.6, §11.7 | `specs/modules/notifications.md` (new) | done |
| TS-062 | Publish `analytics.service_factory` and `comparison.service_factory` from their `module.py` files | spec audit | `specs/modules/analytics.md`, `specs/modules/comparison.md` (update) | done |
| TS-063 | Fix route wording in `specs/modules/timeline.md` and `specs/modules/crossref.md` to match implementation | spec audit | `specs/modules/timeline.md`, `specs/modules/crossref.md` (update) | done |
| TS-064 | Align `ingestion` public interface with code: publish `ingestion.service_factory` shape, add `doc_chunks` and `doc_text` | spec audit; Doc §3.3, §6.1 | `specs/modules/ingestion.md` (update) | done |
| TS-065 | Align `risk` public interface with code: publish `risk.service_factory` / document consumed capabilities | spec audit; Doc §6.3 | `specs/modules/risk.md` (update) | done |
| TS-066 | Align `drafting` public interface with code: `drafting.service_factory` vs separate `export` module | spec audit; Doc §6.5 | `specs/modules/drafting.md` (update) | done |
| TS-067 | Add tests for `export`, `health`, and `notifications` modules | spec audit | — | done |
| TS-068 | Implement `ingestion.doc_chunks` table and `ingestion.doc_text` capability | spec audit; Doc §3.3 | `specs/modules/ingestion.md` (update) | done |
| TS-069 | Implement assistant SSE `/chat` and conversation/session persistence | spec audit; Doc §8 | `specs/modules/assistant.md` (update) | done |
| TS-070 | Add billing invoice list and `billing.record_usage` capability | spec audit; Doc §7, §15 | `specs/modules/billing.md` (update) | done |
| TS-071 | Sign in with Apple (OIDC /auth/apple/callback, link verified Apple ID to user) | product; Doc §5 | `specs/modules/auth.md` (update) | todo |

## Notes

- A task moves to `in-progress` when work starts and `done` in the commit that
  completes it, with the task ID in the commit body.
- New requirements → new `TS-###` rows here first, then a spec, then code.
- Hardening items marked `(needs …)` are logic-ready but require external
  accounts/services to complete; the interfaces they plug into are already built.
