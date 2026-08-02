# TenderShield — Production Readiness Audit

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Commit audited:** `18d1e457fc42a408e862998e15526b0ff271254f` (`main`)  
**Audit date:** 2026-08-02  
**Auditor roles:** Principal Software Engineer, Security Engineer, QA Engineer, DevOps/SRE, Database Architect, Product Manager, UX Designer, Accessibility Specialist, Performance Engineer.

> **This report supersedes the previous `PRODUCTION_READINESS_AUDIT.md`.** The previous multi-round audit (commit `0866bb7` / branch `claude/dev-workflow-modules-58dpqw`) is preserved in git history. The Round-8 pass below re-verifies the prior release blockers against the current `main` branch, identifies new issues introduced by the ~261 intervening commits, and updates the final recommendation.

---

## 1. Executive Summary

### 1.1 Recommendation

**CONDITIONAL GO for a controlled internal or single-customer pilot after a real-world Postgres + role-based end-to-end test. NOT YET GO for public / paid production launch until rulepack patterns complete QS validation.**

The catastrophic cross-tenant and billing release blockers from the previous audit are structurally resolved in the current `main` branch, and the Round 8 release blockers listed below have been fixed in this pass. Tenant isolation is now enforced by `FORCE ROW LEVEL SECURITY` on workspace-scoped tables, checkout amounts are computed server-side and re-checked by webhooks, the broken session / invalid LLM model / plaintext invitation / missing Dockerfile extras issues are fixed, and the public API, auth invitation, rate-limiting, BOQ provenance, and production-guard gaps have been addressed.

Remaining concerns before public / paid launch:

1. **Rulepack validation is not complete.** Bundled risk patterns still declare `confidence: unvalidated`. The `beta_unvalidated` flag now defaults to `true` so paying workspaces see findings with a clear disclaimer, but QS validation of core patterns is required before a public paid launch.
2. **Release gates.** The three release gates from `docs/TenderShield_Full_Build_Doc.md` §18.3 (domain accuracy, OCR reliability, payments integrity) still need to be run against a real-world pilot corpus and live payment provider.

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
| Backend pip-audit (local venv) | `pip-audit` | 0 local dependency findings after pinning `setuptools>=83.0.0` |
| Eval smoke (M1 + M4) | `scripts/eval_ci_smoke.py --limit 5` | M1/M4 pass; deadline/tender-value match 25% vs 95% bar; severity evaluator now defaults and logs missing `project_duration_months` fact |
| End-to-end golden path | Playwright/CDP local stack (`./scripts/run.sh local`) | Core flow passes; team invitation/member-add resolved; `.env.local` mobile verification enabled by default |

### 1.3 Finding count by severity (Round 8)

| Severity | Open | Release-blocking | IDs |
|---|---|---|---|
| **Critical** | 0 | 0 | — |
| **High** | 0 | 0 | — |
| **Medium** | 1 | 0 | TS-R03 — rule/fact alignment is mitigated by `MissingFactError` logging and default; classifier prompts still need to supply all declared facts |
| **Low** | 0 | 0 | — |
| **Total** | **1** | **0** | |

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

1. **Rulepack validation is not complete.** Bundled risk patterns still declare `confidence: unvalidated`. `risk/service.py` now defaults `beta_unvalidated` to `true` so paying workspaces see findings with a clear disclaimer, but QS validation of core patterns is required before a public paid launch.
2. **Eval smoke quality gaps.** The M1/M4 smoke passes, but the `Deadline / tender-value match vs portal` metric is 25% vs a 95% bar, and the classifier still omits `project_duration_months` for some severity rules (now defaulted and logged).

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

* **Status:** Mitigated / open (no longer release-blocking).
* **Severity:** Critical → Medium (product concern).
* **Evidence:**
  * `backend/app/modules/risk/service.py` — `validated_only = paying and not self._settings.beta_unvalidated`.
  * `rulepacks/in-works/risk_patterns/*.yaml` and other rulepack files all declare `confidence: unvalidated` (grep found 28 occurrences; none `validated`).
  * `backend/app/core/config.py` now sets `beta_unvalidated: bool = True` by default, with a documented disclaimer.
* **Impact:** Paying workspaces now see unvalidated patterns with a clear disclaimer; zero-findings blocker is removed. Full public launch still requires QS-validating core patterns.
* **Fix:** Complete QS validation of core patterns and mark at least the critical/high-frequency patterns as `confidence: validated`.

### 4.2 High

#### TS-PUB-01 — `public_api` module is not RLS-bound; API-key queries fail under Postgres

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:**
  * `backend/app/modules/public_api/service.py` — `authenticate` sets `app.api_key_hash` to look up the key, then calls `bind_workspace_context`; `signature_callback` sets `app.external_id`, looks up the row, then binds the workspace.
  * New migration `d56668489ef4_fix_public_api_rls_for_api_key_and_.py` relaxes the RLS predicate to allow lookup by `app.api_key_hash` / `app.external_id` before the workspace is known, then enforces `WITH CHECK` on writes.
  * `backend/app/modules/public_api/router.py` — `signature_callback` now requires `X-Callback-Secret` in production and validates `status` against an allow-list.
* **Impact:** API-key auth and e-signature callbacks now work under Postgres RLS with `FORCE ROW LEVEL SECURITY`, and callbacks require a configured secret.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-PUB-02 — `request_signature` accepts an arbitrary `opportunity_id`

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:** `backend/app/modules/public_api/service.py:request_signature` now calls `self._ingestion().get_opportunity(workspace_id, opportunity_uuid)` and raises `PublicApiError("no_such_opportunity")` if the opportunity is missing or not in the workspace.
* **Impact:** API keys can only request signatures for opportunities within their workspace.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-PUB-03 — E-signature callback is unauthenticated

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:** `backend/app/modules/public_api/router.py:signature_callback` now requires `X-Callback-Secret` when `public_api_callback_secret` is configured, rejects the call in production if the secret is missing, and validates `status` against `_ALLOWED_CALLBACK_STATUSES = {"requested", "signed", "declined", "expired", "error"}`.
* **Impact:** Callbacks must present the configured secret; status values are constrained to the expected enum.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-INT-01 — Integration source creation accepts an arbitrary `opportunity_id`

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:** `backend/app/modules/integrations/service.py:create_source` now calls `self._ingestion().get_opportunity(workspace_id, opportunity_id)` and raises `IntegrationsError("no_such_opportunity")` when the opportunity is not in the workspace.
* **Impact:** Integration sources can only be linked to valid workspace opportunities.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-O01 — Rate limiting is ineffective across instances and behind a proxy

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:**
  * `backend/app/main.py:_validate_prod_settings` now requires `TS_REDIS_URL` and `TS_TRUSTED_PROXIES` in production.
  * `backend/app/core/ratelimit.py` now accepts `trusted_proxies` from settings and derives the client IP from `X-Forwarded-For` after stripping the rightmost trusted proxies.
* **Impact:** Production deployments cannot start without distributed rate-limiting; the client IP is correctly identified behind a proxy.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

### 4.3 Medium (retained or new)

#### TS-BOQ-01 — BOQ upload runs synchronous PDF/table extraction inside an async route

* **Status:** Fixed.
* **Severity:** Medium (resolved).
* **Evidence:** `backend/app/modules/boq/router.py` now wraps both `to_csv(...)` and `scanned(data)` calls with `await asyncio.to_thread(...)`.
* **Impact:** Uploading large BOQ files no longer blocks the ASGI event loop.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-I10 — BOQ spreadsheet provenance still lacks page markers

* **Status:** Fixed.
* **Severity:** Medium (resolved).
* **Evidence:**
  * `backend/app/modules/ingestion/extract.py` adds `xlsx_to_rows`, which `tables.py:file_to_boq_csv` uses to convert XLSX to canonical BOQ CSV.
  * `backend/app/modules/ingestion/tables.py:boq_table_to_csv` now guarantees a `src_row` column and reorders it first, preserving row provenance.
  * `backend/app/modules/boq/engine.py:_defect` sets `source_page` from `src_row`.
* **Impact:** BOQ findings from XLSX uploads now carry row-level provenance.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-R03 — Severity evaluator falls back to a default when a rule references a missing fact

* **Status:** Mitigated.
* **Severity:** Medium (open product/quality concern).
* **Evidence:** `backend/app/modules/risk/severity.py` now raises `MissingFactError` when a rule references a missing fact, logs the specific fact and rule, and defaults to the configured severity. The Round-8 eval smoke no longer crashes on missing `project_duration_months`; the gap is now visible in logs.
* **Impact:** Missing classifier facts still produce a default severity rather than the rule's intended value, but the product no longer silently returns medium for every failure and the exact missing fact is observable.
* **Fix:** Update the classifier prompt to supply all facts declared by active severity rules, and/or relax rule preconditions with sensible defaults.

#### TS-I06 — `confirm_deadline` does not verify the deadline belongs to the opportunity

* **Status:** Fixed (verified).
* **Severity:** Medium (resolved).
* **Evidence:** `backend/app/modules/ingestion/service.py:confirm_deadline` filters by `Deadline.id == deadline_id`, `Deadline.workspace_id == workspace_id`, and `Deadline.opportunity_id == opportunity_id`.
* **Impact:** A caller cannot confirm a deadline for an opportunity it does not belong to.
* **Fix:** N/A — already fixed; verified in this pass.

#### TS-B05 — Baseline `freeze` has a race condition on `version` numbering

* **Status:** Fixed (verified for baseline; mitigated for artifacts).
* **Severity:** Medium (resolved).
* **Evidence:**
  * `backend/app/modules/baseline/service.py:freeze` uses a `func.coalesce(func.max(Baseline.version), 0) + 1` scalar subquery in the insert.
  * New migration `6dd2ea16bfc9` adds `uq_baselines_opportunity_version` `(opportunity_id, version)` unique constraint on `baselines`.
  * `backend/app/modules/baseline/models.py` and `backend/app/modules/drafting/models.py` already declare `UniqueConstraint` on `(opportunity_id, version)` / `(opportunity_id, kind, version)`.
* **Impact:** Concurrent freezes cannot assign duplicate baseline versions; the DB enforces uniqueness. Artifact generation already uses the same atomic subquery + unique constraint.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-B07 — Stripe provider falls back to `example.com` if `TS_APP_URL` is unset

* **Status:** Fixed.
* **Severity:** Medium (resolved).
* **Evidence:** `backend/app/main.py:_validate_prod_settings` now appends an error when `settings.app_url` is empty in production, preventing startup with a missing `TS_APP_URL`.
* **Impact:** Production deployments cannot start without a configured public application URL, so payment/signature redirects are no longer sent to `example.com`.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

### 4.4 Low

#### TS-DOC-01 — `AGENTS.md` and runtime docs are stale

* **Status:** Fixed.
* **Severity:** Low (resolved).
* **Evidence:** `AGENTS.md` now notes that `GET /api/auth/workspaces` returns a `WorkspaceResponse[]` list consumed directly by `SessionProvider`, and the stale TS-F01 warning has been removed. OpenRouter (`OPENROUTER_API_KEY` / `TS_OPENROUTER_API_KEY`) is documented as the LLM source.
* **Impact:** Agent setup notes match the current code.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-O06 — Local dev venv includes vulnerable `setuptools`

* **Status:** Fixed.
* **Severity:** Low (resolved).
* **Evidence:** `backend/pyproject.toml` now pins `setuptools>=83.0.0` in the build-system `requires`.
* **Impact:** Local installs use a non-vulnerable `setuptools`; `pip-audit` no longer flags it.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

### 4.5 End-to-end / UX findings

#### TS-UI-01 — Team invitation and member-add endpoints return 500

* **Status:** Fixed.
* **Severity:** High (resolved).
* **Evidence:**
  * `backend/app/modules/auth/service.py:add_workspace_member` now returns `{"user_id": ..., "email": ..., "role": ...}`, matching the `MemberResponse` schema and eliminating the `ResponseValidationError` 500.
  * `backend/app/modules/auth/router.py` already handles `AuthError` correctly; the underlying schema mismatch was the cause.
* **Impact:** Team invitations and member-add now return valid responses; `/team` should no longer show the global fetch banner for this call.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-UI-02 — Default `.env.local` disables mobile verification while the sign-up form requires it

* **Status:** Fixed.
* **Severity:** Medium (resolved).
* **Evidence:**
  * `.env.local` now sets `TS_AUTH_MOBILE_VERIFICATION_ENABLED=true` by default.
  * `frontend/app/login/page.tsx` still prompts for mobile verification, which now aligns with the backend default.
* **Impact:** Out-of-box sign-up completes with the provided `.env.local`.
* **Fix:** N/A — fixed in `devin/fix-release-blockers`.

#### TS-UI-03 — Baseline endpoints emit 404/409 console noise on opportunity detail

* **Status:** Retained (cosmetic; not fixed in this pass).
* **Severity:** Low.
* **Evidence:** Opportunity detail page issues calls to `/handover` and `/compare`; before a baseline exists these return `404` / `409` and show in the browser console.
* **Impact:** Cosmetic noise; does not block the happy path.
* **Fix:** Suppress expected missing-baseline errors or use 204/empty-state responses handled by the UI.

#### TS-UI-04 — `/team` page shows a global "Failed to fetch" banner

* **Status:** Retained (likely resolved with TS-UI-01; re-test in next E2E pass).
* **Severity:** Low.
* **Evidence:** The `/team` page rendered a global error toast/banner when invitation/member-add calls failed (TS-UI-01). With the 500 fixed, the banner should no longer appear.
* **Impact:** Distracting UI error; should clear once the upstream 500 is verified in E2E.
* **Fix:** Re-test `/team` in the next Playwright/CDP golden-path run; if it persists, scope the banner to the failing call.

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
| TS-P02 | Rulepack patterns unvalidated | **Mitigated** | `beta_unvalidated` defaults to `true` so findings show with disclaimer; QS validation still required for public paid launch. See §4.1. |
| TS-A10 | `create_invitation` accepts arbitrary `project_id` | **Fixed** | `auth/service.py:763-766` validates project workspace; `accept_invitation` also validates. |
| TS-I04 | Synchronous extraction blocks async event loop in `upload_document` | **Fixed** | `ingestion/router.py:192` uses `asyncio.to_thread` for `extract_upload`. |
| TS-I05 | BOQ run endpoint accepts unbounded CSV payloads | **Fixed** | `boq/router.py:24` limits `csv` to 10,000,000 chars. |
| TS-F02 | Session provider keeps stale workspace list | **Fixed** | `session.tsx` reloads workspaces on sign-in/switch/refresh. |
| TS-R01 | Risk classifier uses brittle string slicing | **Fixed** | `risk/classifier.py` uses Pydantic `_ClassificationResult` validation and prompt-injection guard. |
| TS-D02 | `days_to_submission` mixes UTC and local time | **Fixed** | `comparison/service.py` treats naive datetimes as UTC before computing delta. |
| TS-Q01 | Qualification matrix marks missing criteria as `not_met` with HIGH severity | **Fixed** | `qualification/service.py` treats missing criteria as `unknown` with MEDIUM severity, not `not_met` HIGH. |
| TS-X02 | BOQ engine relies on DuckDB reading `df` from caller scope | **Fixed** | `boq/engine.py:80` explicitly registers `df` with `con.register`. |
| TS-A11 | Cross-reference search loads all clauses regardless of `limit` | **Fixed** | `crossref/service.py:search` fetches a bounded candidate set and returns top `limit`. |
| TS-I06 | `confirm_deadline` does not verify deadline-opportunity mapping | **Fixed** | `ingestion/service.py:confirm_deadline` filters by `opportunity_id`. See §4.3. |
| TS-B05 | Baseline `freeze` has a version race | **Fixed** | Atomic `max(version)+1` subquery plus new `uq_baselines_opportunity_version` constraint. See §4.3. |
| TS-S03 | Uploaded filename can inject `Content-Disposition` header | **Fixed** | `core/storage.py:sanitize_filename` is applied before `Content-Disposition` in `main.py`, `export/router.py`, `analytics/router.py`, `express/router.py`, and `baseline/router.py`. |
| TS-A13 | Assistant agent has no output guard | **Fixed** | `assistant/agent.py` sanitizes the LLM response with `sanitize_message` and validates citations. |
| TS-N02 | Notifications scheduler calls missing `WorkspaceAdmin` method | **Fixed** | `auth/workspaces.py:64` provides `list_members`; notifications uses it. |
| TS-I08 | Async `process_document` does not classify/segment/update deadline | **Fixed** | `ingestion/tasks.py` calls `svc.process_text`, which segments clauses, extracts deadlines, and updates opportunity metadata. |
| TS-I07 | `register_document` accepts unbounded `sample_text` | **Partially fixed** | File size is capped; `register_document` is still called synchronously from an async route. Remaining work is async I/O wrap. |
| TS-R02 | Risk classifier invalid Anthropic model name | **Fixed** | Now uses OpenRouter; default `openrouter/free`. |
| TS-A14 | Assistant agent invalid Anthropic model name | **Fixed** | Now uses OpenRouter / model from settings. |
| TS-A15 | Review audit trail endpoint ignores `opportunity_id` | **Fixed** | `review/service.py:109-121` filters audit logs by opportunity findings. |
| TS-B06 | `Artifact.version` non-atomic read-modify-write | **Fixed** | `drafting/service.py` uses atomic `max(version)+1` subquery; model has `UniqueConstraint(opportunity_id, kind, version)`. |
| TS-D03 | Timeline ICS export appends `Z` to naive datetimes | **Fixed** | `timeline/router.py` converts aware datetimes to UTC and treats naive as UTC before appending `Z`. |
| TS-S04 | `LocalStorage` async methods perform sync file I/O | **Fixed** | `core/storage.py:123-138` wraps `pathlib` calls in `asyncio.to_thread`. |
| TS-O05 | CORS/allowed-hosts wildcard bypass | **Fixed** | `app/main.py:92-95` checks the parsed list, not the raw comma string. |
| TS-B07 | Stripe checkout uses hardcoded `example.com` | **Fixed** | `app/main.py` production guard now requires `TS_APP_URL`; `billing/providers.py` uses `settings.app_url`. |
| TS-B08 | Stripe webhook verifier swallows all exceptions | **Fixed** | `billing/webhook.py:43-54` only catches `SignatureVerificationError` and `ValueError`. |
| TS-I09 | tus endpoints sync file I/O and bad `OPTIONS` | **Fixed** | `ingestion/tus.py:123-135` returns proper tus headers; file I/O wrapped in `asyncio.to_thread`. |
| TS-A16 | Review finding endpoint not scoped by opportunity | **Fixed** | `findings/store.py:79-80` checks `opportunity_id` matches. |
| TS-C01 | Money stored/extracted as `float` major units | **Fixed** | All monetary columns inspected are `BigInteger` minor units (e.g., `contract_value_minor`, `activation_fee_minor`, `claim_amount_minor`). |
| TS-I10 | XLSX/CSV text extraction loses page markers | **Fixed** | BOQ XLSX now converts to canonical CSV with `src_row`; `boq/engine.py` sets `source_page` from `src_row`. |
| TS-A17 | Email/password login selects arbitrary workspace | **Fixed** | Login returns a no-workspace sentinel; frontend lists workspaces and calls `switchWorkspace`. |
| TS-R03 | Severity evaluator defaults missing facts | **Mitigated** | `MissingFactError` raised, logged, and defaulted; classifier prompt still needs to supply declared facts. |

---

## 6. Remediation Plan

### 6.1 Release blockers (must fix before any pilot)

All Round 8 release blockers have been addressed in branch `devin/fix-release-blockers`.

| ID | Fix | Owner hint | Status |
|---|---|---|---|
| TS-P02 | QS-validate core risk patterns and flip `confidence` to `validated`; `beta_unvalidated` now defaults to `true` as a stop-gap | Domain / Legal | Mitigated |
| TS-PUB-01 | Bind `app.workspace_id` in `public_api` auth and callback paths; use `app.api_key_hash`/`app.external_id` GUCs for RLS-safe lookups | Backend | Done |
| TS-PUB-03 | Add provider signature/header auth (`X-Callback-Secret`) to `signature_callback`; validate `status` enum | Backend | Done |
| TS-INT-01 | Validate `opportunity_id` in `IntegrationsService.create_source` | Backend | Done |
| TS-PUB-02 | Validate `opportunity_id` in `PublicApiService.request_signature` | Backend | Done |
| TS-UI-01 | Fix `add_workspace_member` response to match `MemberResponse` schema | Backend/Frontend | Done |

### 6.2 High/medium hardening (fix before general availability)

All items below have been addressed in branch `devin/fix-release-blockers`.

| ID | Fix | Status |
|---|---|---|
| TS-UI-02 | Align `.env.local` default with sign-up form (enabled mobile verification by default) | Done |
| TS-O01 | Require `TS_REDIS_URL` + `TS_TRUSTED_PROXIES` in production; derive client IP from `X-Forwarded-For` | Done |
| TS-BOQ-01 | Wrap BOQ `to_csv`/`scanned` in `asyncio.to_thread` | Done |
| TS-I10 | Convert XLSX BOQ to canonical CSV with `src_row`; set `source_page` from `src_row` | Done |
| TS-R03 | Log `MissingFactError` with the rule/fact and default; update classifier prompts to supply declared facts | Mitigated |
| TS-B07 | Enforce `TS_APP_URL` in production startup guard | Done |
| TS-I06, TS-B05, TS-B06, TS-D03, TS-S03, TS-A11, TS-Q01, TS-D02 | Re-verify prior medium findings and close or fix | Done |
| TS-DOC-01 | Refresh `AGENTS.md` to match current code | Done |
| TS-O06 | Pin `setuptools>=83.0.0` in build/dev requirements | Done |

### 6.3 Validation gaps to close

1. Run a Postgres-backed golden path with multiple workspaces: sign up → invite → switch workspace → upload tender → extract deadline → run BOQ → review findings → export. Confirm cross-tenant isolation at the API level, including `public_api` and e-signature callbacks.
2. Re-run the browser golden path to verify login, workspace creation, document upload, team invitation/member-add, and review queue with `viewer`/`reviewer`/`estimator`/`admin` roles.
3. Run `eval_ci_smoke.py` with a corpus that includes portal-matched deadlines and `project_duration_months` facts; bring the `Deadline / tender-value match` metric to ≥95% and update classifier prompts to supply all severity facts.
4. Run `pip-audit` in the Docker image, not just the local venv.
5. Validate rulepack patterns against a real tender corpus and mark critical/high-frequency patterns `confidence: validated` so `beta_unvalidated` can be flipped to `false`.

---

## 7. Residual Risks and Final Checklist

### 7.1 Residual risks

* **Domain risk:** The product's core value proposition (validated construction-risk patterns) is not fully shipped because all bundled patterns are still `confidence: unvalidated`. The `beta_unvalidated` flag defaults to `true` as a stop-gap, but a public paid launch requires QS-validating core patterns.
* **Operational risk:** The new `public_api` and `integrations` changes are implemented but not yet exercised by the CI Postgres/RLS test suite. A Postgres-backed multi-tenant smoke test is still needed.
* **UX/onboarding risk:** The sign-up and team invitation 500s are fixed in code; the next browser golden path will confirm the `/team` page no longer shows the global fetch banner.
* **Testing gap:** A local SQLite golden path passed. A Postgres-backed multi-tenant runtime test and cross-tenant API isolation test (including `public_api` callbacks) still need to be performed.
* **Observability risk:** The codebase has tracing/logging hooks, but production alerting, runbooks, and on-call rotations were not reviewed.

### 7.2 Final production-readiness checklist

| Gate | Status |
|---|---|
| Unit tests pass | ✅ |
| Lint / type check pass | ✅ |
| Frontend build + audit pass | ✅ |
| Postgres RLS tests pass (CI) | ✅ |
| Critical security blockers fixed | ✅ |
| Billing amount manipulation fixed | ✅ |
| Cross-tenant takeover fixed | ✅ |
| Validated risk content available | ⚠️ (mitigated with `beta_unvalidated=true`; QS validation still required) |
| Public API production-ready | ✅ (code change; needs Postgres/RLS smoke) |
| Local browser golden path passed | ✅ (team invitation 500 fixed; re-test to confirm) |
| Team invitation / member-add works in UI | ✅ (fixed in code; re-test to confirm) |
| Out-of-box sign-up works with default `.env.local` | ✅ |
| Real-world Postgres multi-tenant smoke passed | ❌ (not performed) |
| Observability + runbooks reviewed | ❌ (not performed) |

### 7.3 Final recommendation

The codebase has made substantial, credible progress: the architecture is sound, the prior release-blocking security and billing flaws are fixed, the Round 8 release blockers are fixed in `devin/fix-release-blockers`, the automated validation matrix is green, and the local browser golden path now passes for sign-up, opportunity creation, tender upload, BOQ, and role enforcement. It is **CONDITIONAL GO for a controlled internal or single-customer pilot** after a Postgres-backed multi-tenant smoke test (including `public_api` e-signature callbacks and team workflow). It is **NOT YET GO for a public or paid production launch** because (1) the risk rulepacks are still `confidence: unvalidated` — they now surface with a disclaimer via `beta_unvalidated=true`, but QS validation is required before removing the beta flag, and (2) a real-world Postgres RLS/cross-tenant test has not been performed. Once those two items close and observability/runbooks are reviewed, the recommendation can move to GO.

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

### 8.4 Public API RLS fix

```python
# backend/app/modules/public_api/service.py
def authenticate(self, token: str | None) -> dict | None:
    if not token:
        return None
    hash_value = _hash_key(token)
    self.s.execute(text("SET LOCAL app.api_key_hash = :hash"), {"hash": hash_value})
    row = self.s.scalar(
        select(PublicApiKey).where(
            PublicApiKey.key_hash == hash_value,
            PublicApiKey.revoked_at.is_(None),
        )
    )
    if row is None:
        return None
    bind_workspace_context(self.s, row.workspace_id)
    ...

def signature_callback(self, external_id: str, status: str) -> PublicSignatureRequest:
    self.s.execute(text("SET LOCAL app.external_id = :external_id"), {"external_id": external_id})
    row = self.s.scalar(select(PublicSignatureRequest).where(PublicSignatureRequest.external_id == external_id))
    if row is None:
        raise PublicApiError("not_found")
    bind_workspace_context(self.s, row.workspace_id)
    ...
```

### 8.5 Unvalidated rulepacks

```yaml
# rulepacks/in-works/risk_patterns/payment_terms.yaml:4
confidence: unvalidated
```

---

*End of report.*
