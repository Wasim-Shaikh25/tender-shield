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
| TS-033 | tus resumable upload + AWS Textract OCR (scanned BOQ) | Doc §4, §6.1 | `specs/modules/ingestion.md` | todo (needs AWS) |
| TS-034 | Celery + Redis: async page-streamed processing (SSE) | Doc §3.1, §3.3 | — | todo (needs Redis) |
| TS-035 | SES/Resend + MSG91 send adapters behind the notifications interface | Doc §4, §11.6 | — | todo (needs creds) |
| TS-036 | Phone OTP (MSG91) + Google OIDC login | Doc §5 | `specs/modules/auth.md` | todo (needs creds) |
| TS-037 | Stripe (GCC/UK) provider + live Razorpay keys behind the billing interface | Doc §7, §15.6 | `specs/modules/billing.md` | todo (needs creds) |

## Notes

- A task moves to `in-progress` when work starts and `done` in the commit that
  completes it, with the task ID in the commit body.
- New requirements → new `TS-###` rows here first, then a spec, then code.
- Hardening items marked `(needs …)` are logic-ready but require external
  accounts/services to complete; the interfaces they plug into are already built.
