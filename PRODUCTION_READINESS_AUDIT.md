# TenderShield — Production Readiness Audit

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `18d1e457fc42a408e862998e15526b0ff271254f` (`main`)  
**Audit date:** 2026-08-02  
**Auditor roles:** Principal Software Engineer, Security Engineer, QA Engineer, DevOps/SRE, Database Architect, Product Manager, UX Designer, Accessibility Specialist, Performance Engineer.

> **This report supersedes the previous `PRODUCTION_READINESS_AUDIT.md`.** The previous multi-round audit (commit `0866bb7` / branch `claude/dev-workflow-modules-58dpqw`) is preserved in git history. The Round-8 pass below re-verifies the prior release blockers against the current `main` branch, identifies new issues introduced by the ~261 intervening commits, and updates the final recommendation.

---

## 1. Executive Summary

### 1.1 Recommendation

**NO-GO for public / paid production launch. CONDITIONAL GO for a controlled internal or single-customer pilot after fixing the remaining release blockers and running a real-world Postgres + role-based end-to-end test.**

The catastrophic cross-tenant and billing release blockers from the previous audit are structurally resolved in the current `main` branch. Tenant isolation is now enforced by `FORCE ROW LEVEL SECURITY` on workspace-scoped tables, checkout amounts are computed server-side and re-checked by webhooks, and the broken session / invalid LLM model / plaintext invitation / missing Dockerfile extras issues are all fixed.

Four release-blocking conditions remain:

1. **Product value blocker — every bundled risk rulepack is `confidence: unvalidated`.** Paying workspaces are shown only validated patterns by default, which currently means **zero risk findings**. The product cannot charge for a risk review that returns no findings unless `TS_BETA_UNVALIDATED=true`.
2. **Operational blocker — the `public_api` module is not RLS-bound and will not function under Postgres with `FORCE ROW LEVEL SECURITY` enabled.** Its routes authenticate with an API key but never set the `app.workspace_id` GUC, so queries against `public_api_keys` and `public_signature_requests` will see no rows. The e-signature callback is also unauthenticated.
3. **E2E team/workflow blocker — `POST /api/auth/invitations` and `POST /api/auth/workspaces/{id}/members` return 500 in the browser.** The golden-path test could not invite or add members; the `/team` page shows a global "Failed to fetch" banner.
4. **Out-of-box onboarding blocker — the default `.env.local` disables mobile verification (`TS_AUTH_MOBILE_VERIFICATION_ENABLED` is commented out), but the sign-up form always requires a mobile verification code.** This blocks the first local run until the flag is explicitly enabled.

Additional high/medium/low issues are detailed below.

### 1.2 Verification summary

| Check | Command / evidence | Result |
|---|---|---|
| Backend lint | `ruff check . --target-version py311` | Pass (296 files) |
| Backend type check | `mypy app` | Pass |
| Backend unit tests | `pytest -q` | **580 passed, 4 skipped** |
| Postgres RLS tests | `tests/test_rls_postgres.py` (CI) | CI job present and passing |
| Frontend lint | `npm run lint` | Pass |
| Frontend type check | `npm run typecheck` | Pass |
| Frontend production build | `npm run build` | Pass (24 routes generated) |
| Frontend npm audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Backend pip-audit (local venv) | `pip-audit` | 1 local dependency finding (`setuptools` 59.6.0; CI upgrades setuptools before audit) |
| Eval smoke (M1 + M4) | `scripts/eval_ci_smoke.py --limit 5` | M1/M4 pass; deadline/tender-value match 25% vs 95% bar; severity rule fails on missing `project_duration_months` fact |
| End-to-end golden path | Playwright/CDP local stack (`./scripts/run.sh local`) | Core flow passes; team invitation/member-add 500; `.env.local` mobile-verification default blocks sign-up unless overridden |

### 1.3 Finding count by severity (Round 8)

| Severity | Open | Release-blocking | IDs |
|---|---|---|---|
| **Critical** | 1 | 1 | TS-P02 |
| **High** | 6 | 4 | TS-PUB-01, TS-PUB-02, TS-PUB-03, TS-INT-01, TS-O01, TS-UI-01 |
| **Medium** | 7 | 0 | TS-BOQ-01, TS-I10, TS-R03, TS-B07, TS-I06*, TS-B05*, TS-UI-02 |
| **Low** | 4 | 0 | TS-DOC-01, TS-O06, TS-UI-03, TS-UI-04 |
| **Total** | **18** | **5** | |

`*` Re-verified / retained from previous rounds; see §4.3.

---

## 2. System and Audit Overview

### 2.1 Architecture

* **Backend:** FastAPI modular monolith, ~30 modules under `backend/app/modules/` (auth, billing, boq, change, claims, controltower, crossref, drafting, evidence, export, express, findings, health, ingestion, integrations, marketdata, notifications, outcomes, pricing, public_api, qualification, review, risk, rulepacks, standards, subcontract, support, timeline, analytics, assistant, baseline, comparison, advisor).
* **Frontend:** Next.js 15 + TypeScript + Tailwind. Production build emits 24 routes covering login, opportunities, billing, plan, team, settings, admin, assistant, analytics, standards, support, and help.
* **Database:** PostgreSQL with `FORCE ROW LEVEL SECURITY` workspace-isolation policies; SQLite fallback for local dev/tests.
* **CI/CD:** GitHub Actions runs backend lint/type/test/security, Postgres RLS tests, Alembic up/down, frontend lint/type/audit/build/a11y, and an eval smoke gate.

### 2.2 Scope of this round

Round 8 focused on:

1. Reproducing the prior Critical/High release blockers on `main`.
2. Checking that the security/auth/RLS fixes are complete and consistent.
3. Spot-checking modules added or heavily changed since the previous audit (`public_api`, `integrations`, `subcontract`, `controltower`, `outcomes`, `express`, `claims`, `change`, `evidence`).
4. Running the full validation matrix and eval smoke.
5. Exercising the full browser golden path through sign-up, workspace creation, opportunity creation, document upload, BOQ, and role-based access.

### 2.3 End-to-end golden-path test

A Playwright/CDP golden-path smoke test was executed against the local stack (`./scripts/run.sh local`) on the audited branch.

* **What passed:**
  * Sign-up → email/mobile verification → MFA login → workspace creation → opportunity creation.
  * Tender PDF upload processed successfully (`test_doc_ocr.pdf`, 1823 chars extracted via OCR).
  * Risk review ran and returned 0 findings as expected because no OpenRouter key was configured.
  * BOQ run returned the deterministic 10 findings (`4 defects + 5 scope gaps + blank/duplicate/grand-total` checks).
  * Workspace switch persisted across reloads; `viewer`/`reviewer`/`estimator`/`admin` role enforcement returned 403 for unauthorized actions.
* **What failed / needs attention:**
  * `POST /api/auth/invitations` returned `500`.
  * `POST /api/auth/workspaces/{id}/members` returned `500`.
  * The `/team` page showed a global "Failed to fetch" banner.
  * Out-of-the-box sign-up was blocked until `TS_AUTH_MOBILE_VERIFICATION_ENABLED=true` was set; the default `.env.local` comments this out.
  * Opportunity detail emitted baseline 404/409 console noise (`/handover`, `/compare`).

Test artifacts: screen recording at `/home/ubuntu/screencasts/tendershield-golden-20260802/tendershield-golden-20260802-edited.mp4` and `/home/ubuntu/test-report.md`.

---

## 3. Product Completeness Assessment

### 3.1 Capability matrix

| Capability | Backend module | Frontend route | Tests | Status |
|---|---|---|---|---|
| Auth / workspaces / roles | `auth` | `/login`, `/team`, `/settings` | `test_auth_module.py` | **E2E team invitation/member-add 500; mobile verification mismatch** |
| Workspace/Project RBAC | `auth` | `/team` | `test_auth_module.py` | Ready |
| Tender document ingestion | `ingestion` | `/opportunities/[id]` | `test_ingestion.py`, `test_hardening.py` | Ready |
| Risk classification | `risk` | `/opportunities/[id]` | `test_risk.py` | **Blocked by unvalidated rulepacks** |
| BOQ checks | `boq` | `/opportunities/[id]` | `test_boq.py` | Ready (minor I/O issue) |
| Review / gate | `review` | `/opportunities/[id]` | `test_review.py` | Ready |
| Change notices / events | `change` | `/opportunities/[id]` | `test_change*.py` | Ready |
| Claims / recoveries | `claims` | (none) | `test_claims.py` | Backend ready, no dedicated UI |
| Analytics dashboard | `analytics` | `/analytics` | `test_analytics.py`? | Ready (no LLM key → empty state) |
| AI-generated plan dashboard | `analytics` + `assistant` | `/plan`, `/assistant` panel | `test_analytics.py`? | Backend ready; `/plan` not in nav, depends on OpenRouter key |
| Control tower / exposure | `controltower` | (none) | `test_controltower.py` | Backend ready, no UI route |
| Subcontract flowdown | `subcontract` | (none) | `test_subcontract.py`? | Not surfaced in UI |
| Billing / subscriptions | `billing` | `/billing`, `/plan` | `test_billing.py` | Ready |
| Public API / e-signature | `public_api` | (none) | `test_public_api.py`? | **Not production-ready (RLS/auth)** |
| Integrations (OCDS/MS Project/P6) | `integrations` | (none) | `test_integrations.py`? | Backend present, UI not visible |
| Assistant | `assistant` | `/assistant` | `test_assistant.py` | Ready |
| Admin | `auth` admin routes | `/admin/*` | `test_auth_module.py` | Ready |
| Review/Export gate | `review` + `export` | n/a | `test_review.py`, `test_export.py`? | Backend wired; express lane bypasses gate with watermark |
| Pricing gate | `pricing` | n/a | `test_pricing.py`? | Backend wired |
| Baseline freeze gate | `baseline` | n/a | `test_baseline.py`? | Backend wired |
| Drafting gate | `drafting` | n/a | `test_drafting.py`? | Backend wired |

### 3.2 Product blockers

1. **Validated risk rulepacks missing.** Every rulepack under `rulepacks/in-works/` is `confidence: unvalidated`. `risk/service.py:89` sets `validated_only = paying and not self._settings.beta_unvalidated`, so paid workspaces see zero patterns. This is a product-level release blocker.
2. **Eval smoke quality gaps.** The M1/M4 smoke passes, but the `Deadline / tender-value match vs portal` metric is 25% vs a 95% bar, and a severity rule fails because `project_duration_months` is not supplied by the classifier.
3. **Team invitation and member-add endpoints return 500 in the browser.** `POST /api/auth/invitations` and `POST /api/auth/workspaces/{id}/members` both fail during the E2E team workflow; `/team` shows a global fetch-failure banner.
4. **Out-of-box onboarding is broken by the default `.env.local`.** The sign-up form requires a mobile verification code, but `TS_AUTH_MOBILE_VERIFICATION_ENABLED` is commented out by default.

### 3.3 AI-generated dashboards and gates assessment

| Capability | What exists | What's missing / risk |
|---|---|---|
| `/analytics` page | Reads `risk_summary`, `deadline_dashboard`, `boq_defect_summary` and renders count cards/distributions. | No trend/time-series; empty until findings/deadlines/BOQ runs exist. |
| AI plan dashboard (`/plan` + assistant panel) | `POST /api/analytics/plan` uses `PlanDashboardAgent` to generate KPI/table/chart/mermaid sections; snapshots save/load/export. | Not linked in main nav; requires OpenRouter key; generated content is not domain-validated. |
| Control tower / exposure | Backend endpoints `/api/controltower/exposure`, `/dashboard`, `/portfolio`, `/response-times`, `/clause-trends`, `/executive-summary`, `/payment-schedule`, `/economics`, `/customer-outcomes` all exist and are tested. | No frontend route consumes them in the current build. |
| 5 workflow gates (review → export/pricing/baseline/drafting) | `review/service.py:gate` is the single source of truth; `export`, `pricing`, `baseline`, and `drafting` (`bid_decision`) all call it before producing artifacts. | Express export intentionally bypasses the gate with a watermark; gates block any artifact when there are zero findings or pending clarifications, which may be too restrictive for early-stage opportunities. |
| 3 release gates (domain-accuracy, OCR-reliability, payments-integrity) | Domain accuracy is measured by `eval_ci_smoke.py` and per-pattern acceptance; OCR reliability is exercised on sample tenders; payments-integrity is enforced by server-side amount checks and webhook idempotency. | None have been run against a real-world pilot corpus or production payment provider, so they remain theoretical until validated with real data. |

---

## 4. Detailed Findings

### 4.1 Critical

#### TS-P02 — Rulepack patterns are still unvalidated; paying workspaces receive zero risk findings

* **Status:** Retained from previous audit.
* **Severity:** Critical (product/release blocker).
* **Evidence:**
  * `backend/app/modules/risk/service.py:87-94` — `validated_only = paying and not self._settings.beta_unvalidated`.
  * `rulepacks/in-works/risk_patterns/*.yaml` and other rulepack files all declare `confidence: unvalidated` (grep found 28 occurrences; none `validated`).
* **Impact:** With the production default `TS_BETA_UNVALIDATED=false`, paying workspaces receive no risk findings. The only way to show findings is to enable a beta disclaimer for unvalidated patterns.
* **Fix:** Complete QS validation of core patterns and mark at least the critical/high-frequency patterns as `confidence: validated`.

### 4.2 High

#### TS-PUB-01 — `public_api` module is not RLS-bound; API-key queries fail under Postgres

* **Status:** New in Round 8.
* **Severity:** High.
* **Evidence:**
  * `backend/app/modules/public_api/router.py:52-67` — `_api_principal` decodes the key but does not call `bind_workspace_context`.
  * `backend/app/modules/public_api/router.py:134-151` and `154-165` — `signature_status` and `signature_callback` use `get_session` with no workspace binding.
  * `backend/migrations/versions/6cce3c3fb917_add_public_api_tables.py:104-105` — `public_api_keys` and `public_signature_requests` are RLS-enabled.
* **Impact:** Under Postgres with `FORCE ROW LEVEL SECURITY`, the `workspace_isolation` policy evaluates `workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid`. With no GUC set this is NULL, so `SELECT` on `public_api_keys` returns no rows and API-key authentication fails. The e-signature feature is non-functional in production.
* **Fix:** Bind the workspace GUC in `_api_principal` immediately after resolving the key; bind the workspace (or a sentinel) in `signature_callback` using the `external_id` lookup, or exempt callback reads from RLS by validating `external_id` as a secret and querying with a privileged helper.

#### TS-PUB-02 — `request_signature` accepts an arbitrary `opportunity_id`

* **Status:** New in Round 8.
* **Severity:** High.
* **Evidence:** `backend/app/modules/public_api/service.py:90-123` creates a `PublicSignatureRequest` with the supplied `opportunity_id` without verifying the opportunity belongs to the API key's workspace.
* **Impact:** An API key holder can create signature requests referencing any opportunity UUID, leading to orphaned/incorrect records and potential downstream confusion.
* **Fix:** Verify `opportunity_id` exists in the workspace (e.g., via ingestion service) before creating the row.

#### TS-PUB-03 — E-signature callback is unauthenticated

* **Status:** New in Round 8.
* **Severity:** High.
* **Evidence:** `backend/app/modules/public_api/router.py:154-165` and `service.py:125-138` — `signature_callback` accepts `external_id` and `status` with no signature/header check.
* **Impact:** Anyone who knows or guesses an `external_id` can set a signature request to `signed`. `external_id` is a 16-byte token URL (e.g., 22 chars) and is returned to counterparties, so it is not a strong secret.
* **Fix:** Add HMAC/signature verification for the configured provider, or at minimum require a provider-secret header and validate `status` against an allowed enum.

#### TS-INT-01 — Integration source creation accepts an arbitrary `opportunity_id`

* **Status:** New in Round 8.
* **Severity:** High.
* **Evidence:** `backend/app/modules/integrations/service.py:67-69` creates `IntegrationSource` with `opportunity_id` taken from the body and never validates it against `workspace_id`.
* **Impact:** An admin can link an integration source to an opportunity outside the workspace. The row will still carry the caller's workspace, but the `opportunity_id` is invalid.
* **Fix:** Validate `opportunity_id` belongs to the workspace before insert.

#### TS-O01 — Rate limiting is ineffective across instances and behind a proxy

* **Status:** Retained from previous audit.
* **Severity:** High.
* **Evidence:** `backend/app/core/ratelimit.py` (and related `RateLimitDep`) uses an in-memory `MemoryStorage` when `TS_REDIS_URL` is unset.
* **Impact:** Without Redis, rate limits are per-process and are reset on every deploy/restart; they do not protect horizontally scaled deployments.
* **Fix:** Ensure `TS_REDIS_URL` is required in production and that the rate-limit key is derived from `X-Forwarded-For` / `X-Real-IP` when behind a proxy.

### 4.3 Medium (retained or new)

#### TS-BOQ-01 — BOQ upload runs synchronous PDF/table extraction inside an async route

* **Status:** New in Round 8.
* **Severity:** Medium.
* **Evidence:** `backend/app/modules/boq/router.py:87` and `90-93` call `to_csv(file.filename, data)` and `scanned(data)` directly from `async def upload_boq` without `asyncio.to_thread`. `file_to_boq_csv` uses `pdfplumber`/`openpyxl` and `scanned_boq_csv` runs table OCR.
* **Impact:** A large BOQ PDF blocks the ASGI event loop for all other requests on the same worker.
* **Fix:** Wrap both calls in `asyncio.to_thread`.

#### TS-I10 — BOQ spreadsheet provenance still lacks page markers

* **Status:** Partially fixed / retained.
* **Severity:** Medium.
* **Evidence:**
  * Fixed for document XLSX/CSV extraction: `backend/app/modules/ingestion/extract.py:74-96` emits `[sheet:...]` and `[pN]` markers.
  * Not fixed for BOQ path: `backend/app/modules/ingestion/tables.py:113-127` `xlsx_to_csv` returns a plain CSV with no `[pN]` markers, so BOQ findings from XLSX uploads lose row/page provenance.
* **Fix:** Emit `[pN]` markers in `xlsx_to_csv` or use the same extraction path as document ingestion.

#### TS-R03 — Severity evaluator falls back to a default when a rule references a missing fact

* **Status:** Partially fixed / retained.
* **Severity:** Medium.
* **Evidence:** `backend/app/modules/risk/severity.py:53-63` now raises `NameError` on missing facts but catches all exceptions and returns `default="medium"`. The Round-8 eval smoke repeatedly logged `NameError: missing severity fact: project_duration_months` for a rule that requires it.
* **Impact:** Findings whose classifier didn't supply every fact used by the rule get an inaccurate `medium` severity instead of the rule's intended value.
* **Fix:** Ensure the classifier prompt returns all facts declared by a rule, or relax the rule's preconditions so missing facts map to a sensible branch.

#### TS-I06 — `confirm_deadline` does not verify the deadline belongs to the opportunity

* **Status:** Not re-verified in Round 8; assumed retained.
* **Severity:** Medium.
* **Evidence:** Not explicitly inspected in this round; previous audit reported it and no related code changes were observed.
* **Fix:** Re-verify and add an `opportunity_id` filter to the deadline update query.

#### TS-B05 — Baseline `freeze` has a race condition on `version` numbering

* **Status:** Not re-verified in Round 8; assumed retained.
* **Severity:** Medium.
* **Evidence:** Not explicitly inspected in this round; previous audit reported a non-atomic read-modify-write on `Artifact.version`.
* **Fix:** Re-verify and use an optimistic-locking version counter or a DB-level `max(version)+1` atomic insert.

#### TS-B07 — Stripe provider falls back to `example.com` if `TS_APP_URL` is unset

* **Status:** Partially fixed / retained.
* **Severity:** Medium.
* **Evidence:** `backend/app/modules/billing/providers.py:101` — `base_url = (self.settings.app_url or "https://example.com").rstrip("/")`. Production startup guard does not require `app_url`.
* **Impact:** A misconfigured production deployment sends successful payers to a non-existent domain.
* **Fix:** Add `TS_APP_URL` to `_validate_prod_settings` and make it required in production.

### 4.4 Low

#### TS-DOC-01 — `AGENTS.md` and runtime docs are stale

* **Status:** New in Round 8.
* **Severity:** Low.
* **Evidence:** `AGENTS.md` still documents a "Known UI bug (TS-F01)" for `/api/auth/workspaces` and references `ANTHROPIC_API_KEY` (with no `TS_` prefix), while the code now uses OpenRouter and `Workspace` types are generated from the backend OpenAPI spec.
* **Impact:** New agents booting the project may follow outdated setup instructions.
* **Fix:** Update `AGENTS.md` to reflect current auth/session/API setup.

#### TS-O06 — Local dev venv includes vulnerable `setuptools`

* **Status:** New in Round 8.
* **Severity:** Low.
* **Evidence:** `pip-audit` flagged `setuptools` 59.6.0 (PYSEC-2022-43012, PYSEC-2025-49, PYSEC-2026-1918, PYSEC-2026-3447). CI upgrades setuptools before its own audit; the production Dockerfile uses `python:3.12-slim`, which ships a newer setuptools.
* **Impact:** Local/development installs only; not a production runtime blocker if CI and Docker base images are current.
* **Fix:** Pin a minimum `setuptools>=83.0.0` in `pyproject.toml` build-system requirements or the dev install step.

### 4.5 End-to-end / UX findings

#### TS-UI-01 — Team invitation and member-add endpoints return 500

* **Status:** New in Round 8 (E2E golden path).
* **Severity:** High (release blocker).
* **Evidence:**
  * Playwright/CDP test: `POST /api/auth/invitations` → `500 Internal Server Error`.
  * Playwright/CDP test: `POST /api/auth/workspaces/{id}/members` → `500 Internal Server Error`.
  * `/team` page displays a global "Failed to fetch" banner that correlates with these calls.
  * `backend/app/modules/auth/router.py:855-871` and `1022-1036` wrap `add_workspace_member` and `create_invitation` in `_handle`, which only catches `AuthError`; any other exception propagates as 500.
* **Impact:** Collaborators cannot be invited or added to a workspace; the team management feature is non-functional in the UI.
* **Fix:** Reproduce and capture the server traceback, then guard the affected service calls and/or add explicit validation to convert expected error conditions into `AuthError` (or add a catch-all logger that still returns a safe 400/500 with an error code).

#### TS-UI-02 — Default `.env.local` disables mobile verification while the sign-up form requires it

* **Status:** New in Round 8 (E2E golden path).
* **Severity:** Medium.
* **Evidence:**
  * `frontend/app/login/page.tsx` always prompts for a mobile verification code during sign-up.
  * `.env.local` comments out `TS_AUTH_MOBILE_VERIFICATION_ENABLED`, so the backend does not send a mobile OTP and the user cannot complete sign-up.
* **Impact:** A new developer or evaluator cannot complete sign-up without reading the code and manually enabling the flag.
* **Fix:** Either enable mobile verification by default in `.env.local` or make the sign-up form conditional on `settings.auth_mobile_verification_enabled`.

#### TS-UI-03 — Baseline endpoints emit 404/409 console noise on opportunity detail

* **Status:** New in Round 8 (E2E golden path).
* **Severity:** Low.
* **Evidence:** Opportunity detail page issues calls to `/handover` and `/compare`; before a baseline exists these return `404` / `409` and show in the browser console.
* **Impact:** Cosmetic noise and may confuse users; does not block the happy path.
* **Fix:** Suppress expected missing-baseline errors or use 204/empty-state responses handled by the UI.

#### TS-UI-04 — `/team` page shows a global "Failed to fetch" banner

* **Status:** New in Round 8 (E2E golden path).
* **Severity:** Low.
* **Evidence:** The `/team` page renders a global error toast/banner even when workspace member list loads successfully; this correlates with the invitation 500 in TS-UI-01.
* **Impact:** Distracting UI error; combined with TS-UI-01 it makes the team feature appear broken.
* **Fix:** Scope the error banner to the failing call (invitations only) and avoid global banners for partial endpoint failures.

---

## 5. Historical Finding Status (prior audit → Round 8)

| ID | Title | Round-8 status | Notes |
|---|---|---|---|
| TS-A01 | Any authenticated user can join any workspace as owner | **Fixed** | Member-add route and invitation flows now validate workspace membership and project ownership. |
| TS-A02 | Google sign-in grants `owner` to every user | **Fixed** | Google/Apple OIDC routes removed. |
| TS-A03 | Row-Level Security structurally inoperative | **Fixed** | Migrations now `ENABLE` + `FORCE ROW LEVEL SECURITY`; `auth/deps.py:34` binds `app.workspace_id`; CI runs `test_rls_postgres.py`. |
| TS-B01 | Client controls payment amount; webhook activates without validation | **Fixed** | `billing/router.py` computes expected amount server-side; `billing/service.py` validates amounts in both Razorpay and Stripe handlers. |
| TS-A04 | Workspace/project member lists readable cross-tenant | **Fixed** | `auth/service.py:499-503` checks caller membership before listing. |
| TS-A05 | Google sign-in with existing email raises 500 | **Fixed** | Google sign-in removed. |
| TS-I01 | Uploads fully buffered before size check | **Fixed** | `ingestion/router.py:148-151` reads `max_size + 1` and rejects oversized uploads. |
| TS-I02 | SSE progress endpoint busy-spins | **Fixed** | `ingestion/router.py:246` sleeps 0.5s per iteration with a 600s timeout. |
| TS-B02 | Webhook processing not atomic; idempotency racy | **Fixed** | `WebhookEvent` has `uq_webhook_provider_event_id`; `_claim_event_id` uses a savepoint. |
| TS-F01 | Frontend/backend contract mismatch breaks session | **Fixed** | `frontend/components/session.tsx` loads workspaces and `api.ts` uses generated `WorkspaceResponse` types. `AGENTS.md` is stale. |
| TS-O01 | Rate limiting ineffective across instances | **Retained** | See §4.2 TS-O01. |
| TS-A06 | `switch_workspace` does not persist rotated refresh token | **Fixed** | `auth/service.py:1031+` commits rotated tokens. |
| TS-A07 | `POST /api/auth/resend-verification` returns raw token | **Fixed** | Endpoint removed; verification flow uses hashed tokens. |
| TS-O04 | Backend Dockerfile omits required extras | **Fixed** | `backend/Dockerfile:10` installs storage, redis, celery, billing, scheduler, ocr, auth extras. |
| TS-A08 | Invitation tokens stored in plaintext | **Fixed** | `auth/service.py:769` stores `token_hash`; only the plaintext URL token is returned once to the inviter. |
| TS-A09 | TOTP enrollment does not require verification code | **Fixed** | `auth/service.py:964-970` verifies pending TOTP secret before activating. |
| TS-P02 | Rulepack patterns unvalidated | **Retained Critical** | See §4.1. |
| TS-A10 | `create_invitation` accepts arbitrary `project_id` | **Fixed** | `auth/service.py:763-766` validates project workspace; `accept_invitation` also validates. |
| TS-I04 | Synchronous extraction blocks async event loop in `upload_document` | **Fixed** | `ingestion/router.py:192` uses `asyncio.to_thread` for `extract_upload`. |
| TS-I05 | BOQ run endpoint accepts unbounded CSV payloads | **Fixed** | `boq/router.py:24` limits `csv` to 10,000,000 chars. |
| TS-F02 | Session provider keeps stale workspace list | **Fixed** | `session.tsx` reloads workspaces on sign-in/switch/refresh. |
| TS-R01 | Risk classifier uses brittle string slicing | **Fixed** | `risk/classifier.py` uses Pydantic `_ClassificationResult` validation and prompt-injection guard. |
| TS-D02 | `days_to_submission` mixes UTC and local time | **Not re-verified** | Not inspected this round; retain until tested. |
| TS-Q01 | Qualification matrix marks missing criteria as `not_met` with HIGH severity | **Not re-verified** | Not inspected this round; retain until tested. |
| TS-X02 | BOQ engine relies on DuckDB reading `df` from caller scope | **Fixed** | `boq/engine.py:80` explicitly registers `df` with `con.register`. |
| TS-A11 | Cross-reference search loads all clauses regardless of `limit` | **Not re-verified** | Not inspected this round. |
| TS-I06 | `confirm_deadline` does not verify deadline-opportunity mapping | **Retained** | See §4.3. |
| TS-B05 | Baseline `freeze` has a version race | **Retained** | See §4.3. |
| TS-S03 | Uploaded filename can inject `Content-Disposition` header | **Not re-verified** | Not inspected this round. |
| TS-A13 | Assistant agent has no output guard | **Not re-verified** | Not inspected this round. |
| TS-N02 | Notifications scheduler calls missing `WorkspaceAdmin` method | **Fixed** | `auth/workspaces.py:64` provides `list_members`; notifications uses it. |
| TS-I08 | Async `process_document` does not classify/segment/update deadline | **Fixed** | `ingestion/tasks.py` calls `svc.process_text`, which segments clauses, extracts deadlines, and updates opportunity metadata. |
| TS-I07 | `register_document` accepts unbounded `sample_text` | **Partially fixed** | File size is capped, but `register_document` is still called synchronously from an async route and processes the full extracted text. |
| TS-R02 | Risk classifier invalid Anthropic model name | **Fixed** | Now uses OpenRouter; default `openrouter/free`. |
| TS-A14 | Assistant agent invalid Anthropic model name | **Fixed** | Now uses OpenRouter / model from settings. |
| TS-A15 | Review audit trail endpoint ignores `opportunity_id` | **Fixed** | `review/service.py:109-121` filters audit logs by opportunity findings. |
| TS-B06 | `Artifact.version` non-atomic read-modify-write | **Not re-verified** | Not inspected this round. |
| TS-D03 | Timeline ICS export appends `Z` to naive datetimes | **Not re-verified** | Not inspected this round. |
| TS-S04 | `LocalStorage` async methods perform sync file I/O | **Fixed** | `core/storage.py:123-138` wraps `pathlib` calls in `asyncio.to_thread`. |
| TS-O05 | CORS/allowed-hosts wildcard bypass | **Fixed** | `app/main.py:92-95` checks the parsed list, not the raw comma string. |
| TS-B07 | Stripe checkout uses hardcoded `example.com` | **Partially fixed** | `billing/providers.py:101` uses `settings.app_url` with `example.com` fallback; production guard does not enforce `app_url`. |
| TS-B08 | Stripe webhook verifier swallows all exceptions | **Fixed** | `billing/webhook.py:43-54` only catches `SignatureVerificationError` and `ValueError`. |
| TS-I09 | tus endpoints sync file I/O and bad `OPTIONS` | **Fixed** | `ingestion/tus.py:123-135` returns proper tus headers; file I/O wrapped in `asyncio.to_thread`. |
| TS-A16 | Review finding endpoint not scoped by opportunity | **Fixed** | `findings/store.py:79-80` checks `opportunity_id` matches. |
| TS-C01 | Money stored/extracted as `float` major units | **Fixed** | All monetary columns inspected are `BigInteger` minor units (e.g., `contract_value_minor`, `activation_fee_minor`, `claim_amount_minor`). |
| TS-I10 | XLSX/CSV text extraction loses page markers | **Partially fixed** | Document XLSX/CSV now emit markers; BOQ `xlsx_to_csv` does not. |
| TS-A17 | Email/password login selects arbitrary workspace | **Fixed** | Login returns a no-workspace sentinel; frontend lists workspaces and calls `switchWorkspace`. |
| TS-R03 | Severity evaluator defaults missing facts to `0` | **Partially fixed** | No longer defaults to `0`, but still falls back to `medium` when facts are missing. |

---

## 6. Remediation Plan

### 6.1 Release blockers (must fix before any pilot)

| ID | Fix | Owner hint |
|---|---|---|
| TS-P02 | QS-validate core risk patterns and flip `confidence` to `validated` | Domain / Legal |
| TS-PUB-01 | Bind `app.workspace_id` in `public_api` auth and callback paths; add tests under Postgres RLS | Backend |
| TS-PUB-03 | Add provider signature/header auth to `signature_callback`; validate `status` enum | Backend |
| TS-INT-01 | Validate `opportunity_id` in `IntegrationsService.create_source` | Backend |
| TS-PUB-02 | Validate `opportunity_id` in `PublicApiService.request_signature` | Backend |
| TS-UI-01 | Reproduce and fix 500 on invitation and workspace-member-add endpoints; add error handling so only valid client errors surface | Backend/Frontend |

### 6.2 High/medium hardening (fix before general availability)

| ID | Fix |
|---|---|
| TS-UI-02 | Align `.env.local` default with sign-up form (enable mobile verification by default or make the form conditional) |
| TS-O01 | Require Redis + proxy-aware client IP for production rate limiting |
| TS-BOQ-01 | Wrap BOQ `to_csv`/`scanned` in `asyncio.to_thread` |
| TS-I10 | Emit `[pN]` markers from `xlsx_to_csv` |
| TS-R03 | Align classifier facts with severity rule expectations |
| TS-B07 | Enforce `TS_APP_URL` in production startup guard |
| TS-I06, TS-B05, TS-B06, TS-D03, TS-S03, TS-A11, TS-Q01, TS-D02 | Re-verify prior medium findings and close or fix |
| TS-DOC-01 | Refresh `AGENTS.md` to match current code |
| TS-O06 | Pin `setuptools>=83.0.0` in build/dev requirements |

### 6.3 Validation gaps to close

1. Run a Postgres-backed golden path with multiple workspaces: sign up → invite → switch workspace → upload tender → extract deadline → run BOQ → review findings → export. Confirm cross-tenant isolation at the API level. (SQLite golden path done; Postgres multi-tenant run still pending.)
2. Re-run the browser golden path after fixing TS-UI-01/TS-UI-02 to verify login, workspace creation, document upload, and review queue with `viewer`/`reviewer`/`estimator`/`admin` roles.
3. Run `eval_ci_smoke.py` with a corpus that includes portal-matched deadlines and `project_duration_months` facts; bring the `Deadline / tender-value match` metric to ≥95%.
4. Run `pip-audit` in the Docker image, not just the local venv.

---

## 7. Residual Risks and Final Checklist

### 7.1 Residual risks

* **Domain risk:** The product's core value proposition (validated construction-risk patterns) is currently unshipped because no patterns are validated. This is the single biggest business risk.
* **Operational risk:** Several new modules (`public_api`, `integrations`) were added but are not yet exercised by the CI Postgres/RLS test suite. They may fail silently in production.
* **UX/onboarding risk:** The first-run sign-up experience is blocked by a mismatch between the default `.env.local` and the UI, and the team-management workflow crashes. These were found through an end-to-end browser test, which is positive, but they must be fixed before any pilot.
* **Testing gap:** A local SQLite golden path passed, but a Postgres-backed multi-tenant runtime test and cross-tenant API isolation still need to be performed.
* **Observability risk:** The codebase has tracing/logging hooks, but production alerting, runbooks, and on-call rotations were not reviewed.

### 7.2 Final production-readiness checklist

| Gate | Status |
|---|---|
| Unit tests pass | ✅ |
| Lint / type check pass | ✅ |
| Frontend build + audit pass | ✅ |
| Postgres RLS tests pass (CI) | ✅ |
| Critical security blockers fixed | ✅ (except `public_api` RLS) |
| Billing amount manipulation fixed | ✅ |
| Cross-tenant takeover fixed | ✅ |
| Validated risk content available | ❌ |
| Public API production-ready | ❌ |
| Local browser golden path passed | ✅ (team feature blocked by TS-UI-01) |
| Team invitation / member-add works in UI | ❌ (TS-UI-01) |
| Out-of-box sign-up works with default `.env.local` | ❌ (TS-UI-02) |
| Real-world Postgres multi-tenant smoke passed | ❌ (not performed) |
| Observability + runbooks reviewed | ❌ (not performed) |

### 7.3 Final recommendation

The codebase has made substantial, credible progress: the architecture is sound, the prior release-blocking security and billing flaws are fixed, the automated validation matrix is green, and a local browser golden path now passes for sign-up, opportunity creation, tender upload, BOQ, and role enforcement. It is **not ready for a public or paid production launch** because (1) the risk rulepacks are all unvalidated, (2) the `public_api` / e-signature feature is not RLS-aware and would break in a Postgres deployment, (3) team invitation and member-add endpoints return 500 in the browser, and (4) the default `.env.local` blocks out-of-box sign-up due to a mobile-verification mismatch. It **could support a controlled single-customer or internal pilot** once the release blockers above are resolved and a Postgres-backed multi-tenant smoke test is completed.

---

## 8. Appendix — Evidence snapshots

### 8.1 RLS migration pattern

```python
# backend/migrations/versions/d5e0f7a14b60_evidence_and_project_billing.py:18-27
def _enable_rls(table: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY workspace_isolation ON {table} "
        "USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) "
        "WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)"
    )
```

### 8.2 Billing amount validation

```python
# backend/app/modules/billing/router.py:147-154
def _create_checkout(...):
    if body.amount_minor is not None and body.amount_minor != amount:
        raise HTTPException(400, "amount_mismatch")
```

### 8.3 Webhook idempotency

```python
# backend/app/modules/billing/service.py:833-853
def _claim_event_id(self, event_id: str, provider: str, user_id=None) -> bool:
    if not event_id:
        return True
    try:
        with self.s.begin_nested():
            self.s.add(WebhookEvent(...))
            self.s.flush()
    except IntegrityError:
        return False
    return True
```

### 8.4 Public API RLS gap

```python
# backend/app/modules/public_api/router.py:52-67
def _api_principal(request: Request, session: Session = Depends(get_session), authorization: str = Header(None)):
    token = None
    if authorization:
        parts = authorization.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower() == "apikey":
            token = parts[1].strip()
    if not token:
        raise HTTPException(401, "api_key_required")
    principal = _service(request, session).authenticate(token)
    # No bind_workspace_context(...) call
```

### 8.5 Unvalidated rulepacks

```yaml
# rulepacks/in-works/risk_patterns/payment_terms.yaml:4
confidence: unvalidated
```

---

*End of report.*
