# Production Readiness Audit — TenderShield

> Audit scope: `Wasim-Shaikh25/tender-shield` repository root (`/home/ubuntu/repos/tender-shield`).
> Audit performed: 2026-07-29.
> Source-of-truth reviewed: `docs/TenderShield_Full_Build_Doc.md`, `CLAUDE.md`, `.cursor/rules/*.mdc`, `.devin/rules/*.mdc`, `tasks/backlog.md`, `tasks/spec_audit_tracker.md`, `CHANGELOG.md`.
> Evidence-first: no code was modified. All commands were run in a local Python 3.11.11 virtualenv and Node 22 environment.

---

## 1. Executive Summary

### 1.1 Readiness assessment

**CONDITIONAL GO for controlled internal / staging use. NO-GO for a public production launch.**

The backend is a well-structured FastAPI modular monolith with strong architectural discipline (pluggable modules, registry capabilities, event bus, per-module migrations, RLS helpers). The frontend is a small Next.js 15 SPA that covers a subset of the bid-review workbench. Automated checks pass (`ruff`, `tsc --noEmit`, `pytest`, `next build`).

However, multiple **Critical** and **High** findings block production release:

- A default Razorpay webhook secret would allow forged billing events.
- CORS is wildcard by default.
- The access token is persisted in `localStorage` with no refresh rotation.
- MFA is enroll-only and not enforced at login.
- Risk patterns are all `confidence: unvalidated` and the engine does not filter them for paying users.
- File upload has no content/MIME/virus validation and runs synchronously in-request up to 2 GB.
- Real notifications, email/SMS delivery, S3 storage, and live payment-provider order creation are not wired.
- Several environment/deployment artefacts referenced in docs are missing.

The product is best treated as a **feature-complete Phase-1/1.5 backend + partial frontend** that needs hardening and integrations before any production tenant or revenue data is trusted to it.

### 1.2 Finding count by severity

| Severity | Count |
|---|---:|
| Critical | 1 |
| High | 14 |
| Medium | 8 |
| Low | 2 |

### 1.3 Major technical and product risks

1. **Billing forgery** — `TS_RAZORPAY_WEBHOOK_SECRET` defaults to a hardcoded string (`dev-razorpay-secret`). If this is not overridden, an attacker can forge `subscription.activated` / `order.paid` events and upgrade any workspace or create invoices.
2. **Cross-tenant / session compromise** — wildcard CORS + bearer tokens in `localStorage` + no refresh rotation + no rate limits create a realistic path to token exfiltration and replay.
3. **Professional-liability exposure** — unvalidated rule-pack patterns are surfaced to users without the documented Phase-1 QS sign-off; generated artifacts could mis-state contractual risk.
4. **Operational gaps** — no real notifications, no async job queue, no staging/prod env files, no S3 adapter, and no live payment order creation.
5. **Frontend incompleteness** — billing, plan upgrade, admin, password-reset UI, and multi-workspace switching are missing or minimal.

### 1.4 Scope limitations

- No live Razorpay/Stripe/Apple/Google/SMS/email credentials were available; only the interfaces and default/dev paths could be reviewed.
- No production deployment, CDN, WAF, or load balancer configuration was accessible.
- Accessibility was inspected manually; no automated axe/Lighthouse/screen-reader run was performed.
- Postgres RLS was evaluated by reading migrations and `bind_workspace_context`; no dedicated integration test against a live Postgres instance was run.
- OCR/RapidTable could not be executed in the sandbox because the ONNX models are downloaded on first use.

### 1.5 Release conditions

Before any production release the following must be true at minimum:

1. Replace default `TS_RAZORPAY_WEBHOOK_SECRET` and every other default secret; enforce secret presence in prod.
2. Restrict CORS to known origins; add security headers (HSTS, CSP, X-Frame-Options); add rate limiting.
3. Move refresh token to `httpOnly` cookie, keep access token in memory, implement token refresh, and revoke server-side on logout.
4. Enforce MFA at login for privileged roles and wire real email/SMS delivery.
5. Filter `risk` patterns by `validated_only=True` for non-internal users; complete the Phase-1 accuracy gate and QS sign-off.
6. Add content/MIME/file-size validation, virus scanning, and async processing for uploads.
7. Provide S3/SES/MSG91/Razorpay/Stripe adapters and real env files.
8. Add an admin console, billing/plan UI, multi-workspace switcher, and remove hardcoded demo data from production pages.
9. Resolve high-severity npm dependencies and add `mypy`, ESLint, dependency-audit, and E2E tests to CI.

---

## 2. System and Audit Overview

### 2.1 Architecture and critical flows

- **Backend**: FastAPI 0.115+, Python 3.11+, SQLAlchemy 2, Pydantic v2, Alembic.
- **Frontend**: Next.js 15.5.21, React 19, TypeScript 5.7.3, Tailwind CSS 3.4.17.
- **Database**: PostgreSQL 16 in Docker compose; SQLite used for tests/CI.
- **Architecture**: pluggable modules under `backend/app/modules/<name>/`, each exposing `module: ModuleSpec` in `module.py`. Cross-module calls go through `app.core.registry` and `app.core.events`. Shared contracts live in `app/core/contracts/`.
- **Tenant isolation**: `WorkspaceScopedMixin` adds `workspace_id` and registers tables for PostgreSQL RLS; `bind_workspace_context` sets `app.workspace_id` per request.
- **Auth**: Argon2id password hashing, ephemeral RS256 JWT keypair if keys are not configured, rotating refresh tokens with reuse detection, TOTP MFA primitives.
- **Billing**: free/paygo/pro/scale plans, usage metering, Razorpay webhook HMAC verification, invoice creation.
- **File/text pipeline**: pypdf/pdfplumber/openpyxl/CSV extraction → clause segmentation → deterministic deadline extraction → risk pattern engine (LLM optional) → BOQ deterministic checks (DuckDB) → review queue → artifact generation (clarification, assumptions, bid decision) → export (DOCX/XLSX/PDF) or baseline freeze.

### 2.2 Roles, trust boundaries, and integrations

| Role | Trust boundary |
|---|---|
| `viewer` | Read-only inside a workspace |
| `reviewer` | Can accept/edit/reject findings, freeze baselines |
| `estimator` | Can run risk/BOQ, generate artifacts, export packs |
| `admin` / `owner` | Workspace/project/member management, billing checkout, org standards |
| `superadmin` | Cross-workspace user/workspace admin endpoints |
| Anonymous | Signup, login, forgot/reset password, public health, Razorpay webhook |

Third-party integrations required but not fully wired: Razorpay (webhook skeleton present), Stripe (todo), Apple Sign-In (skeleton), Google OIDC (todo), MSG91/SMS (todo), SES/Resend (todo), S3 (todo).

### 2.3 Files, routes, APIs, and workflows reviewed

- 20 backend modules discovered (excluding `_broken` underscore-prefixed fixture).
- 82 API routes extracted from `backend/app/modules/*/router.py` files under `/api/<module>`.
- 10 static/dynamic frontend routes from `next build`:
  `/`, `/forgot-password`, `/help`, `/login`, `/opportunities`, `/opportunities/[id]`, `/reset-password`, `/standards`.
- Workflows reviewed end-to-end: signup → workspace → opportunity → document upload → risk/BOQ → review → artifact generation → export/baseline freeze.

### 2.4 Commands and tests executed

| Check | Command | Result |
|---|---|---|
| Backend lint | `cd backend && ../.venv/bin/ruff check . --target-version py311` | `All checks passed!` |
| Frontend typecheck | `cd frontend && npx tsc --noEmit` | clean (exit 0) |
| Backend tests | `cd backend && ../.venv/bin/pytest -q` | 144 passed, 1 skipped, 1 warning in 20.21s |
| Frontend build | `cd frontend && npm run build` | success, 10 pages |
| Frontend dependency audit | `cd frontend && npm audit --audit-level=moderate` | 3 high severity vulnerabilities (`postcss`, `sharp` via `next`) |
| Frontend lint | `cd frontend && npm run lint` | `next lint` is deprecated and prompts for ESLint config; no config exists |
| Architecture test | `backend/tests/test_architecture.py` | passed: no cross-module import violations |

### 2.5 Assumptions, exclusions, and untested areas

- Assumed the PostgreSQL migration `migrations/versions/e26e85245237_workspace_tenant.py` correctly enables RLS on all `WorkspaceScopedMixin` tables.
- Assumed `ANTHROPIC_API_KEY` and payment-provider credentials are intentionally absent and will be injected at deploy time.
- Did not review live infrastructure (AWS/GCP accounts, DNS, WAF, TLS certs, backup jobs, log shipping).
- Did not run the throwaway `scripts/phase0_accuracy_test.py` because `anthropic` is not installed and no API key was present.
- Did not evaluate model output quality or legal accuracy; this audit is about code, configuration, and workflow completeness.

---

## 3. Product Completeness

### 3.1 Role-to-Capability Matrix

| Capability | Anonymous | Viewer | Reviewer | Estimator | Admin/Owner | Superadmin |
|---|---|---|---|---|---|---|
| Sign up / log in / forgot password | Implemented | — | — | — | — | — |
| View opportunity board | — | Implemented | Implemented | Implemented | Implemented | — |
| Create opportunity | — | — | — | Implemented | Implemented | — |
| Upload tender documents | — | — | — | Implemented | Implemented | — |
| View deadlines / timeline / ICS | — | Implemented | Implemented | Implemented | Implemented | — |
| Run risk analysis | — | — | — | Implemented | Implemented | — |
| Run BOQ checks | — | — | — | Implemented | Implemented | — |
| Review accept/edit/reject findings | — | — | Implemented | — | — | — |
| Generate clarification/assumptions/bid-decision artifacts | — | — | — | Implemented | Implemented | — |
| Export Bid Review Pack (DOCX/XLSX/PDF) | — | — | — | Implemented | Implemented | — |
| Freeze baseline / notice register / handover | — | — | Partial (freeze needs reviewer) | Partial | — | — |
| Compare tender vs award baselines | — | Implemented | Implemented | Implemented | Implemented | — |
| Manage workspace / projects / members / invitations | — | — | — | — | Implemented | — |
| Configure org notice/commercial standards | — | Partial (notice via `/standards`) | — | — | Implemented | — |
| View billing status / invoices | — | Implemented | — | — | Implemented | — |
| Checkout / upgrade plan | — | — | — | — | Partial (backend only) | — |
| Assistant chat | — | Implemented | Implemented | Implemented | Implemented | — |
| Accuracy dashboard | — | — | — | — | Implemented | Implemented |
| Superadmin user/workspace management | — | — | — | — | — | Implemented (API only) |

### 3.2 Entity-to-Operation Matrix

| Entity | Create | View/List | Update | Delete/Archive | Search | Import | Export | Notes |
|---|---|---|---|---|---|---|---|---|
| User | signup | me | Partial | — | — | — | — | no email verification flow |
| Workspace | signup creates one | list | Partial | — | — | — | — | no slug/URL support |
| Project | API | API | — | — | — | — | — | no frontend |
| Opportunity | Implemented | Implemented | — | — | — | register document | baseline compare/handover | |
| Document | upload | list/text | — | — | crossref search | upload PDF/XLSX/CSV | — | no resumable upload |
| Deadline | auto-extracted | list | confirm | — | — | — | ICS export | |
| Clause | auto-segmented | list | — | — | crossref | — | — | |
| Finding | risk/BOQ/qualification | list, queue | review decision | — | — | — | export pack | |
| Artifact | generate | list/get | — | — | — | — | DOCX/XLSX/PDF | |
| Baseline | freeze | list/verify | — | — | — | — | handover pack | |
| Invoice | webhook | list | — | — | — | — | — | manual invoice possible |
| Rulepack / pattern | read (public list) | read | — | — | — | YAML on disk | — | all unvalidated |
| Org standard | PUT | GET | PUT | DELETE | — | — | — | notice + commercial |
| Audit log | auto | API | — | — | — | — | — | append-only |

### 3.3 Workflow Completeness Matrix

| Workflow | Entry point | Auth | Validation | Completion | Failure | Retry/Recovery | Notifications | History | Admin support |
|---|---|---|---|---|---|---|---|---|---|
| Sign up / log in | `/login`, `/api/auth/signup` | public | password min 8 | token issued | 401/409 | no account lockout | none | none | superadmin endpoints |
| Create opportunity | `/opportunities` page, `/api/ingestion/opportunities` | estimator+ | title required | opp created | 422 | manual | none | audit log partial | — |
| Upload tender docs | workbench upload, `/api/ingestion/.../upload` | estimator+ | size cap 2 GB only | document + clauses + deadlines | 413/422 | manual re-upload | none | document row | — |
| Run risk review | workbench risk tab, `/api/risk/opportunities/{id}/run` | estimator+ | opp exists | findings persisted | 503 if deps missing | re-run idempotent | none | findings + audit | analytics dashboard |
| Run BOQ check | workbench BOQ tab, `/api/boq/opportunities/{id}/upload` | estimator+ | table-shaped CSV/XLSX/PDF | findings persisted | 400/422 | re-upload | none | findings | — |
| Review findings | workbench risks tab, `/api/review/findings/{id}` | reviewer+ | decision in enum | status updated, audit log | 404/403 | re-decide | none | audit log | analytics |
| Generate artifacts | `/api/drafting/opportunities/{id}/artifacts` | estimator+ | review gate open | artifact versioned | 403 review incomplete | complete review first | none | artifact rows | — |
| Export pack | `/api/export/opportunities/{id}` | estimator+ | review gate open | XLSX/DOCX/PDF | 403 review incomplete | complete review first | none | artifact rows | — |
| Freeze baseline | `/api/baseline/opportunities/{id}/freeze` | reviewer+ | review gate open | sealed snapshot | 403 review incomplete | complete review first | none | baseline + audit | — |
| Billing upgrade | `/api/billing/checkout` | admin+ | plan kind | deterministic handle | 402 paywall | webhook activation | none | payment_log, invoices | superadmin |
| Workspace/team mgmt | API only | admin/owner | role in ROLES | member/invite created | 400/403 | retry | none (token returned raw) | audit log | superadmin endpoints |

### 3.4 Dashboard and Reporting Matrix

| Dashboard / Report | Status | Notes |
|---|---|---|
| Public landing page | Implemented | hardcoded demo card |
| Opportunity board / deadline wall | Implemented | `/opportunities` |
| Opportunity workbench (overview/risks/BOQ/artifacts/handover) | Implemented | hardcoded SAMPLE data buttons |
| Tender comparison portfolio ranking | Implemented | `/api/comparison/opportunities` (no frontend page) |
| Internal accuracy dashboard | Implemented | `/api/analytics/accuracy` (admin API only) |
| Billing / plan / invoices UI | Missing | only backend routes |
| Admin console / user impersonation / staff dashboards | Missing | raw superadmin API only |
| Audit log viewer | Missing | API exists, no UI |
| Help page | Implemented | `/help` |
| Notification / alert history | Missing | no scheduler |

### 3.5 Missing capabilities

- **Billing UI**: plan selection, checkout, invoice list, usage display.
- **Admin console**: user/workspace management, audit log viewer, staff SSO/impersonation, fraud/review telemetry.
- **Notification system**: real email/SMS/WhatsApp senders, deadline countdown alerts, notice-deadline reminders (`TS-043`, `TS-035`, `TS-079`).
- **Multi-workspace switcher**: backend `login`/`refresh` select the first workspace only.
- **Resumable upload / async processing**: large PDFs are processed synchronously in request (`TS-033`, `TS-034`).
- **Email verification flow**: `email_verified` column exists but is not enforced.
- **Password-reset via email**: tokens are returned in the JSON response.
- **Accessibility/SEO/print/report-specific pages**.

### 3.6 Product decisions required

1. **Production default rule-pack**: Are unvalidated patterns allowed for free/internal users, or blocked for all paying users until a QS signs off?
2. **MFA policy**: Is TOTP mandatory for owner/admin on Pro+ at login, or optional during Phase 1?
3. **Workspace membership model**: Should a user be able to belong to many workspaces and switch at login?
4. **Billing providers**: Is Razorpay sufficient for India launch, or must Stripe/GCC-UK support ship simultaneously?
5. **Storage adapter**: Is LocalStorage acceptable for self-hosted staging, or must S3/SSE be required before any production deploy?
6. **Demo sample data**: Should the "Load sample conditions / BOQ" buttons be removed or gated to a demo tenant in production?
7. **Admin console scope**: Is a separate internal admin SPA required, or can superadmin operations be CLI/API-only for launch?

---

## 4. Detailed Findings

### F01 — Default CORS wildcard in production

- **ID**: F01
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Configuration
- **Affected roles**: All browser users
- **Affected files / lines**:
  - `backend/app/core/config.py:28` — `cors_origins: str = "*"`
  - `backend/app/main.py:45-49` — `CORSMiddleware(... allow_methods=["*"], allow_headers=["*"])`
- **Evidence**: `Settings.cors_origin_list()` splits `"*"` into `["*"]`. The middleware is configured with `allow_methods=["*"]` and `allow_headers=["*"]`.
- **Root cause**: Development convenience left as production default.
- **Impact**: Any website can call the API from a victim's browser if the victim has a valid token, enabling cross-site request forgery-style attacks and token leakage/exploitation.
- **Recommended solution**: Set `TS_CORS_ORIGINS` to the exact production SPA origin(s); reject wildcard in non-local `env`; restrict `allow_methods` to `GET, POST, PUT, DELETE` and `allow_headers` to `Authorization, Content-Type`.
- **Code example / patch**: in `backend/app/core/config.py` add an `@model_validator` or startup check that raises if `env != "dev"` and `cors_origins == "*"`.
- **Regression risks**: Low; must update CI/local env files.
- **Tests to add**: `test_cors_rejects_wildcard_in_prod`, `test_preflight_only_known_origins`.
- **Verification**: set `TS_ENV=prod` and `TS_CORS_ORIGINS=https://example.com`, assert preflight from unknown origin is rejected.
- **Similar locations**: `frontend/lib/api.ts:4` defaults `API_BASE` to `http://localhost:8000/api`.

### F02 — Default Razorpay webhook secret enables payment/webhook forgery

- **ID**: F02
- **Status**: Confirmed Defect
- **Severity**: Critical
- **Release-blocking**: Yes
- **Category**: Security / Billing
- **Affected roles**: All users (anonymous can hit `/api/billing/webhooks/razorpay`)
- **Affected files / lines**:
  - `backend/app/core/config.py:31` — `razorpay_webhook_secret: str = "dev-razorpay-secret"`
  - `backend/app/modules/billing/webhook.py:11-15` — `verify_signature` uses this secret.
  - `backend/app/modules/billing/service.py:119-186` — `process_razorpay_webhook` applies plan changes and creates invoices after verification.
- **Evidence**: The test suite in `backend/tests/test_billing.py:51` uses `SECRET = "dev-razorpay-secret"` and forges a correctly-signed `subscription.activated` event that upgrades a workspace to `pro`.
- **Root cause**: A hardcoded, guessable default secret ships in `Settings`. If the deployer does not override it, HMAC verification is trivially bypassable.
- **Impact**: An attacker can forge Razorpay events to activate paid plans, mark reviews as paid, and create paid invoices without real money changing hands.
- **Recommended solution**:
  1. Remove the default string; make `razorpay_webhook_secret` a `SecretStr` with no default.
  2. Add a startup guard in `create_app` that raises if `env == "prod"` and the secret is missing or looks like the dev placeholder.
  3. Rotate the secret if it was ever deployed with the default.
- **Code example / patch**:
  ```python
  # backend/app/core/config.py
  razorpay_webhook_secret: SecretStr | None = None  # no default
  ```
  ```python
  # backend/app/main.py inside create_app
  if settings.env == "prod" and not settings.razorpay_webhook_secret:
      raise RuntimeError("TS_RAZORPAY_WEBHOOK_SECRET is required in production")
  ```
- **Regression risks**: Low; tests must provide the secret via env/override.
- **Tests to add**: `test_webhook_rejected_when_secret_missing`, `test_prod_boot_fails_without_webhook_secret`.
- **Verification**: run app with `TS_ENV=prod` and no `TS_RAZORPAY_WEBHOOK_SECRET`; expect startup failure. Run existing `test_webhook_activates_plan` with a non-default secret.
- **Similar locations**: `jwt_private_key` and `jwt_public_key` default to empty; while the app generates an ephemeral keypair, this is also dangerous in prod and is already flagged in comments.

### F03 — Risk engine uses unvalidated rule-pack patterns for paying users

- **ID**: F03
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (per build doc Phase-1 exit gate)
- **Category**: Product / Data integrity
- **Affected roles**: estimator, admin, reviewer, viewer
- **Affected files / lines**:
  - `backend/app/modules/risk/service.py:54-60` — `run_opportunity` calls `self._loader.list_patterns(self._pack_id)` without `validated_only=True`.
  - `backend/app/modules/rulepacks/loader.py:134-138` — `list_patterns` supports `validated_only=True`.
  - `rulepacks/in-works/pack.yaml:9-11` — every pattern is `confidence: unvalidated` and `reviewer_signoff: null`.
  - `rulepacks/in-works/risk_patterns/*.yaml` — all five patterns have `confidence: unvalidated`.
- **Evidence**: `grep -n "confidence" rulepacks/in-works/risk_patterns/*.yaml` returns `unvalidated` for every file. `RiskService.run_opportunity` does not pass the validated flag.
- **Root cause**: The engine was wired to use all available patterns; the validated-only paying-user gate documented in `loader.py:134` is never invoked.
- **Impact**: Paying customers may be shown risk findings from patterns that have not been QS-reviewed, creating commercial and legal liability. The build doc Phase-1 exit gate requires validation before paid use.
- **Recommended solution**:
  1. In `RiskService.run_opportunity`, call `self._loader.list_patterns(self._pack_id, validated_only=True)` when the workspace plan is not `free` or when an `internal/demo` flag is false.
  2. Gate free/internal/demo workspaces to use all patterns for tuning, but log a warning.
  3. Add a `validated_at` / `reviewer_signoff` workflow before marking patterns `validated`.
- **Code example / patch**:
  ```python
  # backend/app/modules/risk/service.py
  validated_only = workspace_plan not in {"free", "internal"}
  patterns = self._loader.list_patterns(self._pack_id, validated_only=validated_only)
  ```
- **Regression risks**: May reduce finding counts for paying workspaces until patterns are validated; ensure the Phase-0/1 validation pipeline feeds `confidence: validated`.
- **Tests to add**: `test_risk_engine_uses_unvalidated_for_demo_only`, `test_paid_plan_uses_validated_patterns`.
- **Verification**: set a pattern to `validated`, create a paying workspace, run risk, and assert only validated patterns appear.
- **Similar locations**: `backend/app/modules/rulepacks/router.py:29` public `list_patterns` endpoint defaults `validated_only=False`; consider defaulting to `True` for authenticated non-demo callers.

### F04 — MFA is enroll-only and not enforced at login

- **ID**: F04
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (for admin/owner Pro+)
- **Category**: Security / Auth
- **Affected roles**: All authenticated users, especially admin/owner
- **Affected files / lines**:
  - `backend/app/modules/auth/mfa.py:2` — "Optional; mandatory for owner/admin on Pro+ is enforced at login in a follow-up."
  - `backend/app/modules/auth/service.py:468-487` — `mfa_enroll` / `mfa_verify`.
  - `backend/app/modules/auth/service.py:71-93` — `login` never checks MFA.
  - `backend/app/modules/auth/router.py:324-331` — `mfa_verify` endpoint exists but is separate from login.
- **Evidence**: `mfa_verify` only returns a boolean; `login` does not inspect `user.mfa_method`, `mfa_totp_secret`, or any verified MFA state. The MFA routes are not part of the token issuance flow.
- **Root cause**: MFA verification was implemented as an isolated endpoint; the follow-up to enforce it during token issuance is pending.
- **Impact**: Even if a user enrolls TOTP, an attacker with the password can log in without the second factor.
- **Recommended solution**:
  1. Add a `mfa_verified_at` timestamp and a `pending_mfa_token` (short-lived, single-use) to the login flow.
  2. If MFA is enrolled, `login` returns `mfa_required: true` and a short-lived token; `/mfa/verify` exchanges it for the real access/refresh tokens.
  3. Enforce mandatory MFA for owner/admin on Pro+.
- **Regression risks**: Login response shape changes; frontend must handle `mfa_required`.
- **Tests to add**: `test_login_requires_mfa_when_enrolled`, `test_mfa_verified_token_exchanged_for_full_session`.
- **Verification**: enroll MFA, call `login` with correct password, assert `mfa_required`; verify correct TOTP, assert full tokens.
- **Similar locations**: `TS-079` in `tasks/backlog.md` tracks real email/SMS MFA delivery.

### F05 — Frontend stores access token in localStorage and never rotates refresh tokens

- **ID**: F05
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Frontend
- **Affected roles**: All web users
- **Affected files / lines**:
  - `frontend/components/session.tsx:1-44` — stores `{token, role, workspaceId, is_superadmin}` in `localStorage`.
  - `frontend/lib/api.ts:33-47` — attaches the token to every request; no `refresh_token` usage.
  - `frontend/app/login/page.tsx` — uses `signIn(tokens)` but `session.tsx` discards `refresh_token`.
- **Evidence**: `SessionProvider` only stores `access_token`; `refresh_token` is ignored. `signOut` only clears localStorage and does not call `/api/auth/logout`, so refresh tokens remain valid server-side.
- **Root cause**: The frontend is a skeleton with a documented TODO; production cookie-based refresh was not implemented.
- **Impact**: XSS can steal the access token; users cannot recover a session after the 15-minute token expires; logout does not revoke refresh tokens.
- **Recommended solution**:
  1. Move refresh token to an `httpOnly`, `SameSite=Strict`, `Secure` cookie set by `/api/auth/login` and `/api/auth/refresh`.
  2. Keep access token in memory; implement an Axios/fetch interceptor that calls `/api/auth/refresh` on 401.
  3. Call `/api/auth/logout` with the refresh token on sign-out.
- **Regression risks**: Requires backend cookie handling and CORS `credentials: "include"`.
- **Tests to add**: E2E tests for token refresh, logout revocation, and XSS token exfiltration mitigation.
- **Verification**: set short `TS_ACCESS_TTL_MINUTES=1`, refresh the page, assert frontend silently refreshes and API calls succeed.
- **Similar locations**: build doc §5 explicitly states production keeps refresh token in httpOnly cookie.

### F06 — Login and refresh arbitrarily select the first workspace

- **ID**: F06
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (for multi-workspace users)
- **Category**: Auth / Product
- **Affected roles**: Users belonging to multiple workspaces
- **Affected files / lines**:
  - `backend/app/modules/auth/service.py:80` — `member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))`
  - `backend/app/modules/auth/service.py:110-111` — same pattern in `refresh`.
- **Evidence**: `select(WorkspaceMember).where(...)` with no ordering returns one arbitrary row. If a user is a member of several workspaces, login always lands in the same one; there is no `active_workspace_id` or workspace switcher.
- **Root cause**: The token embeds a single `workspace_id`; the query is not deterministic and does not let the user choose.
- **Impact**: Users with multiple workspaces cannot switch; permissions and data access may be wrong.
- **Recommended solution**:
  1. Add an `/api/auth/workspaces/switch` endpoint that issues a new access token with a different `workspace_id` and role.
  2. Order workspace selection by `created_at` or last-used, and include a `workspace_id` prompt on login if multiple exist.
  3. Build a workspace switcher in the frontend nav.
- **Regression risks**: Token shape already includes `workspace_id`; no breaking change.
- **Tests to add**: `test_login_with_multiple_workspaces_returns_list_and_requires_selection`, `test_switch_workspace_reissues_token`.
- **Verification**: create a user in two workspaces, login, assert response lists workspaces; switch, assert token contains chosen workspace.
- **Similar locations**: `frontend/lib/api.ts` token consumers assume a single workspace.

### F07 — Forgot-password and invitations return raw tokens; email/SMS delivery not wired

- **ID**: F07
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Auth / Notifications
- **Affected roles**: All users, admins inviting members
- **Affected files / lines**:
  - `backend/app/modules/auth/service.py:396-416` — `create_invitation` returns `{"token": token, ...}` with TODO at line 415.
  - `backend/app/modules/auth/service.py:491-501` — `forgot_password` returns `{"ok": True, "token": raw}` with TODO at line 500.
- **Evidence**: Both functions have explicit TODO comments. `forgot_password` does return `{"ok": True}` for unknown emails, but for known emails leaks the raw reset token in the JSON response.
- **Root cause**: Email/SMS senders are not implemented (`TS-035`, `TS-079`).
- **Impact**: Reset and invitation tokens can be read from network logs or browser dev tools, bypassing the intended out-of-band channel.
- **Recommended solution**:
  1. Implement `EmailSender`/`SmsSender` behind the `notifications.sender` protocol.
  2. Replace dev-only token returns with `{"ok": True}`; send the token via email/SMS using a templated link.
  3. Add rate limiting and per-user/per-email throttling for forgot-password and invitation creation.
- **Regression risks**: Frontends relying on the raw token for testing must switch to reading from test outboxes.
- **Tests to add**: `test_forgot_password_sends_email_no_token_in_response`, `test_invitation_email_delivered`.
- **Verification**: call `forgot-password` for a known user, assert response has no `token`; assert `ConsoleSender`/`EmailSender` received the message.
- **Similar locations**: `frontend/app/forgot-password/page.tsx` and reset page may expect a token in the URL query string.

### F08 — No rate limiting on public auth and billing endpoints

- **ID**: F08
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Resilience
- **Affected roles**: All users, anonymous attackers
- **Affected files / lines**:
  - `backend/app/modules/auth/router.py:123-424` — all auth routes have no rate limits.
  - `backend/app/modules/billing/router.py:98-105` — `/api/billing/webhooks/razorpay` has no rate limit.
- **Evidence**: No `slowapi`, `fastapi-limiter`, or custom rate-limit dependency is used anywhere in the codebase.
- **Root cause**: Rate-limiting infrastructure was not added.
- **Impact**: Credential stuffing, signup abuse, enumeration, webhook flooding, and DoS against `/login`, `/signup`, `/forgot-password`, `/reset-password`, and `/billing/webhooks/razorpay`.
- **Recommended solution**:
  1. Add `slowapi` with Redis-backed storage.
  2. Apply stricter limits to public routes (5 req/min for auth) and per-signature limits to webhooks.
  3. Add account lockout after N failed logins.
- **Regression risks**: None; can be added as middleware/dependencies.
- **Tests to add**: `test_login_rate_limit_blocks_after_threshold`, `test_webhook_rate_limit`.
- **Verification**: fire 10 `POST /api/auth/login` requests quickly from one IP, assert 429 after threshold.
- **Similar locations**: all public routes.

### F09 — File upload endpoints lack validation and process synchronously in request

- **ID**: F09
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Performance
- **Affected roles**: estimator, admin
- **Affected files / lines**:
  - `backend/app/modules/ingestion/router.py:12` — `MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024` (2 GB).
  - `backend/app/modules/ingestion/router.py:110-146` — reads entire file into memory, runs extraction/segmentation in the request.
  - `backend/app/modules/ingestion/extract.py:15-24` — `extract_text` falls back to `data.decode("utf-8")` for unknown extensions with no MIME check.
  - `backend/app/modules/boq/router.py:56-86` — BOQ upload has no size cap and reads the whole file.
- **Evidence**: `extract_upload` checks only filename suffix. There is no MIME sniffing, no virus scan, and no async job queue. BOQ upload `await file.read()` has no `max_length`.
- **Root cause**: Synchronous request-time processing chosen for simplicity; validation deferred.
- **Impact**: DoS via memory exhaustion, malicious binary upload, and lack of malware scanning.
- **Recommended solution**:
  1. Cap file size per plan (e.g. 50 MB free, higher for paid) at reverse proxy and in code.
  2. Validate MIME type and magic bytes; reject executable/archive uploads.
  3. Stream uploads to S3 and process asynchronously via Celery/Redis with progress SSE (`TS-033`, `TS-034`).
  4. Add virus scanning (ClamAV or cloud) before extraction.
- **Regression risks**: Large workflow changes; frontends need upload progress UI.
- **Tests to add**: `test_upload_rejects_large_file`, `test_upload_rejects_bad_mime`, `test_async_extraction_sse`.
- **Verification**: upload a 100 MB file, expect 413; upload an `.exe` renamed `.pdf`, expect 415.
- **Similar locations**: `backend/app/modules/ingestion/storage.py:22-29` builds a local path from the SHA and extension.

### F10 — Missing HTTPS/security headers middleware

- **ID**: F10
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security
- **Affected roles**: All web users
- **Affected files / lines**:
  - `backend/app/main.py:44-50` — only `CORSMiddleware` is added.
- **Evidence**: No `HTTPSRedirect`, `TrustedHost`, `X-Frame-Options`, `HSTS`, `CSP`, `Referrer-Policy`, or `Permissions-Policy` headers are configured in FastAPI.
- **Root cause**: Security headers were not added to the app factory.
- **Impact**: Clickjacking, protocol downgrade, MIME sniffing, and reduced XSS mitigation.
- **Recommended solution**:
  1. Add `HTTPSRedirectMiddleware` and `TrustedHostMiddleware` when `env != "dev"`.
  2. Add a custom middleware that sets `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- **Regression risks**: CSP may block inline scripts; test frontend thoroughly.
- **Tests to add**: `test_security_headers_present`, `test_http_redirects_to_https_in_prod`.
- **Verification**: call a health endpoint, assert required headers are present.
- **Similar locations**: none.

### F11 — LocalStorage is the only file storage adapter

- **ID**: F11
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (for multi-container/cloud deploys)
- **Category**: Infra / Reliability
- **Affected roles**: All upload users
- **Affected files / lines**:
  - `backend/app/modules/ingestion/storage.py:18-29` — only `LocalStorage` exists.
  - `backend/app/core/config.py:14` — `storage_dir: str = "./.tender_storage"`.
  - `backend/Dockerfile:9-13` — container local filesystem is ephemeral unless a volume is mounted.
- **Evidence**: `Storage` is a Protocol but no S3 implementation is provided. `ingestion/router.py:126` always instantiates `LocalStorage(request.app.state.ctx.settings.storage_dir)`.
- **Root cause**: S3 adapter planned but not implemented.
- **Impact**: Files disappear on container restart/redeploy; not horizontally scalable; no server-side encryption.
- **Recommended solution**:
  1. Implement an `S3Storage` class (per-org prefix, SSE-KMS, presigned GET) behind the `Storage` protocol.
  2. Select the adapter via config (`TS_STORAGE_TYPE=s3|local`).
  3. For prod, require `s3` and reject `local`.
- **Regression risks**: Local dev still wants LocalStorage; use config switch.
- **Tests to add**: `test_s3_storage_put_get`, `test_local_storage_path_traversal`.
- **Verification**: configure S3 in tests (moto), upload a file, assert it is stored under `workspace_id/...` and retrievable.
- **Similar locations**: `docs/TenderShield_Full_Build_Doc.md` §11.2 expects S3 in prod.

### F12 — Billing checkout returns a deterministic handle, no live payment provider order

- **ID**: F12
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (for paid launch)
- **Category**: Product / Billing
- **Affected roles**: admin, owner
- **Affected files / lines**:
  - `backend/app/modules/billing/router.py:34-55` — `checkout` returns a JSON with `provider: "razorpay"`, `notes`, and a note that activation is via webhook.
  - `backend/app/modules/billing/plans.py:9-14` — prices in paise, no live order creation.
- **Evidence**: The endpoint never calls Razorpay's `/orders` or Stripe's `Checkout.Session.create`. It returns a deterministic `notes` object for the client to pass to Razorpay; the backend trusts the webhook for all activation.
- **Root cause**: Live payment-provider SDK integration not wired (`TS-037` todo).
- **Impact**: No actual payment collection can happen; a user can obtain a checkout handle and wait for a real or forged webhook.
- **Recommended solution**:
  1. Add a `BillingProvider` protocol with `RazorpayProvider` and `StripeProvider` implementations.
  2. In `/checkout`, create a real provider order/session, persist a pending `Payment`, and return the provider's order/session id.
  3. Use `country` from the workspace to choose Razorpay (IN/GCC) or Stripe.
- **Regression risks**: Frontend must switch from notes-based to order-id-based checkout.
- **Tests to add**: `test_checkout_creates_razorpay_order`, `test_stripe_used_for_uk_workspace`.
- **Verification**: mock Razorpay API, call `/checkout`, assert a POST to Razorpay `/orders` was made and `order_id` returned.
- **Similar locations**: `backend/app/modules/billing/service.py` `create_invoice` is fine but only called by webhooks.

### F13 — npm audit reports high-severity transitive vulnerabilities

- **ID**: F13
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Security / Supply chain
- **Affected roles**: End users of the frontend
- **Affected files / lines**:
  - `frontend/package.json:12` — `next: "^15.5.21"`.
  - `frontend/package-lock.json` — `postcss` and `sharp` pulled in by Next.js.
- **Evidence**: `npm audit` reported 3 high severity issues: `postcss` XSS / path traversal / source map disclosure, and `sharp` inherited libvips CVEs. `npm audit fix --force` would install `next@9.3.3`.
- **Root cause**: Next.js 15.5.21 depends on vulnerable `postcss` and `sharp` versions.
- **Impact**: Potential XSS, arbitrary file read, and library vulnerabilities in image processing.
- **Recommended solution**:
  1. Check for a newer Next.js patch that resolves the advisories.
  2. If no patch exists, override `postcss` and `sharp` to patched versions using `npm overrides` or `resolutions` and verify the build still works.
  3. Add `npm audit` to CI and fail on high/critical findings.
- **Regression risks**: Build output may change; run `next build` and visual diff.
- **Tests to add**: `npm audit` in CI; no new code tests needed.
- **Verification**: run `npm audit` after override, confirm zero high/critical.
- **Similar locations**: backend has no `pip-audit` or `safety` step either.

### F14 — Missing `.env.local`, `.env.dev`, `.env.prod` files; `run.sh` and docs reference them

- **ID**: F14
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (for local dev / staging)
- **Category**: DevEx / Deployment
- **Affected roles**: Developers, operators
- **Affected files / lines**:
  - `scripts/run.sh:7-16` — expects `.env.${ENV}` and exits with "Missing env file".
  - `docs/deployment.md:9-11` — claims `.env.local`, `.env.dev`, `.env.prod` exist.
  - `CHANGELOG.md:101-105` (TS-072) — claims these files were added.
  - `.gitignore:19-21` — `.env.*` are ignored except `.env.example`.
  - `docker-compose.yml:24` — `env_file: [.env]`.
- **Evidence**: `find_file_by_name .env*` returned only `.env.example`. `scripts/run.sh local` would fail.
- **Root cause**: The env files were either never created, removed, or ignored and not committed. The docs and changelog are out of sync.
- **Impact**: New contributors and CI cannot run `./scripts/run.sh local` or `docker compose` without manually recreating env files; risk of stale/missing config.
- **Recommended solution**:
  1. Add `.env.local`, `.env.dev`, `.env.prod` templates that are **safe for commit** (only placeholder/no secrets) and rename `.env.example` or remove the broad `.gitignore` rule for these specific files.
  2. Update `docker-compose.yml` to use `.env.local` for local and `.env.dev`/`.env.prod` for the respective stacks.
  3. Update `docs/deployment.md` and `CHANGELOG.md` to match reality.
- **Regression risks**: Ensure no real secrets are committed; use placeholders.
- **Tests to add**: CI step that runs `./scripts/run.sh --dry-run local` or `docker compose config`.
- **Verification**: fresh clone, copy `.env.local.example` → `.env.local`, run `./scripts/run.sh local`, expect backend/frontend to start.
- **Similar locations**: `README.md` may also reference these files.

### F15 — Notifications module is console-only; no real email/SMS or deadline alerts

- **ID**: F15
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes
- **Category**: Product / Reliability
- **Affected roles**: All users (missing alerts)
- **Affected files / lines**:
  - `backend/app/modules/notifications/module.py:5-8` — provides `ConsoleSender` only.
  - `backend/app/modules/notifications/sender.py:24-31` — `ConsoleSender` appends to an in-memory list.
  - `backend/app/modules/notifications/router.py` — does not exist.
- **Evidence**: No SES/Resend/MSG91 adapter, no scheduler, no cron, no alert route. `tasks/backlog.md` marks `TS-035` as todo.
- **Root cause**: Notification adapters require credentials; only the protocol was implemented.
- **Impact**: Missed submission deadlines, missed notice windows, no password-reset or invitation emails, no MFA SMS.
- **Recommended solution**:
  1. Implement SES/Resend and MSG91 senders; gate by country/config.
  2. Add a periodic task runner (Celery beat or APScheduler) that scans deadlines and notice rules and sends alerts at configurable thresholds.
  3. Expose notification preferences API and UI.
- **Regression risks**: Need retry/back-off for failed deliveries; idempotency to avoid duplicate alerts.
- **Tests to add**: `test_deadline_alert_sent`, `test_notification_retry`.
- **Verification**: configure `ConsoleSender`, create deadline in 1 hour, run scheduler, assert message in outbox.
- **Similar locations**: `backend/app/modules/notifications/digest.py` exists; review its logic when wiring the scheduler.

### F16 — Frontend opportunity workbench ships hardcoded SAMPLE data and lacks billing/admin pages

- **ID**: F16
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Product / UX
- **Affected roles**: estimator, admin, reviewer
- **Affected files / lines**:
  - `frontend/app/opportunities/[id]/page.tsx:22-45` — `const SAMPLE` and `const SAMPLE_BOQ` are used by "Load sample ..." buttons.
  - `frontend/app/page.tsx:42-43` — claims "Hosted in India (ap-south-1)" without infra evidence in the repo.
- **Evidence**: The workbench has `loadConditions()` and `runBoq()` functions that push hardcoded demo text into the production API.
- **Root cause**: Demo data left in the main opportunity page.
- **Impact**: Users may accidentally pollute real opportunities with demo data; looks unprofessional; no billing or admin UI exists.
- **Recommended solution**:
  1. Remove SAMPLE data from production pages; gate demo mode behind a separate `/demo` route or a `DEMO_TENANT` workspace.
  2. Add billing page (`/billing`), admin dashboard (`/admin`), and workspace switcher.
- **Regression risks**: Low; frontend-only.
- **Tests to add**: E2E that demo data is not shown in non-demo workspaces.
- **Verification**: open `/opportunities/{id}` on a production build, assert no "Load sample" buttons.
- **Similar locations**: `frontend/lib/api.ts` has a fallback `listOpportunities` 404 → empty array.

### F17 — Bid Review Pack export lacks named reviewer signature and date

- **ID**: F17
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Product / Compliance
- **Affected roles**: estimator, reviewer
- **Affected files / lines**:
  - `backend/app/modules/export/service.py:77-96` — `export` builds `meta = {"date": date.today().isoformat(), "pack": self._pack_version}`.
  - `backend/app/modules/export/render.py:14-19` — `stamp_line` says "reviewed and approved on ..." but does not name the reviewer.
- **Evidence**: The renderer includes a generic stamp, not the actual `reviewed_by` user or a digital signature. Build doc §11.4 describes professional-liability sign-off.
- **Root cause**: `export` does not pass reviewer identity into `meta`.
- **Impact**: Generated packs cannot be traced to the reviewer who accepted the findings; compliance/liability gap.
- **Recommended solution**:
  1. In `ExportService.export`, read the `reviewer_id` from the latest `AuditLog` or `FindingRow.reviewed_by`, include the user's email/name, and add it to `meta`.
  2. Optionally add a tamper-evident signature/hash over the export bytes.
- **Regression risks**: None significant.
- **Tests to add**: `test_export_includes_reviewer_name_and_date`.
- **Verification**: accept a finding as user X, export PDF, assert stamp contains X and date.
- **Similar locations**: `backend/app/modules/review/service.py:72-79` writes reviewer to audit log.

### F18 — No ESLint / mypy strict gates in CI

- **ID**: F18
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Maintainability
- **Affected roles**: Developers
- **Affected files / lines**:
  - `frontend/package.json:9` — `"lint": "next lint"`.
  - `frontend` root — no `.eslintrc` or `eslint.config.mjs`.
  - `backend/pyproject.toml:48-63` — only `ruff` config; no `mypy`.
  - `.github/workflows/ci.yml` — only `ruff check .`, `pytest`, `npm run build`.
- **Evidence**: `npm run lint` prompts for ESLint setup. `ruff` does not perform static type checking. CI does not run `mypy` or `tsc --noEmit`.
- **Root cause**: Lint/type tooling not fully configured.
- **Impact**: Type errors and lint issues can reach main; slower debugging.
- **Recommended solution**:
  1. Add `eslint`/`typescript-eslint` to the frontend and run `npm run lint` in CI.
  2. Add `mypy` to backend dev deps and run `mypy --strict app` in CI.
  3. Add `pip-audit`/`safety` and `npm audit` to CI.
- **Regression risks**: May reveal existing type/lint errors that need fixing.
- **Tests to add**: none (tooling).
- **Verification**: CI fails on `mypy`/`eslint`/`npm audit` high findings.
- **Similar locations**: `backend/pyproject.toml` dev extras.

### F19 — Phase-1 accuracy / evaluation pipeline is not integrated; all patterns remain unvalidated

- **ID**: F19
- **Status**: Confirmed Defect
- **Severity**: High
- **Release-blocking**: Yes (per build doc Phase-1 exit gate)
- **Category**: Product / Quality
- **Affected roles**: Product, QA, domain reviewers
- **Affected files / lines**:
  - `rulepacks/in-works/pack.yaml:9-11` — "every pattern is confidence: unvalidated until the Phase-1 QS checkpoint".
  - `evals/in-works/scorecard.md` — empty scorecard; no real HITs/MISSes filled.
  - `scripts/phase0_accuracy_test.py` — throwaway script, not part of CI, requires `anthropic` which is not installed.
- **Evidence**: All five risk patterns are `confidence: unvalidated`. The scorecard table is empty. There is no automated pipeline that runs on every rule/prompt change and compares model output against golden answers.
- **Root cause**: Accuracy validation depends on manual QS sign-off and is not automated yet.
- **Impact**: The product cannot satisfy its own Phase-1 exit gate, risking incorrect risk findings for real tenders.
- **Recommended solution**:
  1. Build a CI job that runs the accuracy harness against the synthetic and real golden sets and enforces the scorecard thresholds.
  2. Track pattern `confidence` changes through PR review and require a QS sign-off before flipping to `validated`.
  3. Wire the `analytics` dashboard to real precision/recall once golden labels exist.
- **Regression risks**: May block releases until accuracy thresholds are met; that is intentional.
- **Tests to add**: `test_phase0_scorecard_recall_threshold`.
- **Verification**: run `scripts/phase0_accuracy_test.py evals/in-works/sample_tender/conditions.md` with an API key and assert recall ≥ 70%, critical recall ≥ 90%, zero invented quotes.
- **Similar locations**: `evals/in-works/sample_tender/gold_answer.yaml` provides the expected hits.

### F20 — BOQ upload route has no size cap and reads the whole file into memory

- **ID**: F20
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Performance / Reliability
- **Affected roles**: estimator, admin
- **Affected files / lines**:
  - `backend/app/modules/boq/router.py:56-86` — `upload_boq` does `await file.read()` with no `MAX_UPLOAD_BYTES` check.
- **Evidence**: Unlike `ingestion/router.py:12` (2 GB cap), BOQ upload has no equivalent guard.
- **Root cause**: Size validation omitted from the BOQ route.
- **Impact**: A large or malformed BOQ file can exhaust memory.
- **Recommended solution**: Add `MAX_UPLOAD_BYTES` and stream/chunk large CSV/XLSX; reject PDFs larger than the cap.
- **Regression risks**: Low.
- **Tests to add**: `test_boq_upload_rejects_oversized_file`.
- **Verification**: upload a 2 GB+ file to `/api/boq/opportunities/{id}/upload`, expect 413.
- **Similar locations**: `backend/app/modules/ingestion/router.py:110-146`.

### F21 — No admin console beyond raw superadmin API endpoints

- **ID**: F21
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Product / Admin
- **Affected roles**: superadmin
- **Affected files / lines**:
  - `backend/app/modules/auth/router.py:388-424` — `/api/auth/admin/users` and `/api/auth/admin/workspaces`.
  - `frontend/app/` — no `/admin` directory or admin pages.
- **Evidence**: Superadmin operations are API-only; no UI for user/workspace/plan management, audit logs, or analytics.
- **Root cause**: Admin console deferred.
- **Impact**: Operations and support must use `curl`/scripts; higher chance of human error.
- **Recommended solution**: Build a protected `/admin` Next.js route (or separate admin SPA) that consumes the existing superadmin endpoints and adds audit log viewer.
- **Regression risks**: Frontend-only; backend already supports the API.
- **Tests to add**: E2E admin smoke tests.
- **Verification**: login as superadmin, navigate `/admin`, list users and workspaces.
- **Similar locations**: `backend/app/modules/analytics/router.py:24-29` admin-only accuracy endpoint.

### F22 — Weak password policy and no account lockout / breach checks

- **ID**: F22
- **Status**: Confirmed Defect
- **Severity**: Medium
- **Release-blocking**: No
- **Category**: Security
- **Affected roles**: All users
- **Affected files / lines**:
  - `backend/app/modules/auth/router.py:30-31` — `password: str = Field(min_length=8)`.
  - `backend/app/modules/auth/service.py:71-79` — `login` returns `invalid_credentials` with no delay/lockout.
- **Evidence**: Only length is checked; no complexity, no HaveIBeenPwned/troy-hunt breach check, no account lockout.
- **Root cause**: MVP auth focused on Argon2 and JWT; additional controls deferred.
- **Impact**: Weak credentials can be brute-forced; no breach awareness.
- **Recommended solution**: Add Pydantic validator for complexity; integrate breach API or local bloom filter; add exponential backoff/lockout after failed attempts.
- **Regression risks**: Slightly slower login; acceptable.
- **Tests to add**: `test_weak_password_rejected`, `test_account_lockout_after_failures`.
- **Verification**: try `password` → rejected; fail login 5 times → locked.
- **Similar locations**: signup route.

### F23 — Health endpoint exposes internal module and capability list publicly

- **ID**: F23
- **Status**: Probable Risk
- **Severity**: Low
- **Release-blocking**: No
- **Category**: Security / Information disclosure
- **Affected roles**: Anonymous
- **Affected files / lines**:
  - `backend/app/modules/health/router.py:6-17` — returns loaded module names, failed modules, and all registered capability names.
- **Evidence**: The endpoint is unauthenticated and lists `auth.authenticate`, `rulepacks.loader`, `billing.record_usage`, etc.
- **Root cause**: Health endpoint designed for debug visibility.
- **Impact**: Attackers can enumerate the attack surface and identify disabled/failed modules.
- **Recommended solution**: Keep a minimal `/health` status endpoint public; move the detailed capability/module report behind an admin-only `/health/details` route.
- **Regression risks**: Low; any load balancer must be updated if it checks the detailed endpoint.
- **Tests to add**: `test_public_health_minimal`, `test_detailed_health_requires_admin`.
- **Verification**: `GET /api/health` as anonymous returns only `{"status":"ok"}`.
- **Similar locations**: none.

### F24 — Landing page makes unverified "Hosted in India" claim

- **ID**: F24
- **Status**: Clarification Required
- **Severity**: Low
- **Release-blocking**: No
- **Category**: Product / Compliance
- **Affected roles**: Marketing/operations
- **Affected files / lines**:
  - `frontend/app/page.tsx:42-43` — "Hosted in India (ap-south-1)".
- **Evidence**: No Terraform, CDK, or deployment file in the repo places infrastructure in `ap-south-1`.
- **Root cause**: Marketing copy added before infra finalized.
- **Impact**: Potential false advertising / compliance claim if the actual deployment differs.
- **Recommended solution**: Confirm actual hosting region and data-residency plans; update copy or remove until verified.
- **Regression risks**: None.

### F25 — ComparisonService uses deprecated `datetime.utcnow()`

- **ID**: F25
- **Status**: Improvement Opportunity
- **Severity**: Low
- **Release-blocking**: No
- **Category**: Maintainability
- **Affected files / lines**:
  - `backend/app/modules/comparison/service.py:68` — `datetime.utcnow()`.
- **Evidence**: Python 3.12 deprecates `datetime.utcnow()`.
- **Root cause**: Leftover usage.
- **Impact**: Deprecation warnings; potential naive/aware mixing bugs if `submission_due` is timezone-aware.
- **Recommended solution**: Replace with `datetime.now(UTC)` and ensure `submission_due` is timezone-aware.
- **Regression risks**: Low.

---

## 5. Remediation Plan

### Immediate release blockers (fix before any production deploy)

| Finding | Action | Owner | Verification |
|---|---|---|---|
| F02 | Remove default Razorpay webhook secret; enforce prod startup check | Security/DevOps | `test_prod_boot_fails_without_webhook_secret` |
| F03 | Filter risk patterns by `validated_only=True` for paying/internal users | Product/ML | `test_paid_plan_uses_validated_patterns` |
| F04 | Enforce MFA at login; wire token refresh flow | Auth/Frontend | `test_login_requires_mfa_when_enrolled` |
| F05 | Move refresh token to httpOnly cookie; implement refresh | Frontend/Auth | E2E token refresh test |
| F01 | Restrict CORS to known origins; add security headers | Security | preflight/header tests |
| F08 | Add rate limiting to public routes and webhooks | Security | rate-limit tests |
| F09 | Add file validation, size caps, and async processing plan | Backend | upload validation tests |
| F11 | Provide S3 storage adapter and require it in prod | DevOps | S3 integration test |
| F13 | Patch `postcss`/`sharp` vulnerabilities and add `npm audit` to CI | Frontend | `npm audit` clean |
| F19 | Integrate Phase-1 accuracy harness and QS sign-off workflow | Product/QA | scorecard thresholds in CI |

### Required pre-release fixes (before paid/general availability)

| Finding | Action | Owner |
|---|---|---|
| F06 | Multi-workspace selection and switcher | Auth/Frontend |
| F07 | Real email/SMS delivery for password reset and invitations | Auth/Notifications |
| F10 | HTTPS/security headers middleware | Security |
| F12 | Live payment provider order creation (Razorpay/Stripe) | Billing |
| F14 | Add missing env files and fix `run.sh` / Docker Compose | DevOps |
| F15 | Real notification senders and deadline alert scheduler | Notifications |
| F16 | Remove demo data from prod pages; add billing/admin UI | Frontend |
| F18 | Add ESLint, mypy, and dependency-audit gates to CI | Engineering |

### Short-term improvements (next sprint)

- F17: Add reviewer identity and digital signature to Bid Review Pack.
- F20: Add size cap to BOQ upload.
- F21: Build admin console.
- F22: Strengthen password policy and account lockout.
- F23: Split public and admin health endpoints.
- F24: Verify and update landing-page hosting claims.
- F25: Replace `datetime.utcnow()`.

### Long-term architectural improvements

- Replace synchronous upload/extraction with Celery + Redis + SSE progress.
- Implement full event-sourced audit log with tamper-evident signatures for baselines and exports.
- Add vector/semantic clause search and full-text index (currently crossref is token overlap only).
- Build a proper admin SPA with impersonation, staff roles, and operational dashboards.
- Add multi-region support and data-residency controls.

---

## 6. Residual Risks and Final Checklist

| Readiness area | Status | Evidence |
|---|---|---|
| Architecture / modularity | Pass | `test_architecture.py` passed; no cross-module imports; registry/event bus used |
| Automated build | Pass | `next build` succeeded |
| Type checking | Partial | `tsc --noEmit` clean; no `mypy` or strict backend type checking |
| Lint | Partial | `ruff` clean; frontend ESLint not configured |
| Unit/integration tests | Pass | 144 passed, 1 skipped, 1 warning |
| Dependency security | Fail | `npm audit` 3 high severity findings; no `pip-audit` in CI |
| Auth / sessions | Fail | tokens in localStorage, no MFA enforcement, no rate limits |
| Authorization / tenant isolation | Partial | RLS helpers and workspace-scoped models present; not tested against live Postgres; superadmin RLS edge cases untested |
| Security headers / CORS | Fail | wildcard CORS, no security headers |
| File uploads | Fail | no MIME/virus/size validation for BOQ; ingestion size cap only |
| Billing / payments | Fail | default webhook secret, no live order creation |
| Notifications | Fail | console-only sender, no scheduler |
| Frontend completeness | Partial | core workbench exists; billing/admin/upgrade missing, demo data present |
| Product accuracy / validation | Fail | all patterns unvalidated, scorecard empty |
| Deployment / env | Fail | missing env files, local dev flow broken |
| Observability | Not tested | no logging/metrics/alerting config reviewed |
| Backups / DR | Not tested | no accessible backup/restore documentation |
| Accessibility | Not tested | not verified with automated tools |
| Performance / scalability | Partial | modular, but sync 2 GB uploads and no caching/queue |

### Final checklist

- [x] Architecture and critical workflows understood.
- [x] Missing product capabilities evaluated.
- [x] Role, entity, workflow, and dashboard matrices completed.
- [x] Auth, authorization, tenant isolation, security, and data integrity reviewed.
- [x] Relevant automated checks executed and documented.
- [x] Findings contain evidence, recommendations, and verification steps.
- [x] Product questions, scope limitations, and residual risks documented.
- [x] Release blockers clearly identified.
- [x] `PRODUCTION_READINESS_AUDIT.md` created.

---

*Prepared by Devin. This audit does not claim the code is bug-free or production-secure; it documents the state observed from the accessible repository and the checks run on 2026-07-29.*
