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
| TS-033 | tus resumable upload; (Textract NOT required — open-source scanned-table path shipped in TS-039) | Doc §4, §6.1 | `specs/modules/ingestion.md` | done |
| TS-039 | Scanned-table BOQ via rapid-table (offline ONNX, NO cloud) + HTML→CSV; wired as BOQ-upload fallback — NOTE: ONNX model downloads on first use; not verified in a sandbox | Doc §6.1, §12.4 | `specs/modules/ingestion.md` | done |
| TS-038 | Local OCR (RapidOCR, offline) + PDF table extraction (pdfplumber) — no cloud; OCR provider interface + honest needs_ocr degradation | Doc §6.1, §12.4 | `specs/modules/ingestion.md` | done |
| TS-034 | Celery + Redis: async page-streamed processing (SSE) | Doc §3.1, §3.3 | — | done |
| TS-035 | SES/Resend + MSG91 send adapters behind the notifications interface — BLOCKED: adapters written, needs live provider credentials to verify | Doc §4, §11.6 | — | blocked |
| TS-036 | Phone OTP (MSG91) + Google OIDC login — BLOCKED: needs live provider credentials to verify | Doc §5 | `specs/modules/auth.md` | blocked |
| TS-037 | Stripe (GCC/UK) provider + live Razorpay keys behind the billing interface — BLOCKED: needs live provider credentials to verify | Doc §7, §15.6 | `specs/modules/billing.md` | blocked |

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
| TS-043 | Notice-deadline countdowns + alerts driven by the notice-rule register (wire register → deadline/notification path) | Doc §0.1 (P3), §10 | `specs/modules/baseline.md` | done |
| TS-044 | Award-document ingestion: parse negotiated contract / award letter so the award baseline seals from real award text | Doc §0.1 (P2/P3) | `specs/modules/baseline.md` | done |
| TS-045 | Handover-pack file export (DOCX/PDF) reusing the export renderer | Doc §1.1(8), §0.1 | `specs/modules/baseline.md` | done |

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
| TS-071 | Sign in with Apple (OIDC /auth/apple/callback, link verified Apple ID to user) | product; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-072 | Provide .env.local/.env.dev/.env.prod, run script, and deployment instructions | dev-experience; Doc §11.1 | `docs/deployment.md` (new), `scripts/run.sh` (new) | done |
| TS-073 | Create Devin AI assistant rules mirroring Cursor/Claude rules | dev-experience; Doc §11.1 | `.devin/rules/*.mdc` (new), `DEVIN.md` (new) | done |
| TS-074 | Spec for workspace/project tenant refactor + super admin | product; Doc §3.2, §5 | `specs/workspace-and-admin-refactor.md` (new) | done |
| TS-075 | Auth model: remove `org`/`org_members`, add `User` + `Workspace`/`WorkspaceMember` + `Project`/`ProjectMember` + `Invitation`, super-admin flag | product; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-076 | Rename `org_id` → `workspace_id` across all modules, RLS, and `core.db` | architecture; Doc §3.2 | `specs/data-model.md` (update) | done |
| TS-077 | Workspace/project CRUD, sharing/invites, super-admin endpoints, and 2FA method | product; Doc §5, §16 | `specs/modules/auth.md` (update) | done |
| TS-078 | Update tests and verify `ruff`/`pytest`/frontend build for tenant refactor | testing; Doc §11.1 | — | done |
| TS-079 | Real email/SMS delivery for `email`/`sms` MFA and OTP codes — BLOCKED: needs live provider credentials to verify | product; Doc §5 | `specs/modules/auth.md` (update), `specs/modules/notifications.md` (update) | blocked |
| TS-080 | Real web automation validation of signup -> workspace -> project -> invite flow | testing; Doc §11.1 | — | done |
| TS-081 | Fix `accept_invitation` naive/aware datetime comparison and add invitation flow test | bugfix; Doc §11.1 | `backend/tests/test_auth_module.py` (update) | done |
| TS-082 | Forgot-password and reset-password flow (token via email, dev mode returns token) | product; Doc §5 | `specs/modules/auth.md` (update) | done |

## Notes

- A task moves to `in-progress` when work starts and `done` in the commit that
  completes it, with the task ID in the commit body.| done || done || blocked || blocked || blocked || done || done || done || blocked |
- New requirements → new `TS-###` rows here first, then a spec, then code.
- Hardening items marked `(needs …)` are logic-ready but require external
  accounts/services to complete; the interfaces they plug into are already built.| done || done || blocked || blocked || blocked || done || done || done || blocked |

## Production readiness audit fixes (2026-07-29)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-083 | Security hardening: CORS restrictions, security headers, default-secret guard, rate limiting, public health split | audit F01/F02/F08/F10/F23 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/core.md`, `specs/modules/health.md` | done |
| TS-084 | Auth session/MFA: httpOnly refresh cookies, MFA enforcement at login, password policy + lockout | audit F04/F05/F22 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/auth.md` | done |
| TS-085 | Workspace/tenant: multi-workspace selection and switcher | audit F06 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/auth.md` | done |
| TS-086 | File upload/storage: MIME/magic/size validation, S3 adapter, virus-scan stub, BOQ size cap | audit F09/F11/F20 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/ingestion.md`, `specs/modules/boq.md` | done |
| TS-087 | Risk/export quality: `validated_only` filter for paying users, reviewer stamp in exports, `datetime.utcnow` cleanup | audit F03/F17/F25 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/risk.md`, `specs/modules/export.md` | done |
| TS-088 | Frontend cleanup and admin/billing UI: remove demo data, workspace switcher, billing/admin pages | audit F16 | `specs/900-production-readiness-audit-fixes.md`, `specs/frontend.md` | done |
| TS-089 | Deployment/DevEx: `.env.*` templates, `run.sh`/`docker-compose` fixes, CHANGELOG updates | audit F14 | `specs/900-production-readiness-audit-fixes.md` | done |
| TS-090 | CI/tooling: ESLint, `mypy`, `pip-audit`, `npm audit` in CI | audit F18 | `specs/900-production-readiness-audit-fixes.md` | done |
| TS-091 | Notification/payment adapter skeletons: SES/MSG91 senders, Razorpay/Stripe providers, scheduler stubs (credential-gated) | audit F07/F12/F15, TS-035/TS-037/TS-079 | `specs/900-production-readiness-audit-fixes.md`, `specs/modules/notifications.md`, `specs/modules/billing.md` | done |
| TS-092 | Admin console and analytics UI: superadmin dashboard, audit log viewer, accuracy dashboard | audit F21 | `specs/900-production-readiness-audit-fixes.md`, `specs/frontend.md` | done |
| TS-093 | Post-audit remaining fixes: env templates, upload/SSE auth, integration fallbacks, currency, file download, scheduler lock, email verification | `PRODUCTION_READINESS_AUDIT.md` F26–F42; Doc §3.2, §5, §7, §11.1, §11.6, §11.7, §14, §15 | `specs/901-post-audit-remaining-fixes.md` | done |

## End-to-end production readiness audit (2026-07-29, commit `d651d00`)

Audit only — no source changes. Findings and full remediation detail live in
`PRODUCTION_READINESS_AUDIT.md`. Each row below is a fix task derived from it.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-094 | End-to-end production readiness audit of trunk (`d651d00`); report + reproduced exploit probes | `CLAUDE.md` §4; Doc §3.2, §5, §7 | `PRODUCTION_READINESS_AUDIT.md` | done |
| TS-095 | **BLOCKER** Bind workspace-scoped routes to the caller's workspace; membership check in `add_workspace_member` | audit TS-A01; Doc §3.2, §5 | `specs/modules/auth.md` (update) | done |
| TS-096 | **BLOCKER** Google login must use `member.role`, not a hardcoded `"owner"`; unify token issuance across providers | audit TS-A02; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-097 | **BLOCKER** RLS: add `FORCE`, `WITH CHECK`, `current_setting(…, true)`; cover membership tables; add PostgreSQL to CI | audit TS-A03; Doc §3.2 | `specs/modules/core.md`, `specs/data-model.md` (update) | done |
| TS-098 | **BLOCKER** Server-owned per-currency price table; drop client `amount_minor`; validate paid amount at webhook activation | audit TS-B01; Doc §7, §15 | `specs/modules/billing.md` (update) | done |
| TS-099 | Membership checks on workspace/project member-list endpoints | audit TS-A04; Doc §3.2 | `specs/modules/auth.md` (update) | done |
| TS-100 | Google account linking on verified email; `IntegrityError` → 409 instead of 500 | audit TS-A05; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-101 | Cap upload size before buffering (`Content-Length` + streamed read); enforce at the proxy | audit TS-I01; Doc §11.1 | `specs/modules/ingestion.md` (update) | done |
| TS-102 | Async SSE generator: sleep, client-disconnect check, hard timeout | audit TS-I02; Doc §11.1 | `specs/modules/ingestion.md` (update) | done |
| TS-103 | Align `/auth/workspaces` response contract with the frontend client; generate the TS client from OpenAPI | audit TS-F01; Doc §9 | `specs/frontend.md` (update) | done |
| TS-104 | Rate limiting: wall-clock Redis scores, unique members, `X-Forwarded-For` with configured hop count | audit TS-O01; Doc §11.3 | `specs/modules/core.md` (update) | done |
| TS-105 | Webhook atomicity: claim the idempotency marker first, single transaction, unique constraint | audit TS-B02; Doc §15.5 | `specs/modules/billing.md` (update) | done |
| TS-106 | Team-management UI: invite, list, change role, remove member; member removal + invitation revocation API | audit §3.5 items 1, 3; Doc §5, §9 | `specs/frontend.md`, `specs/modules/auth.md` (update) | done |
| TS-107 | Account & security settings UI: change password, MFA enrolment, resend verification, session list | audit §3.5 item 2; Doc §5, §9 | `specs/frontend.md` (update) | done |
| TS-108 | Observability: metrics, error tracking, dependency-checking health probes, documented backup/rollback | audit TS-O02; Doc §16 | `specs/modules/health.md` (update) | done |
| TS-109 | Enforce plan seat limits in `add_workspace_member` and `accept_invitation` | audit TS-B03; Doc §7 | `specs/modules/billing.md` (update) | done |
| TS-110 | tus: `201` + `Location` header, shared chunk state, TTL sweeper, `upload_id` validation | audit TS-I03; Doc §11.1 | `specs/modules/ingestion.md` (update) | done |
| TS-111 | Deadline-alert deduplication table and per-user notification preferences | audit TS-N01; Doc §11.6 | `specs/modules/notifications.md` (update) | done |
| TS-112 | Prompt-injection hardening: delimit untrusted tender text; adversarial eval fixtures | audit TS-P01; Doc §11.3 | `specs/modules/assistant.md` (update) | done |
| TS-113 | Replace the virus-scan stub with a real scanner; quarantine on detection | audit TS-S01; Doc §11.2 | `specs/modules/core.md` (update) | done |
| TS-114 | Remove the cross-module FK `findings.opportunity_id → opportunities`; add a metadata architecture test | audit TS-X01; `CLAUDE.md` §2 | `specs/modules/findings.md`, `specs/data-model.md` (update) | done |
| TS-115 | Extend the production startup guard (Stripe secret, Redis, cookie policy, keypair parse) | audit TS-S02; Doc §11 | `specs/modules/core.md` (update) | done |
| TS-116 | Complete the audit log: auth, membership, role, billing, and export events | audit §3.5 item 6; Doc §11.4 | `specs/modules/review.md` (update) | done |
| TS-117 | Data export and account deletion (GDPR/DPDP) | audit §3.5 item 5; Doc §11.5 | `specs/modules/auth.md` (update) | done |
| TS-118 | Pagination on all list endpoints; `/api/health/details` super-admin gate in every environment | audit TS-L01, TS-L02 | `specs/modules/core.md` (update) | done |
| TS-119 | Accessibility: `eslint-plugin-jsx-a11y` + `axe-core` in CI, then WCAG 2.1 AA assessment | audit TS-L03; Doc §9 | `specs/frontend.md` (update) | done |
| TS-120 | Repository governance: default branch, branch protection, `CODEOWNERS`; document the venv install | audit TS-O03, TS-L04 | `docs/governance.md`, `README.md` | done |

## Second-round production readiness audit (2026-07-29, commit `d651d00`)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-121 | Second-round production readiness audit: re-verify TS-* findings, review rulepacks, auth, and packaging; update `PRODUCTION_READINESS_AUDIT.md` | `END_TO_END_PRODUCTION_AUDIT_PROMPT.md` | `PRODUCTION_READINESS_AUDIT.md` | done |
| TS-122 | **BLOCKER** `switch_workspace` must commit the rotated refresh-token session | audit TS-A06; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-123 | **BLOCKER** `resend-verification` must not return the raw verification token; send via email only | audit TS-A07; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-124 | **BLOCKER** `backend/Dockerfile` must install runtime extras (`celery`, `billing`, `scheduler`, `ocr`) and boot in CI | audit TS-O04; Doc §16 | `specs/deployment.md` (create) | done |
| TS-125 | **PRODUCT BLOCKER** Complete rulepack QS validation or add a beta/disclaimer flag so paid workspaces see unvalidated patterns | audit TS-P02; Doc §14 | `specs/modules/rulepacks.md` (update) | done |
| TS-126 | Hash `Invitation.token` instead of storing it plaintext | audit TS-A08; Doc §5 | `specs/modules/auth.md` (update) | done |
| TS-127 | Require TOTP verification before committing `mfa_method=totp` | audit TS-A09; Doc §5 | `specs/modules/auth.md` (update) | done |

## Third-round production readiness audit (2026-07-29, commit `d651d00`)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-128 | Third-round production readiness audit rerun from scratch: re-verify all `TS-*` findings, search for new auth/tenant/deployment/product issues, update `PRODUCTION_READINESS_AUDIT.md` | `END_TO_END_PRODUCTION_AUDIT_PROMPT.md` | `PRODUCTION_READINESS_AUDIT.md` | done |
| TS-129 | **BLOCKER** `create_invitation` and `accept_invitation` must verify `project_id` belongs to the invitation's workspace before persisting `ProjectMember` | audit TS-A10; Doc §5 | `specs/modules/auth.md` (update) | done |

## Fifth-round production readiness audit (2026-07-29)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-130 | Fifth-round end-to-end re-audit of trunk: review notifications, drafting, timeline, risk/assistant adapters, ingestion async/direct routes; skip existing `TS-*` findings and append new gaps | `END_TO_END_PRODUCTION_AUDIT_PROMPT.md` | `PRODUCTION_READINESS_AUDIT.md` | done |

## Sixth-round production readiness audit (2026-07-29)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-131 | Sixth-round end-to-end re-audit of trunk: review core storage, CORS/allowed-hosts guard, Stripe provider, tus I/O, and review/authz scoping; skip existing `TS-*` findings and append new gaps | `END_TO_END_PRODUCTION_AUDIT_PROMPT.md` | `PRODUCTION_READINESS_AUDIT.md` | done |

## Seventh-round production readiness audit (2026-07-29)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-132 | Seventh-round end-to-end re-audit of trunk: audit product invariants (money as minor units, source-page provenance, deterministic severity, multi-workspace auth); skip existing `TS-*` findings and append new gaps | `END_TO_END_PRODUCTION_AUDIT_PROMPT.md` | `PRODUCTION_READINESS_AUDIT.md` | done |


## Post-audit implementation tasks (generated from 61-finding tracker)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-133 | Synchronous extraction blocks the async event loop in upload_document | audit TS-I04; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-134 | BOQ run endpoint accepts unbounded CSV payloads | audit TS-I05; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/boq.md` (update) | done |
| TS-135 | Session provider keeps a stale workspace list after switch/refresh | audit TS-F02; `PRODUCTION_READINESS_AUDIT.md` | `specs/frontend.md` (update) | done |
| TS-136 | Risk classifier uses an invalid default Anthropic model name | audit TS-R02; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/risk.md` (update) | done |
| TS-137 | Risk classifier uses brittle string slicing and no schema validation | audit TS-R01; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/risk.md` (update) | done |
| TS-138 | Days_to_submission mixes UTC and local time for naive deadlines | audit TS-D02; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/comparison.md` (update) | done |
| TS-139 | Qualification matrix marks missing criteria as not_met with HIGH severity | audit TS-Q01; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/qualification.md` (update) | done |
| TS-140 | BOQ engine relies on DuckDB reading df from caller scope | audit TS-X02; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/boq.md` (update) | done |
| TS-141 | Cross-reference search loads all clauses regardless of limit | audit TS-A11; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/crossref.md` (update) | done |
| TS-142 | Confirm_deadline does not verify the deadline belongs to the opportunity | audit TS-I06; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-143 | Baseline freeze has a race condition on version numbering | audit TS-B05; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/baseline.md` (update) | done |
| TS-144 | Uploaded filename can inject Content-Disposition header in file download | audit TS-S03; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/core.md` (update) | done |
| TS-145 | Assistant agent has no output guard and includes user prompt verbatim | audit TS-A13; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/assistant.md` (update) | done |
| TS-146 | Notifications deadline-alert scheduler calls a missing WorkspaceAdmin method | audit TS-N02; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/notifications.md` (update) | done |
| TS-147 | Register_document accepts unbounded sample_text and processes it synchronously | audit TS-I07; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-148 | Async process_document Celery task does not classify, segment clauses, update the submission deadline, or run OCR | audit TS-I08; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-149 | Assistant agent uses an invalid default Anthropic model name | audit TS-A14; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/assistant.md` (update) | done |
| TS-150 | Review audit trail endpoint ignores opportunity_id | audit TS-A15; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/review.md` (update) | done |
| TS-151 | Artifact.version uses a non-atomic read-modify-write increment | audit TS-B06; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/drafting.md` (update) | done |
| TS-152 | Timeline ICS export appends Z to naive or local datetimes; synthetic tender_published uses created_at | audit TS-D03; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/timeline.md` (update) | done |
| TS-153 | LocalStorage async methods perform synchronous file I/O | audit TS-S04; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/core.md` (update) | done |
| TS-154 | Production guard for CORS and allowed hosts can be bypassed with a comma-separated wildcard | audit TS-O05; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/core.md` (update) | done |
| TS-155 | Stripe checkout uses hardcoded example.com redirect URLs | audit TS-B07; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/billing.md` (update) | done |
| TS-156 | Stripe webhook verifier swallows all exceptions and returns None | audit TS-B08; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/billing.md` (update) | done |
| TS-157 | Tus endpoints perform synchronous file I/O and OPTIONS returns a non-compliant empty body | audit TS-I09; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-158 | POST /api/review/findings/{finding_id} does not scope by opportunity | audit TS-A16; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/review.md` (update) | done |
| TS-159 | Finding.amount_exposure and monetary thresholds are stored/extracted as float major units, violating the minor-units invariant | audit TS-C01; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/findings.md` (update) | done |
| TS-160 | XLSX/CSV text extraction does not emit page markers, so spreadsheet-derived deadlines and clauses lose page provenance | audit TS-I10; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/ingestion.md` (update) | done |
| TS-161 | Email/password login selects an arbitrary workspace for multi-workspace users | audit TS-A17; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/auth.md` (update) | done |
| TS-162 | Severity evaluator silently defaults missing facts to 0 | audit TS-R03; `PRODUCTION_READINESS_AUDIT.md` | `specs/modules/risk.md` (update) | done |
| TS-163 | Account-centric auth re-architecture: account as top-level identity, workspace created after login, OTP on every login, remove social login, email+mobile verification, account/security settings | user request; Doc §5 | `specs/modules/auth.md`, `specs/frontend.md` (update) | done |
| TS-164 | Replace Anthropic LLM integration with OpenRouter (OpenAI-compatible API) for risk classifier and assistant agent | user request; `PRODUCTION_READINESS_AUDIT.md` TS-R02/TS-A14 | `specs/modules/risk.md`, `specs/modules/assistant.md`, `docs/deployment.md` | done |
| TS-165 | Add MinIO storage example to production env and deployment docs | user request | `.env.prod`, `docs/deployment.md` | done |
| TS-166 | Create end-to-end automation test scenarios doc and check in the end-to-end audit prompt | user request | `evals/e2e/` | done |
| TS-167 | Expand end-to-end scenarios to cover security, concurrency, performance, compliance, integrations, and edge cases | user request | `evals/e2e/scenarios.md` | done |
| TS-168 | Add assistant non-risk scenarios and sample tender/Q&A fixtures to end-to-end tests | user request | `evals/e2e/scenarios.md`, `evals/e2e/fixtures/` | done |
| TS-169 | Add account settings, admin, payment settings, tickets, user analysis, and log-observability end-to-end scenarios | user request | `evals/e2e/scenarios.md` | done |
| TS-170 | Implement missing admin, billing self-service, support tickets, user analytics, and observability log features (parent) | user request; scenarios TS-169 | `tasks/backlog.md`, `specs/modules/auth.md`, `specs/modules/billing.md`, `specs/modules/support.md`, `specs/modules/analytics.md`, `specs/modules/admin.md` | done |
| TS-171 | Admin user/workspace management: suspend/unsuspend/delete/search user, workspace detail, plan change | TS-170 | `backend/app/modules/auth/`, `specs/modules/auth.md` | done |
| TS-172 | Billing self-service: payment settings, subscription/cancel plan | TS-170 | `backend/app/modules/billing/`, `specs/modules/billing.md` | done |
| TS-173 | Support tickets module: create/reply/admin manage tickets with attachments | TS-170 | `backend/app/modules/support/`, `specs/modules/support.md` | done |
| TS-174 | User analysis/reports: risk summary, deadline dashboard, BOQ defect summary, report export | TS-170 | `backend/app/modules/analytics/`, `specs/modules/analytics.md` | done |
| TS-175 | Observability log search: admin audit-log/log search with filters | TS-170 | `backend/app/core/audit.py`, `backend/app/modules/auth/router.py`, `specs/modules/admin.md` | done |
| TS-176 | Close remaining product needs: notification preferences UI, admin/billing/support/analytics UI, local infra, E2E automation, alerting runbooks | user request | `frontend/`, `docker-compose.yml`, `frontend/e2e/`, `docs/runbooks/` | done |
| TS-177 | Format analytics dashboard: render risk/deadline/BOQ summaries as cards and tables instead of raw JSON | user request | `frontend/app/analytics/page.tsx` | done |
| TS-178 | Add OpenTelemetry tracing and self-hosted Jaeger/Grafana observability stack with automation to verify traces | user request | `backend/app/core/tracing.py`, `docker-compose.yml`, `docs/runbooks/observability.md`, `scripts/verify-traces.sh` | done |
| TS-179 | Update testing skill with observability demo notes (Jaeger/Grafana/network) | TS-178 | `.agents/skills/testing-tendershield/SKILL.md` | done |
| TS-180 | Add request access logging and enrich traces with user/workspace/ticket attributes for observability | user request | `backend/app/core/logging_middleware.py`, `backend/app/core/tracing.py`, `backend/app/core/deps.py` | done |
| TS-181 | Fix `tendershield.access` logger handler so access logs print without custom uvicorn config | TS-180 follow-up | `backend/app/main.py` | done |
| TS-182 | Persist access logs to JSON file and ship to Loki + Grafana for search/dashboard | user request | `backend/app/core/logging.py`, `docker-compose.yml`, `observability/promtail/`, `observability/grafana/` | done |
| TS-183 | Map admin/billing APIs to UI: payment history, plan history, coupon/discount codes | user request | `backend/app/modules/billing/`, `frontend/app/billing/`, `frontend/app/admin/coupons/` | done |
| TS-184 | Move billing plan and `free_review_used` from workspace to user account; update admin UI and billing spec | user request | `backend/app/modules/auth/models.py`, `backend/app/modules/billing/models.py`, `backend/app/modules/auth/service.py`, `backend/app/modules/billing/service.py`, `frontend/app/admin/users/[id]/page.tsx`, `specs/modules/billing.md` | done |
| TS-185 | Move billing usage, payment_log, invoices, webhook_events, billing_provider and billing_settings from workspace to user account | user request | `backend/app/modules/auth/models.py`, `backend/app/modules/billing/models.py`, `backend/app/modules/auth/workspaces.py`, `backend/app/modules/billing/service.py`, `backend/app/modules/billing/router.py`, `backend/migrations/versions/c7dac720f0e6_*.py`, `frontend/app/billing/settings/page.tsx`, `specs/modules/billing.md` | done |
| TS-186 | Scope AI assistant retrieval to user account/workspace and add admin chat mode for super-admins | user request | `backend/app/modules/assistant/`, `specs/modules/assistant.md` | done |
| TS-187 | Microsoft Office MCP server for QS engineers: read/write Word/Excel tender data | user request | `mcp-servers/office-mcp/`, `specs/modules/mcp-office.md`, `docs/integrations/office-mcp.md` | done |
| TS-188 | AI-generated dynamic tender plan dashboard: natural-language query with dynamic charts, sequence diagrams, and mind maps | user request | `backend/app/modules/analytics/`, `frontend/app/plan/`, `specs/modules/plan-dashboard.md` | done |
| TS-189 | Add backend tests and audit-log verification for assistant scoping, admin chat, and plan dashboard | TS-186/188 follow-up | `backend/tests/`, `backend/tests/test_assistant.py`, `backend/tests/test_analytics.py` | done |
| TS-190 | Integrate Office MCP server with TenderShield API so QS engineers can pull opportunities/findings into Word/Excel | TS-187 follow-up | `mcp-servers/office-mcp/`, `docs/integrations/office-mcp.md` | done |
| TS-191 | Add plan dashboard templates, saved snapshots, and export to PowerPoint/PDF | TS-188 follow-up | `frontend/app/plan/`, `backend/app/modules/analytics/`, `specs/modules/plan-dashboard.md` | done |
| TS-192 | Add user-facing plan upgrade/downgrade endpoints and UI | user request | `backend/app/modules/billing/`, `frontend/app/billing/`, `specs/modules/billing.md` | done |
| TS-193 | Reframe AI plan dashboard as the assistant: dedicated `/assistant` chat UI with collapsible dashboard panel for KPIs/tables/charts/Mermaid | user request; TS-188 | `specs/modules/assistant.md`, `frontend/app/assistant/`, `frontend/app/plan/page.tsx`, `frontend/components/plan-dashboard.tsx`, `backend/app/modules/assistant/` | done |
| TS-194 | Fix plan snapshot export 404 and default OpenRouter model to `openrouter/free` with clear no-key messaging | user request; E2E findings | `backend/app/modules/analytics/`, `backend/app/core/config.py`, `.env.*`, `specs/modules/plan-dashboard.md` | done |
| TS-297 | Make AI Assistant workspace-scoped instead of opportunity-scoped | user request; Build Doc §8 | `backend/app/modules/assistant/`, `frontend/app/assistant/page.tsx`, `frontend/lib/api.ts`, `specs/modules/assistant.md` | done |
| TS-298 | CI gate: fail a PR when code changed but `CHANGELOG.md` didn't (enforce CLAUDE.md §1.5) | user request; CLAUDE.md §1.5 "a push without a changelog entry is incomplete work" | `specs/902-changelog-check.md` | done |

## Phase 16 — Defensibility, Domain-Agnosticism & Scale Validation

Requirement source: `docs/TenderShield_Market_Strategy_2026.md`.
Every task below maps to a **moat class** (Strategy §B.2): 1 = proprietary data,
2 = deterministic computation, 3 = accountability, 4 = workflow position.
A task that maps to no moat class does not belong in this phase.

Tracker: `tasks/phase16_tracker.md`.

### 16.A — Employer Behaviour Graph (`marketdata`) — moat 1

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-195 | `marketdata` module scaffold: ModuleSpec, config flag, registry capabilities, graceful absence | Strategy §C.1 | `specs/modules/marketdata.md` | done |
| TS-196 | Corpus schema + migrations: `md_tenders`, `md_awards`, `md_employers`, `md_profiles`, `md_harvest_runs` (OCDS-shaped, non-tenant) | Strategy §A.2, §C.1 | `specs/modules/marketdata.md` | done |
| TS-197 | Source adapters P0: CPPP + one state NIC portal — legality review recorded in adapter docstring, robots/rate-limit compliant | Strategy §A.2 | `specs/eval-at-scale.md` §2.2 | done |
| TS-198 | Employer identity resolution: deterministic normalization to family/division/region with confidence; unresolved stays unresolved | Strategy §C.1 | `specs/modules/marketdata.md` | done |
| TS-199 | Deterministic aggregates + sample-size suppression (n ≥ 12) + comparable-set builder that returns its own filter | Strategy §C.1 | `specs/modules/marketdata.md` | done |
| TS-200 | Employer context block on risk findings + `/api/marketdata/*` read routes | Strategy §C.1 | `specs/modules/marketdata.md` | done |

### 16.B — Pricing intelligence (`pricing-intel`) — moat 2

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-201 | `pricing-intel` module scaffold + `pi_*` migrations; assert module has no LLM client dependency | Strategy §C.2 | `specs/modules/pricing-intel.md` | done |
| TS-202 | `price_impact` block in rulepack schema + named versioned formula registry with worked-example tests | Strategy §C.2 | `specs/modules/pricing-intel.md` | done |
| TS-203 | Bid loading sheet: accepted findings → rupee loading with formula and inputs shown; missing input → no loading | Strategy §C.2 | `specs/modules/pricing-intel.md` | done |
| TS-204 | SOR/DSR rulepack data format + loader (`rulepacks/<pack>/rates/<authority>/<year>.yaml`) | Strategy §C.4 | `specs/modules/pricing-intel.md` | done |
| TS-205 | Rate benchmarking: two-band matching (code / description), headline variance from code matches only, unmatched reported | Strategy §C.4 | `specs/modules/pricing-intel.md` | done |
| TS-206 | Cashflow & working-capital model with mandatory `assumptions[]` block; peak requirement + month | Strategy §C.3 | `specs/modules/pricing-intel.md` | done |
| TS-207 | Pricing artifacts inherit the review export gate; excluded from unreviewed tiers (test-asserted) | Build Doc §11.4; Strategy §C.2 | `specs/modules/pricing-intel.md` | done |

### 16.C — Express pay-per-report lane (`express`) — revenue / top of funnel

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-208 | `express` module scaffold + `ex_*` migrations; ephemeral internal workspace backing | Strategy §F.2 | `specs/modules/express-report.md` | done |
| TS-209 | Anonymous session lifecycle: create (email + acknowledgment), upload with pre-buffer size caps, expiry, high-entropy tokens | Strategy §F.2 | `specs/modules/express-report.md` | done |
| TS-210 | Teaser renderer: full deadline wall + missing-doc checklist + severity counts + 2 complete cited findings | Strategy §F.2 | `specs/modules/express-report.md` | done |
| TS-211 | Server-owned tier price table + guest checkout (Razorpay India / Stripe GCC-UK); client never sends an amount | Build Doc §15; audit TS-B01 | `specs/modules/express-report.md` | done |
| TS-212 | Webhook-only activation + full report delivery (in-app + emailed PDF); test proves redirect alone never unlocks | Build Doc §15.1 | `specs/modules/express-report.md` | done |
| TS-213 | `unreviewed` export variant: watermark on every page/format, acknowledgment logged with version/timestamp/IP, pricing outputs excluded | Build Doc §11.4; Strategy §F.2 | `specs/modules/express-report.md` | done |
| TS-214 | Anti-abuse (email/IP/document-hash limits, teaser dedupe), retention deletion job, magic-link claim into a workspace | Strategy §F.2 | `specs/modules/express-report.md` | done |

### 16.D — Outcome capture (`outcomes`) — moat 1

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-215 | `outcomes` module + `oc_*` workspace-scoped migrations; record/read bid outcome and risk materialization | Build Doc §1.1(9); Strategy §C.6 | `specs/modules/outcomes.md` | done |
| TS-216 | Prefill from public award record via `marketdata` with one-click confirm; manual path always available | Strategy §C.6 | `specs/modules/outcomes.md` | done |

### 16.E — Cross-cutting moat work

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-217 | Contradiction engine: fact-level cross-document disagreement + rulepack-configurable precedence naming the governing instance | Strategy §C.5 | `specs/modules/crossref.md` (update) | done |
| TS-218 | Correction loop: aggregate review corrections per pattern per employer family → **proposed** rulepack overlay in admin console; never auto-mutate | Build Doc §11.5, §2.4; Strategy §C.9 | `specs/modules/rulepacks.md` (update) | done |
| TS-219 | Reproducibility chain: pin `rulepack_version`/`model_id`/`prompt_hash`/`document_hash`/`engine_version` on every finding; deterministic stages byte-identical on re-run | Strategy §C.7 | `specs/modules/findings.md` (update) | done |

### 16.F — Domain-agnosticism

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-220 | Pack SDK: schema, validator CLI, pack test harness so a third party can author and verify a pack | Strategy §D.4 | `specs/modules/rulepacks.md` (update) | done |
| TS-221 | Ladder rung 1 trade checklists: plumbing/public-health, fire-fighting, structural steel, lifts (YAML only, zero code) | Strategy §D.2 | `rulepacks/in-works/boq/trade_checklists/` | done |
| TS-222 | Ladder rung 2 patterns: supply-and-erection — customs/GST variation, split delivery/erection LD, PG tests, free-issue material, O&M tail | Strategy §D.2 | `specs/modules/rulepacks.md` (update) | done |

### 16.G — Profitability instrumentation

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-223 | Per-review cost instrumentation (tokens in/out/cached, OCR pages, worker seconds, storage) tagged by opportunity/rulepack/model; p50+p95 cost-per-review metric; token-ceiling test guarding the retrieval-first property | Strategy §G.2, §G.3 | `specs/modules/observability.md` (update) | done |

### 16.H — Evaluation at scale (1,000+ tenders, automated)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-224 | Corpus schema + `scripts/corpus_harvest.py` with pluggable adapter interface (`fetch_index`, `fetch_documents`), sha256 storage, full provenance | Strategy §A.2 | `specs/eval-at-scale.md` §2 | done |
| TS-225 | Adapters: CPPP, state NIC, Etimad (official API), OCDS registry — each with recorded legality review and rate-limit compliance | Strategy §A.2, §E | `specs/eval-at-scale.md` §2.2 | done |
| TS-226 | M1 structural invariant suite (quote integrity, citations, no invented numbers, BOQ closure, determinism, currency, tenant isolation, degradation, budget, no-crash) | Build Doc §6.2, §6.5, §11.5 | `specs/eval-at-scale.md` §1 | done |
| TS-227 | M2 portal-metadata agreement scoring with `extraction_miss`/`extraction_wrong`/`portal_wrong` triage | `specs/eval-at-scale.md` §1 | `specs/eval-at-scale.md` | done |
| TS-228 | M3 outcome backtest with **time-based** train/test split (L1 MAPE, bidder count, award latency, retender AUC) | Strategy §C.1 | `specs/eval-at-scale.md` §1 | done |
| TS-229 | M4 metamorphic checks: format, order, addendum monotonicity, redundancy, locale invariance | `specs/eval-at-scale.md` §1 | `specs/eval-at-scale.md` | done |
| TS-230 | `scripts/bulk_eval.py`: Celery fan-out, disposable workspace per tender, checkpoint/resume, sharding, cost guard + kill switch, failure classification | `specs/eval-at-scale.md` §3 | `specs/eval-at-scale.md` | done |
| TS-231 | `scripts/eval_report.py`: `evals/runs/<run_id>/` scorecard + regression diff vs previous run on the same slice | Build Doc §11.5 | `specs/eval-at-scale.md` §3.2 | done |
| TS-232 | CI wiring: 20-tender smoke per PR (M1+M4, blocking), 100-tender nightly, 1,000+ weekly; >2pt headline drop blocks the change | Build Doc §11.5 | `specs/eval-at-scale.md` §3.4 | done |
| TS-233 | M5 human gold set: 50 tenders composed per the slice table, annotated per Build Doc §19, stored under `evals/gold-set/` | Build Doc §19, §14.2 | `specs/eval-at-scale.md` §1 | done |

### 16.I — North-star metric (added from founding research)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-234 | **North-star metric — "verified contractor margin protected"**: deterministic computation over accepted risk allowances, declined-bid exposure avoided, and BOQ defects corrected pre-submission; excludes speculative value; grows as Phases 18–19 land | Research Doc §12.1; Roadmap §6.1 | `specs/modules/outcomes.md` (update) | done |

---

### 16.J — Follow-ups discovered by the M1 invariant suite (TS-226)

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-294 | Add `Finding.document_id` (migration + risk/boq/qualification/standards writers) so quote/citation checks resolve to one document instead of any document sharing a page number | TS-226 finding; `specs/eval-at-scale.md` §1 | `specs/modules/findings.md` (update) | done |
| TS-295 | Add `Finding.currency` (ISO 4217) alongside `amount_exposure` so `check_currency_integrity` can assert an explicit currency, not just an int; required before Phase 16 multi-jurisdiction findings (Strategy §E.2) can be trusted cross-currency | TS-226 finding; Strategy §E.2 | `specs/modules/findings.md` (update) | done |
| TS-296 | Add `Finding.facts` (structured extraction facts, not just quote/detail) and `Opportunity.contract_value_minor` so `pricing.loading` can source real facts instead of caller-supplied query params | TS-203 finding; `specs/modules/pricing-intel.md` | `specs/modules/findings.md` (update), `specs/data-model.md` (update) | done |

## Phase 17 — Stage 2: Baseline Lock & Handover completion

Requirement source: Research Doc §4.E, §5.2; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4.
**Unlock gate:** Phase 16 exit gates green.
**Why:** change detection (Phase 18) diffs against a baseline. The `baseline` module freezes
documents but produces none of the *controls* stage 3 consumes.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-235 | Spec: `baseline` completion — controls, notice rules, cost codes, approval matrix, handover pack | Research Doc §4.E | `specs/modules/baseline.md` (update) | done |
| TS-236 | Award comparison: diff negotiated contract + accepted BOQ against tender assumptions; highlight concessions and new obligations with citations | Research Doc §5.2(10) | `specs/modules/baseline.md` | done |
| TS-237 | Risk → project watchlist: convert accepted tender findings into monitored project controls with owner, trigger and review cadence | Research Doc §4.E | `specs/modules/baseline.md` | done |
| TS-238 | Notice-rule register: per-contract notice types, trigger events, deadline arithmetic (deterministic), required content, correspondence addresses, authorized representatives | Research Doc §4.E, §5.2(13) | `specs/modules/standards.md` (update) | done |
| TS-239 | Approval matrix: role-based authority limits per action (notice issue, variation acceptance, claim submission) | Research Doc §4.E, §13 Negotiation | `specs/modules/auth.md` (update) | done |
| TS-240 | Cost-code model: create cost codes, map to BOQ items and variation categories; foundation for stage 3/4 valuation | Research Doc §4.E | `specs/modules/baseline.md` | done |
| TS-241 | Commercial handover pack export (site, planning, procurement, finance views) with hash-sealed baseline reference | Research Doc §4.E, §5.2(12) | `specs/modules/export.md` (update) | done |
| TS-242 | Baseline adoption telemetry: projects with a locked baseline, weekly active baseline users — measures the Phase 18 unlock gate | Research Doc §12.4 | `specs/modules/analytics.md` (update) | done |

---

## Phase 18 — Stage 3: Change & Notice Control ★ recurring revenue

Requirement source: Research Doc §4.F, §5.3; Roadmap §2, §4.
**Unlock gate:** *"Two projects use baseline weekly"* (Research Doc §12.4 / Phase-2 exit).
**Why this is the priority phase:** converts transactional revenue into per-project recurring
subscription (Research Doc §10.1), and creates the first real switching cost in the product.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-243 | Spec: `change` module — event model, sources, confidence, site confirmation, notice deadlines | Research Doc §4.F | `specs/modules/change.md` (new) | done |
| TS-244 | `change` module scaffold + migrations: `change_events`, `change_sources`, `change_confirmations` (workspace-scoped, RLS) | Research Doc §4.F | `specs/modules/change.md` | done |
| TS-245 | Baseline diff engine: compare new drawing/spec/instruction revisions against the locked baseline; emit candidate change events with citations | Research Doc §4.F, §5.3(15) | `specs/modules/change.md` | done |
| TS-246 | Change-signal ingestion: RFIs, site instructions, meeting minutes, daily reports — classified into candidate events with source provenance | Research Doc §4.F | `specs/modules/change.md` | done |
| TS-247 | Email ingestion adapter (forward-to-inbox address per project), with prompt-injection defenses for untrusted correspondence | Research Doc §4.F; Build Doc §11.3 | `specs/modules/change.md` | done |
| TS-248 | Potential-variation inbox: reason, source, affected scope, confidence band, triage queue | Research Doc §4.F | `specs/modules/change.md` | done |
| TS-249 | Impact linking: connect a change event to affected BOQ items, cost codes and subcontract packages | Research Doc §4.F | `specs/modules/change.md` | done |
| TS-250 | Site confirmation workflow: changed / not changed / clarification only / contractor risk / client risk / unknown — with recorded confirmer and timestamp | Research Doc §4.F, §5.3(16) | `specs/modules/change.md` | done |
| TS-251 | **Deterministic notice-deadline engine**: compute the notice deadline and required content from the Phase-17 notice-rule register; never LLM | Research Doc §4.F, §5.3(17); `CLAUDE.md` §4 | `specs/modules/change.md` | done |
| TS-252 | Deadline countdown, escalation rules and multi-channel alerts (email/WhatsApp) with per-event dedup | Research Doc §4.F | `specs/modules/notifications.md` (update) | done |
| TS-253 | Notice drafting: contract-specific template populated with **verified facts only**; three validators applied; human approval mandatory before issue | Research Doc §4.G, §5.3(18); Build Doc §6.5, §11.4 | `specs/modules/drafting.md` (update) | done |
| TS-254 | Evidence attachment + chain of custody on change events (type, date, creator, custody chain, event link) | Research Doc §4.G, §6.3 | `specs/modules/evidence.md` (new) | done |
| TS-255 | **Evidence-completeness scoring** per event with a list of missing contemporaneous records | Research Doc §2.1, §4.G | `specs/modules/evidence.md` | done |
| TS-256 | Per-project billing lane: project activation + per-project monthly subscription (server-owned prices, webhook-only activation) | Research Doc §10.1; Build Doc §15 | `specs/modules/billing.md` (update) | done |

---

## Phase 19 — Stage 4: Claims & Evidence Workspace

Requirement source: Research Doc §4.G, §5.3.
**Unlock gate (both required, Research Doc §12.4):** *"Do not build claims valuation until users
capture contemporaneous evidence in the platform"* **and** *"Document at least five real events
before work completion."*

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-257 | Spec: `claims` module — chronology, quantum, delay register, negotiation tracking | Research Doc §4.G | `specs/modules/claims.md` (new) | done |
| TS-258 | `claims` module scaffold + migrations (workspace-scoped, RLS) | Research Doc §4.G | `specs/modules/claims.md` | done |
| TS-259 | Chronology builder from approved correspondence, revisions and confirmed events — every entry cited | Research Doc §4.G | `specs/modules/claims.md` | done |
| TS-260 | Evidence checklist per claim type: instruction, baseline, revised scope, labour, plant, material, schedule, photos, approvals | Research Doc §4.G | `specs/modules/evidence.md` (update) | done |
| TS-261 | **Quantum workspace**: deterministic quantity × rate × daywork calculation with reviewer sign-off; zero LLM arithmetic | Research Doc §4.G, §7.1; `CLAUDE.md` §4 | `specs/modules/claims.md` | done |
| TS-262 | Delay-event register with links to programme records; **no autonomous entitlement conclusion** | Research Doc §4.G | `specs/modules/claims.md` | done |
| TS-263 | Draft generators: interim particulars, variation proposal, EOT narrative, full claim package — facts injected, prose generated, all validators applied | Research Doc §4.G; Build Doc §6.5 | `specs/modules/drafting.md` (update) | done |
| TS-264 | Issue → response → negotiation → settlement tracking with outcome capture | Research Doc §4.G, §5.3(21) | `specs/modules/claims.md` | done |
| TS-265 | Outcome feedback into the private learning set: approved / negotiated / rejected / withdrawn / disputed | Research Doc §5.3(22) | `specs/modules/outcomes.md` (update) | done |
| TS-266 | Chain-integrity test: every claim traces to a notice → event → baseline obligation → tender clause; a broken link fails the build | Research Doc §14; Roadmap §5 | `specs/modules/claims.md` | done |
| TS-267 | Conflicts control: block serving opposing parties on the same project | Research Doc §11.1 | `specs/modules/auth.md` (update) | done |
| TS-268 | Claim-cycle-time and notice-timeliness workflow metrics | Research Doc §12.2 | `specs/modules/analytics.md` (update) | done |
| TS-269 | North-star extension: recovered claim value linked to TenderShield evidence feeds "margin protected" | Research Doc §12.1 | `specs/modules/outcomes.md` (update) | done |
| TS-270 | Site evidence capture: mobile geotagged photos, labour/plant/daywork records, offline sync, evidence-quality prompts | Research Doc §13 Site evidence | `specs/modules/evidence.md` (update) | done |

---

## Phase 20 — Stage 5: Commercial Control Tower & Portfolio Intelligence

Requirement source: Research Doc §4.H, §12.2.
**Unlock gate:** Phase 19 in production use with at least one customer.

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-271 | Spec: `controltower` module — exposure model, dashboards, forecasting | Research Doc §4.H | `specs/modules/controltower.md` (new) | done |
| TS-272 | Commercial exposure model (deterministic): at-risk revenue, unnotified change, submitted / certified / rejected value, ageing, cash exposure | Research Doc §4.H | `specs/modules/controltower.md` | done |
| TS-273 | Project deadline + evidence-health dashboard | Research Doc §4.H | `specs/modules/controltower.md` | done |
| TS-274 | Risk-adjusted forecast at completion with explicit assumptions block | Research Doc §4.H | `specs/modules/controltower.md` | done |
| TS-275 | Client / consultant response-time analytics | Research Doc §4.H | `specs/modules/controltower.md` | done |
| TS-276 | Portfolio clause trends, recurring omission patterns and loss-reason analysis across projects | Research Doc §4.H | `specs/modules/analytics.md` (update) | done |
| TS-277 | Executive summaries with source links and drill-down | Research Doc §4.H | `specs/modules/controltower.md` | done |
| TS-278 | Payment control: RA/progress bill checklist, certification variance, retention and security release dates, ageing and collection actions | Research Doc §13 Payment control | `specs/modules/controltower.md` | done |
| TS-279 | Economics metrics: paid conversion, gross margin, CAC payback, project retention, expansion revenue | Research Doc §12.2 | `specs/modules/analytics.md` (update) | done |
| TS-280 | Customer-outcome metrics: risks priced, bad bids declined, omissions corrected, value notified/certified, hours saved | Research Doc §12.2 | `specs/modules/analytics.md` (update) | done |

---

## Phase 21 — Integrations, Subcontract Control & Advisor Edition

Requirement source: Research Doc §4.I, §8.3, §13.
**Unlock gate:** *"Integration marketplaces only after workflow proof"* (Research Doc §10.2);
*"Start with uploads/exports; add APIs after proven value"* (§12.3).

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-281 | Spec: integration adapter framework (auth, sync model, conflict handling, rate limits) | Research Doc §4.I | `specs/modules/integrations.md` (new) | done |
| TS-282 | SharePoint / OneDrive document-source adapter | Research Doc §4.I | `specs/modules/integrations.md` | done |
| TS-283 | Procore adapter (documents, RFIs, change events) | Research Doc §4.I | `specs/modules/integrations.md` | done |
| TS-284 | Autodesk Construction Cloud adapter | Research Doc §4.I | `specs/modules/integrations.md` | done |
| TS-285 | Oracle Aconex adapter | Research Doc §4.I | `specs/modules/integrations.md` | done |
| TS-286 | ERP adapter (cost codes, committed cost, certified value) — Tally / SAP / MS Dynamics shortlist | Research Doc §4.I | `specs/modules/integrations.md` | done |
| TS-287 | Schedule import: P6 / MS Project; event-to-activity links; contemporaneous programme snapshots | Research Doc §13 Schedule linkage | `specs/modules/integrations.md` | done |
| TS-288 | **Subcontract control**: flow-down clause comparison against the main contract, subcontract scope-gap checks | Research Doc §13 Subcontract control | `specs/modules/subcontract.md` (new) | done |
| TS-289 | Back-to-back notice calendar and **pay-when-paid exposure flags** across the subcontract chain | Research Doc §13 Subcontract control | `specs/modules/subcontract.md` | done |
| TS-290 | Advisor Edition: multi-client workspace separation, review queues, per-client usage billing | Research Doc §8.3, §10.1 | `specs/modules/advisor.md` (new) | done |
| TS-291 | White-label branded report templates for the advisor channel | Research Doc §8.3 | `specs/modules/advisor.md` | done |
| TS-292 | Public API + e-signature integration for notice issue | Research Doc §4.I | `specs/modules/public_api.md` (new) | done |

## Tooling

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-293 | `scripts/task_tracker.py`: parse/validate `tasks/backlog.md`, report progress by phase, list incomplete/blocked tasks, cross-check tracker files; wired into CI as a blocking job | `CLAUDE.md` §1; user request | `scripts/task_tracker.py` | done |

## Round 8 release-blocker fixes

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-299 | Fix Round 8 audit release blockers: public_api RLS/auth, integrations/public_api opportunity validation, auth invitation/member 500s, `.env.local` mobile verification mismatch, backlog tracker cleanup | Round 8 audit; Build Doc §3.2, §5, §6, §11.4 | `PRODUCTION_READINESS_AUDIT.md` §6 | done |

## Feature coverage audit

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-300 | Cross-check every capability in `TenderShield_AI_Architecture_and_Market_Research.pdf` against the codebase, specs, tasks and tests; produce `FEATURE_COVERAGE.md` with implemented/partial/missing verdicts | Research Doc §4, §5, §9 | `FEATURE_COVERAGE.md` | done |

## Phase 22 — Gap closure roadmap

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-301 | Change / variation inbox and confirmation workflow UI | Research Doc §4.F, §5.3; FEATURE_COVERAGE.md §F | frontend/app/opportunities/[id]/changes/ | done |
| TS-302 | Claims workspace UI | Research Doc §4.G, §5.3; FEATURE_COVERAGE.md §G | frontend/app/opportunities/[id]/claims/ | done |
| TS-303 | Commercial Control Tower dashboards UI | Research Doc §4.H, §12.2; FEATURE_COVERAGE.md §H | frontend/app/controltower/ or /analytics/controltower | done |
| TS-304 | Subcontract management UI | Research Doc §13 Subcontract control; FEATURE_COVERAGE.md §I | frontend/app/opportunities/[id]/subcontracts/ | done |
| TS-305 | Integration source configuration UI | Research Doc §4.I; FEATURE_COVERAGE.md §I | frontend/app/settings/integrations/ | done |
| TS-306 | Public API key management UI | Research Doc §4.I; FEATURE_COVERAGE.md §I | frontend/app/settings/api-keys/ | done |
| TS-307 | Admin / Advisor multi-client workspace UI | Research Doc §3.3 Advisor Edition, §8.3; FEATURE_COVERAGE.md §I | frontend/app/advisor/ and admin workspace switcher | done |
| TS-308 | Plan dashboard navigation link | Research Doc §4 analytics; plan-dashboard spec | frontend/components/nav/ | done |
| TS-309 | Pricing / rate benchmark / cashflow results UI | Research Doc §4.C rate build-up; pricing-intel spec | frontend/app/opportunities/[id]/pricing/ | done |
| TS-310 | DOCX upload and text extraction | Research Doc §4.A bulk upload; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/extract.py | done |
| TS-311 | Image (PNG/JPG/TIFF) upload and standalone OCR | Research Doc §4.A OCR; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/ocr.py | done |
| TS-312 | ZIP bulk package upload | Research Doc §4.A bulk upload; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/router.py | done |
| TS-313 | Exported model schedule ingestion (CSV/IFC) | Research Doc §4.A exported model schedules; FEATURE_COVERAGE.md §A | backend/app/modules/integrations/adapters.py ScheduleAdapter + new ingestion route | done |
| TS-314 | Automatic addendum comparison and duplicate detection | Research Doc §4.A version detection, addendum comparison; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/service.py | done |
| TS-315 | Language detection and multilingual extraction assistance | Research Doc §8.1 localization; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/doc_text.py | done |
| TS-316 | Defined-term glossary and linking | Research Doc §4.A defined-term linking; FEATURE_COVERAGE.md §A | backend/app/modules/ingestion/segment.py + new glossary model | done |
| TS-317 | Clause deviation scoring against playbook/standard | Research Doc §4.B clause deviation comparison; FEATURE_COVERAGE.md §B | backend/app/modules/comparison/ or new risk/deviation.py | done |
| TS-318 | BOQ cross-check against drawing schedules | Research Doc §4.C cross-check BOQ vs drawings; FEATURE_COVERAGE.md §C | backend/app/modules/boq/engine.py | done |
| TS-319 | Missing-scope suggestions from historical patterns | Research Doc §4.C historical patterns; FEATURE_COVERAGE.md §C | backend/app/modules/boq/engine.py + outcomes/ | done |
| TS-320 | Rate build-up templates and sensitivity UI | Research Doc §4.C rate build-up/sensitivity; FEATURE_COVERAGE.md §C | frontend/app/opportunities/[id]/pricing/ + backend/pricing | done |
| TS-321 | Drawing register, title-block extraction, revision and superseded controls | Research Doc §4.D; FEATURE_COVERAGE.md §D | new backend/app/modules/drawings/ | done |
| TS-322 | Drawing overlay and region-level change detection | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/compare.py | done |
| TS-323 | Drawing symbol and count assistance | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/vision.py | done |
| TS-324 | Drawing-to-BOQ link | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/ + boq/ | done |
| TS-325 | Drawing confidence heatmap | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/heatmap.py | done |
| TS-326 | IFC / model quantity import | Research Doc §4.D; FEATURE_COVERAGE.md §D | backend/app/modules/drawings/ifc.py | done |
| TS-327 | Live change signal ingestion from RFIs, emails, meeting minutes, site instructions, daily reports | Research Doc §4.F; FEATURE_COVERAGE.md §F | backend/app/modules/change/signals.py + notifications/email adapters | done |
| TS-328 | Delay-event critical-path and programme links | Research Doc §4.G delay-event register; FEATURE_COVERAGE.md §G | backend/app/modules/change/delay_analysis.py | done |
| TS-329 | Portfolio clause trends, recurring omission patterns and loss-reason analytics | Research Doc §4.H; FEATURE_COVERAGE.md §H | backend/app/modules/controltower/service.py + frontend/controltower | done |
| TS-330 | Document-class ACL | Research Doc §4.I role-based access by document class; FEATURE_COVERAGE.md §I | backend/app/modules/auth/acl.py + settings UI | done |
| TS-331 | Custom branded report templates | Research Doc §4.I export to customer templates; FEATURE_COVERAGE.md §I | backend/app/modules/export/models.py + settings UI | done |
| TS-332 | Data residency, encryption at rest and retention controls | Research Doc §11.2 security baseline; FEATURE_COVERAGE.md §I | backend/app/modules/governance + settings UI | done |
| TS-333 | Live CDE/ERP connector sync (OAuth + polling/webhooks) | Research Doc §4.I; FEATURE_COVERAGE.md §I | backend/app/modules/integrations/connectors/ + API | done |
| TS-334 | Generic dynamic REST connector (no-code) for ERP/Oracle/sandbox systems — store connector spec in DB, DynamicRestConnector fetches from UI, test endpoint pings sandbox URL without persisting | User request (post-Phase 22) | backend/app/modules/integrations/dynamic.py + frontend/settings/integrations | done |
| TS-342 | Backfill backend tests for Phase 22 modules and fix connector/RLS/subcontract gaps discovered during testing (merged as separate task) | CLAUDE.md §1; user request | backend/tests/test_integrations.py, test_public_api.py, test_subcontract.py | done |

## Phase 23 — Round 9 audit gap closure

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-335 | Round 9 gap-closure requirements doc + spec | `docs/GAP_CLOSURE_REQUIREMENTS.md`; `PRODUCTION_READINESS_AUDIT.md` | `specs/903-round9-gap-closure.md` | done |
| TS-336 | Dynamic REST connector SSRF protection | `PRODUCTION_READINESS_AUDIT.md` TS-INT-03; `specs/modules/integrations.md` | `backend/app/modules/integrations/connectors/dynamic.py` | done |
| TS-337 | Integration source webhook signature verification | `PRODUCTION_READINESS_AUDIT.md` TS-INT-02; `specs/modules/integrations.md` | `backend/app/modules/integrations/router.py`, `service.py`, `connectors/base.py` | done |
| TS-338 | Document-class ACL enforcement on read/export/change/claims/drafting paths | `PRODUCTION_READINESS_AUDIT.md` TS-ACL-01; `specs/modules/auth.md` | `backend/app/modules/auth/acl.py` + router deps | done |
| TS-339 | Public API `request_signature` `notice_id` / `change_event_id` workspace validation | `PRODUCTION_READINESS_AUDIT.md` TS-PUB-04; `specs/modules/public_api.md` | `backend/app/modules/public_api/service.py` | done |
| TS-340 | Governance retention / archive execution job | `PRODUCTION_READINESS_AUDIT.md` TS-GOV-01; `specs/modules/governance.md` | `backend/app/modules/governance/` + scheduler | done |
| TS-341 | Eval deadline and tender-value match ≥95% | `PRODUCTION_READINESS_AUDIT.md` TS-EV-01; `specs/modules/evalmetadata.md` | `backend/app/evalmetadata/m2.py`, `evalrunner/pipeline.py`, `scripts/eval_ci_smoke.py` | done |

## Phase 24 — Round 10 production-readiness re-audit

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-343 | Round 10 production-readiness re-audit: refresh `PRODUCTION_READINESS_AUDIT.md` for `e912395`, re-run validation matrix, and document `.env.local` test hermeticity (TS-ENV-01) | `PRODUCTION_READINESS_AUDIT.md`; user request | `PRODUCTION_READINESS_AUDIT.md` | done |

## Phase 25 — Automated full-pipeline validation importer

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-344 | End-to-end validation importer: create a test workspace by API, seed 50+ sample opportunities, run ingestion/risk/BOQ/baseline and downstream features, and produce a pass/fail report | user request; `specs/eval-at-scale.md` | `scripts/validate_full_pipeline.py` | done |

## Phase 26 — Validation UI follow-up bugfixes

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-345 | Validation UI follow-up: fix Control Tower `Margin protected` `₹NaN`, per-opportunity dashboard `unavailable` flag, and NaN currency formatting | testing; `PRODUCTION_READINESS_AUDIT.md` UI findings | `frontend/app/controltower/page.tsx` | done |

## Phase 27 — Validation against real public-tender corpus + rulepack expansion

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-346 | Run validation importer against real public-tender corpus (India/UAE) via `scripts/corpus_harvest.py` with `TS_OPENROUTER_API_KEY` for AI risk validation | user request; `specs/eval-at-scale.md` | `scripts/validate_full_pipeline.py` | todo |
| TS-347 | Expand `in-works` rulepack: avoid same 5 synthetic risk findings on every opportunity; add UAE/India notice-standard and employer-family overlays | user request; `PRODUCTION_READINESS_AUDIT.md` UI findings | `rulepacks/in-works/` | todo |

## Phase 28 — Admin/rulepack, AI assistant, and project dashboards

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-348 | Rulepack admin: upload rulepacks (YAML + source PDF/Word/image/zip), store versions, and apply them per project | user request; `rulepacks/` | `specs/modules/rulepacks-admin.md` | done |
| TS-349 | Rulepack per-project selection: choose one or more rulepacks (universal + regional + private) at opportunity creation and later | user request; `specs/modules/rulepacks.md` | `specs/modules/rulepacks-admin.md` | done |
| TS-350 | Private rulepacks: user/workspace-scoped packs that are not shared with other workspaces | user request; `specs/modules/rulepacks.md` | `specs/modules/rulepacks-admin.md` | done |
| TS-351 | RAG-assisted rulepack expansion: suggest new YAML patterns from uploaded circulars/rulebooks; human approve creates a new draft rulepack version; deterministic YAML remains source of truth | user request; `specs/modules/rulepacks.md` | `specs/modules/rulepacks-admin.md` | done |
| TS-352 | AI assistant redesign: persistent thread history + rich markdown/Tailwind rendering with citations | user request; `specs/modules/assistant.md` | `specs/modules/assistant-ui.md` | done |
| TS-353 | Project state marketing dashboard: spec for state-machine view (draft → ingested → reviewed → baseline locked → awarded/rejected) with "what's next" actions | user request; `specs/frontend.md` | `specs/project-state-dashboard.md` | done |
| TS-354 | All-projects / workspace filter dashboard: spec for a global opportunity board with filters by workspace, jurisdiction, status, deadline | user request; `specs/frontend.md` | `specs/project-state-dashboard.md` | done |
| TS-355 | E2E test bugfixes: persist/serialize assistant `suggested_followups`, allow `.md`/`txt` upload, fix assistant live-update on first message | testing findings; `specs/modules/assistant.md` | `backend/app/modules/assistant/`, `frontend/app/assistant/`, `backend/app/core/storage.py` | done |
| TS-356 | Global left sidebar navigation replacing top navbar | user request; `specs/frontend.md` | `frontend/app/layout.tsx`, `frontend/components/` | done |
|
## Phase 29 — Round 11 production-readiness re-audit & remediation
|
| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-357 | Round 11 production-readiness re-audit: refresh `PRODUCTION_READINESS_AUDIT.md` for `9e09cac`, run validation matrix, and document new XSS / rulepack-isolation / dependency findings | `PRODUCTION_READINESS_AUDIT.md`; user request | `PRODUCTION_READINESS_AUDIT.md` | done |
| TS-358 | Markdown XSS hardening: URL scheme whitelist and `noopener` for rendered links (TS-SEC-01) | `PRODUCTION_READINESS_AUDIT.md` TS-SEC-01 | `frontend/components/markdown.tsx` | done |
| TS-359 | Auth toggle test hermeticity: explicit defaults in `test_auth_toggles.py` `_client` (TS-ENV-01) | `PRODUCTION_READINESS_AUDIT.md` TS-ENV-01 | `backend/tests/test_auth_toggles.py` | done |
| TS-360 | npm audit CVE remediation: dependency overrides and lockfile refresh (TS-DEP-01) | `PRODUCTION_READINESS_AUDIT.md` TS-DEP-01 | `frontend/package.json`, `frontend/package-lock.json` | done |
| TS-361 | Rulepack workspace isolation: scope-aware loader, admin service visibility, and route filters (TS-SEC-03) | `PRODUCTION_READINESS_AUDIT.md` TS-SEC-03 | `backend/app/modules/rulepacks/` | done |
| TS-362 | Rulepack confidence validation: sign off bundled `in-works` patterns as `validated` (TS-P02) | `PRODUCTION_READINESS_AUDIT.md` TS-P02 | `rulepacks/in-works/`, `backend/tests/test_rulepacks.py` | done |
| TS-363 | Backlog/CHANGELOG hygiene: fix `tasks/backlog.md` Phase 29 heading and add `### Next` to `CHANGELOG.md` (Devin Review follow-ups) | PR #125 Devin Review | `tasks/backlog.md`, `CHANGELOG.md` | done |
| TS-364 | Rulepack loader cache should not leak workspace DB packs across tenants (Devin Review #126) | PR #126 Devin Review | `backend/app/modules/rulepacks/loader.py` | done |
| TS-365 | Propagate rulepack loader session/workspace to ingestion/pricing/export/drafting/assistant/boq callers (Devin Review #126) | PR #126 Devin Review | `backend/app/modules/*` | done |
| TS-366 | Rulepack admin endpoints should return 403 for forbidden operations (Devin Review #126) | PR #126 Devin Review | `backend/app/modules/rulepacks/admin_service.py`, `router.py` | done |
| TS-367 | Markdown link scheme whitelist should reject URLs with embedded control characters (Devin Review #126) | PR #126 Devin Review | `frontend/components/markdown.tsx` | done |
| TS-368 | Devin Review #126 follow-up: CHANGELOG entry for post-merge fixes | PR #126 Devin Review | `CHANGELOG.md` | done |

## Phase 30 — UI/API integration gap analysis & residual fixes

| ID | Title | Req ref | Spec | Status |
|---|---|---|---|---|
| TS-369 | UI/API integration gap analysis: compare `frontend/lib/api.ts` to FastAPI routes, scan pages and raw-JSON `<pre>` renders, document in `PRODUCTION_READINESS_AUDIT.md` | user request | `PRODUCTION_READINESS_AUDIT.md` | done |
| TS-370 | Claims API path fix: add the missing `/claims` module segment to claim and draft routes in `frontend/lib/api.ts` | testing findings; integration gap | `frontend/lib/api.ts` | done |
| TS-371 | Auth export method fix: call `POST /auth/export` from `frontend/lib/api.ts exportAccount` to match backend route | testing findings; integration gap | `frontend/lib/api.ts` | done |
| TS-372 | Login mobile verification code should not be `required` when `mobileToken` is empty (mobile verification disabled) | testing findings; integration gap | `frontend/app/login/page.tsx` | done |
| TS-373 | Rulepack admin file list should return 403 for cross-workspace packs, consistent with activate/delete | testing findings; security | `backend/app/modules/rulepacks/admin_service.py` | done |
| TS-374 | Devin Review #126 residual polish: call-time loader resolution in export module, callable `loader_provider` in ingestion Celery task, `RulePackLoader.invalidate`, and markdown entity/Unicode-whitespace hardening | PR #126 Devin Review | `backend/app/modules/export/module.py`, `backend/app/modules/ingestion/tasks.py`, `backend/app/modules/rulepacks/loader.py`, `frontend/components/markdown.tsx` | done |
| TS-375 | Devin Review #129 follow-ups: login mobile verification required flag and markdown numeric entity range check | PR #129 Devin Review | `frontend/app/login/page.tsx`, `frontend/components/markdown.tsx` | in-progress |
| TS-376 | PR #128 integration: pull `claude/ui-dev-tools-setup-r3sxpg`, resolve merge conflicts with `main`, fix CI failures, and re-run checks | user request | `*` | todo |
