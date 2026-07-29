# TenderShield Production Readiness Audit

**Repository:** `Wasim-Shaikh25/tender-shield`  
**Audit date:** 2026-07-29  
**Scope:** Post-TS-083–TS-092 hardening re-audit. Full accessible repository; no source code changes were made. The only file produced/updated is this report.  
**Auditor role:** Principal Software Engineer, Security Engineer, QA Engineer, DevOps/SRE, Database Architect, Product Manager, UX/Accessibility, Performance.

---

## 1. Executive Summary

### 1.1 Readiness recommendation

**CONDITIONAL GO for controlled internal / design-partner staging use. NO-GO for any public, revenue-bearing production launch until the blockers listed in §5 are resolved.**

The recent TS-083–TS-092 commits fixed the bulk of the previous audit's Critical/High findings: CORS/production guards, security headers, HTTPS/trusted-host enforcement, RS256 JWT auth with httpOnly refresh cookies, MFA enforcement at login, workspace switching, file upload validation, S3 storage adapter, real payment-provider adapters, notification adapters, deadline-alert scheduling, admin/billing/analytics UI, export reviewer stamping, CI hardening, and removal of hardcoded demo data.

However, **three classes of issues prevent a production release**:

1. **Product data is not production-ready** — every risk-pattern and trade-checklist in `rulepacks/in-works/` is still `confidence: unvalidated`, and the code deliberately hides unvalidated patterns from paying workspaces. A paid workspace therefore receives **zero risk findings**.
2. **Deployment is broken out-of-the-box** — `.env.local`, `.env.dev`, and `.env.prod` are missing, `scripts/run.sh` exits, and `docker-compose.yml` references a file that does not exist, despite docs and the changelog claiming they exist.
3. **Security/operational guards are still stubs or misconfigured** — virus scanning is a no-op, S3 calls block the async event loop, the tus PATCH and Celery SSE endpoints are unauthenticated, and several integration fallbacks leak tokens or accept fake money if credentials are omitted.

### 1.2 Finding count by severity

| Severity | Count | Finding IDs |
|---|---|---|
| Critical | 1 | F27 |
| High | 4 | F26, F28, F29, F30 |
| Medium | 8 | F31, F32, F34, F36, F37, F38, F39, F40 |
| Low | 3 | F33, F35, F41 |

### 1.3 Major technical and product risks

| Risk | Why it matters | Affected areas |
|---|---|---|
| Unvalidated rulepacks block paid value | Paying users get an empty risk register; violates the Build Doc §14 / Phase-1 exit gate. | `risk/service.py`, `rulepacks/in-works/` |
| Deployment cannot run from a clean clone | Missing env templates prevent `run.sh` and Docker Compose from working. | `scripts/run.sh`, `docker-compose.yml`, `.gitignore` |
| Integration fallbacks leak tokens / accept fake payments | `forgot-password`, `invitations`, and checkout return raw tokens/mock order IDs when credentials are absent. | `auth/service.py`, `billing/providers.py` |
| Malware and DoS vectors in file upload | Virus scan is a stub; tus PATCH has no auth and no max-size enforcement during chunks. | `core/storage.py`, `ingestion/tus.py`, `boq/router.py` |
| Async event loop blocking & broken local file URLs | S3 `put_object/get_object` are synchronous inside `async def`; local storage URL points to a non-existent `/api/files/{key}` route. | `core/storage.py` |
| No E2E, accessibility, or performance verification | All automated coverage is unit/integration; real user journeys and a11y are untested. | `frontend/`, CI workflow |
| No production operations artefacts | No Terraform/CDK, backup/restore scripts, monitoring, SLOs, or runbooks. | `docs/`, `.github/workflows/` |

### 1.4 Scope limitations

- No live AWS, Razorpay, Stripe, SES, MSG91, Anthropic, or RapidOCR credentials were available; integration behaviour was verified by code review and unit tests only.
- No browser end-to-end, accessibility (axe/Lighthouse), load, or security penetration testing was performed.
- No production infrastructure (Terraform, Kubernetes, etc.) was reviewed because it is not present in the repo.
- The audit was conducted on the current working tree; any uncommitted local changes are reflected in the assessment.

### 1.5 Release conditions

Before a public production release:

1. Commit `.env.local`/`.env.dev`/`.env.prod` templates and verify `scripts/run.sh local` and `docker compose` work on a fresh clone.
2. Complete the Phase-1 QS validation checkpoint and flip at least the critical risk patterns to `confidence: validated`, or add a beta flag that lets paid users see unvalidated patterns with a clear disclaimer.
3. Wire real integrations and make the app refuse to run in production when email/payment credentials are absent; never return password-reset or invitation tokens in API responses.
4. Add authentication and workspace binding to `tus PATCH`, `tus HEAD`, and the Celery SSE stream; enforce per-type size caps during tus chunking.
5. Replace the virus-scan stub with a sandboxed scanner or cloud API; make S3 I/O non-blocking; add `GET /api/files/{key}` or fix local URL generation.
6. Add Playwright E2E, accessibility, and load tests to CI.
7. Add production operations: IaC, backups, monitoring, alerting, and runbooks.

---

## 2. System and Audit Overview

### 2.1 Architecture

TenderShield is a modular FastAPI monolith with a Next.js 15 SPA.

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, Celery (optional Redis broker), APScheduler (optional), DuckDB in-memory analytics.
- **Frontend:** Next.js 15, React 19, TypeScript (strict), Tailwind CSS.
- **Storage:** Local filesystem by default; optional S3-compatible object store.
- **Database:** SQLite for tests/dev; PostgreSQL (with RLS workspace isolation) for production.
- **Payments:** Razorpay (India) and Stripe (GCC/UK) via webhook-verified activation.
- **Notifications:** SES/MSG91 with console fallback; deadline digest scheduler.

Modules are self-contained under `backend/app/modules/<name>/`. Cross-module interaction is through `app.core.registry` capabilities and `app.core.events`; modules do not import each other directly. This architecture was verified by `test_architecture.py` and the full test suite.

### 2.2 Roles and trust boundaries

| Role | Capabilities |
|---|---|
| anonymous | sign up, log in, view public health, accept invitation, reset password, view rulepacks |
| viewer | view opportunities, deadlines, findings, baselines, invoices, billing status |
| reviewer | accept/reject findings |
| estimator | create opportunities, upload documents, run BOQ/risk, freeze baselines |
| admin | invite members, manage billing/checkout, manage project membership |
| owner | full workspace admin |
| superadmin | admin console: list all users/workspaces, toggle superadmin flag |

Trust boundaries:
- JWT access token carries `user_id`, `workspace_id`, `role`, `is_superadmin`.
- PostgreSQL RLS uses `SET LOCAL app.workspace_id` on every authenticated request via `bind_workspace_context`.
- Refresh tokens are RS256-signed short-lived JWTs stored as SHA256 hashes; rotation and reuse detection are implemented.

### 2.3 Files, routes, APIs and workflows reviewed

- **Entry points:** `backend/app/main.py`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`.
- **Auth:** `backend/app/modules/auth/router.py`, `service.py`, `security.py`, `refresh.py`, `mfa.py`, `deps.py`, `rbac.py`.
- **Ingestion:** `backend/app/modules/ingestion/router.py`, `tus.py`, `service.py`, `extract.py`, `tasks.py`, `models.py`.
- **Risk/BOQ/Review/Export:** `backend/app/modules/{risk,boq,review,export,findings,drafting}/`.
- **Billing:** `backend/app/modules/billing/{router.py,providers.py,plans.py,service.py}`.
- **Notifications:** `backend/app/modules/notifications/{adapters.py,module.py}`.
- **Storage:** `backend/app/core/storage.py`.
- **Frontend pages:** `frontend/app/{login,opportunities,opportunities/[id],billing,admin,analytics,help,standards,forgot-password,reset-password}/page.tsx`.
- **Frontend shared:** `frontend/components/{session.tsx,header-actions.tsx,badges.tsx}`, `frontend/lib/api.ts`.
- **CI/CD:** `.github/workflows/ci.yml`, `scripts/run.sh`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.
- **Migrations:** `backend/migrations/versions/e26e85245237_workspace_tenant.py` and successors.

### 2.4 Commands and tests executed

All commands were run from a clean checkout using the environment blueprint.

```text
# Backend
/home/ubuntu/.pyenv/versions/3.11.11/bin/python -m venv backend/.venv
backend/.venv/bin/pip install -e "backend/.[dev,celery,auth,billing,storage,redis,scheduler]"
cd backend && .venv/bin/ruff check . --target-version py311
# All checks passed!

.venv/bin/mypy app
# Success: no issues found in 143 source files

.venv/bin/pytest -q
# 145 passed, 1 skipped, 1 warning in 21.53s

.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade base
.venv/bin/alembic upgrade head
# all clean

# Frontend
cd frontend && npm install
npm run lint
# clean

npm run typecheck
# tsc --noEmit, exit 0

npm run build
# 13 static/dynamic pages built successfully

npm audit --audit-level=moderate
# found 0 vulnerabilities

# Python dependencies
backend/.venv/bin/pip freeze > /tmp/requirements.txt
backend/.venv/bin/pip-audit -r /tmp/requirements.txt --no-deps
# No known vulnerabilities found
```

**Skipped/unavailable checks:** secret scanning (`truffleHog`/`gitleaks` not installed in the environment), browser E2E, accessibility, load/performance, live third-party integration smoke tests, and infrastructure-as-code review.

### 2.5 Assumptions and exclusions

- The repository is the authoritative source of truth for the application; any external secrets, infrastructure, or managed services were not audited.
- Live LLM/OCR behaviour was inferred from code and unit tests; accuracy was not measured against a held-out tender corpus.
- Rulepack accuracy and legal/QS validity were not validated; the report relies on the `confidence:` field and the Build Doc §14 validation plan.
- Mobile native apps, browser extensions, and third-party marketplace integrations are out of scope.

---

## 3. Product Completeness

### 3.1 Role-to-Capability Matrix

| Capability | Anonymous | Viewer | Reviewer | Estimator | Admin | Owner | Superadmin |
|---|---|---|---|---|---|---|---|
| Sign up / log in | ✅ | — | — | — | — | — | — |
| MFA challenge | ✅ | — | — | — | — | — | — |
| View opportunities | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Create opportunity | — | — | — | ✅ | ✅ | ✅ | — |
| Upload tender document | — | — | — | ✅ | ✅ | ✅ | — |
| Run risk review | — | — | — | ✅ | ✅ | ✅ | — |
| Run BOQ check | — | — | — | ✅ | ✅ | ✅ | — |
| Accept/reject findings | — | — | ✅ | ✅ | ✅ | ✅ | — |
| Generate artifacts | — | — | — | ✅ | ✅ | ✅ | — |
| Export bid-review pack | — | — | — | ✅ | ✅ | ✅ | — |
| Freeze baseline | — | — | — | ✅ | ✅ | ✅ | — |
| Invite workspace/project members | — | — | — | — | ✅ | ✅ | — |
| Manage billing / checkout | — | — | — | — | ✅ | ✅ | — |
| View admin console | — | — | — | — | — | — | ✅ |
| Switch workspace | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View audit trail | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Receive deadline alerts | — | ✅ | ✅ | ✅ | ✅ | ✅ | — |

### 3.2 Entity-to-Operation Matrix

| Entity | Create | List/Search | View | Update | Delete/Archive | Import | Export | Audit |
|---|---|---|---|---|---|---|---|---|
| User | ✅ (signup) | ❌ | ✅ (me) | ✅ (password, MFA) | ❌ | ❌ | ❌ | partial |
| Workspace | ✅ | ✅ | ✅ | partial | ❌ | ❌ | ❌ | partial |
| Project | ✅ | ✅ | ✅ | partial | ❌ | ❌ | ❌ | partial |
| Opportunity | ✅ | ✅ | ✅ | partial | ❌ | ❌ | ❌ | partial |
| Document | ✅ (upload) | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | partial |
| Deadline | auto | ✅ | ✅ | ✅ (confirm) | ❌ | ❌ | ❌ | partial |
| Finding | auto | ✅ | ✅ | ✅ (review) | ❌ | ❌ | ✅ (pack) | ✅ |
| Artifact | ✅ (generate) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | partial |
| Baseline | ✅ (freeze) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | partial |
| Invoice/Payment | auto | ✅ | ✅ | auto | ❌ | ❌ | ❌ | partial |
| RulePack | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Standard/Notice | ❌ | ✅ | ✅ | partial | ❌ | ❌ | ❌ | ❌ |

### 3.3 Workflow Completeness Matrix

| Workflow | Entry | Auth | Validation | Complete | Failure | Cancel | Retry | Recovery | Notifications | History | Admin |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sign up / on-board | `/login` | ✅ | ✅ password policy | access + workspace | generic error | — | — | — | ❌ no welcome email | audit log | view users |
| Upload tender | opportunity page | ✅ | ext/magic/size | doc + text extracted | 422/500 | abort | tus resumable | re-upload | ❌ none | audit log | — |
| Risk review | opportunity page | ✅ | paywall | findings list | empty (paid) | — | rerun | — | ❌ none | audit log | — |
| BOQ check | opportunity page | ✅ | CSV/table | findings list | 400/422 | clear CSV | rerun | — | ❌ none | audit log | — |
| Review findings | opportunity page | ✅ | decision enum | gate unlock | — | — | — | — | ❌ none | ✅ audit log | view audit |
| Generate artifacts | opportunity page | ✅ | gate | artifact created | 402/403 | — | regen | — | ❌ none | audit log | — |
| Export pack | opportunity page | ✅ | gate | docx/xlsx/pdf | 403 | — | retry | — | ❌ none | audit log | — |
| Invite member | `/admin` or API | ✅ | email/role | member added | token leak | — | resend | — | ❌ console only | audit log | manage |
| Billing checkout | `/billing` | ✅ | plan/amount | order/session | mock fallback | — | retry | poll status | ❌ none | invoices | view invoices |
| Workspace switch | header | ✅ | membership | new token | 403 | — | — | — | ❌ none | audit log | — |
| Deadline alert | scheduler | ✅ (system) | due window | email sent | console fallback | — | next run | — | ✅ email | — | — |

### 3.4 Dashboard and Reporting Matrix

| Screen | Status | Notes |
|---|---|---|
| Landing/marketing page | ✅ | No false India-hosting claim; clear value prop |
| Login / MFA | ✅ | TOTP and email/SMS code flows wired |
| Opportunities board | ✅ | `/opportunities` |
| Opportunity workbench | ✅ | Tabs: overview, risks, BOQ, artifacts, handover, audit |
| Billing page | ✅ | Plan, usage, invoices, checkout CTAs |
| Admin console | ✅ | Users + workspaces, toggle superadmin |
| Analytics page | ✅ | DuckDB-based dashboards |
| Help page | ✅ | Static help |
| Standards page | ✅ | View pack standards |
| Organisation-wide risk dashboard | ❌ | Not implemented |
| Manager / team workload queue | ❌ | Not implemented |
| DPDP/GDPR data export/delete | ❌ | Not implemented |
| Per-tender activity/notification feed | ❌ | Not implemented |

### 3.5 Missing capabilities

1. **Email verification flow** — `User.email_verified` exists but is never checked.
2. **Document viewer / download** — Uploaded files are stored, but there is no `GET /api/files/{key}` endpoint and no document preview in the UI.
3. **DPDP/GDPR data export and deletion endpoints** — Required for India/UK/EU compliance.
4. **Real-time / WhatsApp alerts** — Only email adapter exists; MSG91 SMS is stubbed.
5. **Team workload / review queue dashboard** — No aggregated pending-actions view.
6. **Mobile-optimised upload flow** — UI is responsive but not tested for mobile tender capture.
7. **Offline / degraded-mode UX** — No explicit network-failure or retry UI beyond generic `catch` messages.

### 3.6 Product decisions required

1. **Rulepack validation strategy** — Run the Phase-1 QS checkpoint, or allow paying users to see unvalidated patterns with a "beta / unverified" badge?
2. **Regional currency** — Should Stripe use `INR` for India, `AED` for GCC, `GBP` for UK based on `Workspace.country`?
3. **Document access** — Add a per-document download endpoint, an in-app preview, or rely only on generated artifacts?
4. **Email verification** — Gate login, password reset, billing, or only sensitive actions?
5. **Free-tier watermarking** — The backend `Grant.watermark=True` exists; is the export watermark applied in rendered documents?
6. **Unvalidated-pattern exposure for free users** — Free users currently see all patterns (including unvalidated). Is this acceptable given the "no paid reliance" rule?

---

## 4. Detailed Findings

### 4.1 Previously reported findings that are now mitigated

| ID | Prior title | Status | Evidence of mitigation |
|---|---|---|---|
| F01 | Default CORS wildcard in production | Resolved | `backend/app/main.py:51-62` rejects `TS_CORS_ORIGINS="*"` in prod; `config.py` uses `TS_CORS_ORIGINS` with explicit split. |
| F02 | Default Razorpay webhook secret enables forgery | Resolved | `backend/app/core/config.py:43` — `razorpay_webhook_secret` is `SecretStr \| None = None`; `main.py:57-58` requires it in prod. |
| F04 | MFA enroll-only / not enforced at login | Resolved | `backend/app/modules/auth/service.py:149-168` requires MFA when configured; `/api/auth/mfa/challenge` in `auth/router.py`; frontend handles MFA in `frontend/app/login/page.tsx:37-41`. |
| F05 | Access token in localStorage / no refresh rotation | Resolved | `frontend/components/session.tsx` keeps access token in memory; refresh token is `httpOnly` cookie; `auth/refresh.py` implements rotation + reuse detection. |
| F06 | Login/refresh select first workspace | Resolved | `backend/app/modules/auth/router.py:355-388` `/workspaces/{id}/switch` returns new access token for selected workspace; `frontend/components/header-actions.tsx` exposes switcher. |
| F08 | No rate limiting on auth/billing | Resolved | `backend/app/core/ratelimit.py` sliding-window limiter; applied in `auth/router.py` and `billing/router.py` with `Depends(RateLimitDep(...))`. |
| F09 | File upload lacks validation / sync processing | Resolved | `backend/app/core/storage.py:191-269` validates extension, magic bytes, size, SHA256 key; `ingestion/router.py:112-181` supports `?async=1` with Celery. |
| F10 | Missing HTTPS/security headers | Resolved | `backend/app/main.py:27-49` adds `SecurityHeadersMiddleware` (CSP, X-Frame-Options, etc.) and `HTTPSRedirectMiddleware`/`TrustedHostMiddleware` in prod. |
| F11 | LocalStorage only file adapter | Resolved | `backend/app/core/storage.py:124-183` adds `S3Storage`; selected by `TS_STORAGE_TYPE=s3`. |
| F13 | npm audit high-severity vulnerabilities | Resolved | `npm audit --audit-level=moderate` → `found 0 vulnerabilities`; `pip-audit` → `No known vulnerabilities found`. |
| F16 | Frontend SAMPLE data / missing billing/admin pages | Resolved | `frontend/app/page.tsx` no sample data; `frontend/app/admin/page.tsx`, `billing/page.tsx`, `analytics/page.tsx` added. |
| F17 | Export lacks reviewer signature/date | Resolved | `backend/app/modules/export/service.py:86-125` stamps `reviewed_by_email` and `reviewed_at`; `review/service.py:102-123` computes last reviewer from audit log; integrity hash re-rendered. |
| F18 | No ESLint/mypy strict gates in CI | Resolved | `.github/workflows/ci.yml` runs `ruff`, `mypy app`, `pip-audit`, `pytest`, Alembic up/down, `npm run lint`, `npm run typecheck`, `npm audit`, `npm run build`. |
| F21 | No admin console beyond raw endpoints | Resolved | `frontend/app/admin/page.tsx` lists users/workspaces and toggles `is_superadmin`. |
| F22 | Weak password policy / no lockout | Resolved | `backend/app/modules/auth/security.py:33-50` enforces 8+ chars, upper/lower/digit/symbol, common-password block; Argon2id used; `auth/service.py:124-134` locks account after 5 failed attempts. |
| F23 | Health endpoint exposes internals publicly | Resolved | `backend/app/modules/health/router.py:29-54` split: public `/api/health` and authenticated `/api/health/details`; prod details require superadmin. |
| F24 | Landing page false "Hosted in India" claim | Resolved | `frontend/app/page.tsx` no longer contains a hosting/data-residency claim. |
| F25 | `datetime.utcnow()` usage | Resolved | `grep -r "utcnow" backend/app` returns no matches; `datetime.now(UTC)` used throughout. |

### 4.2 Remaining and new findings

---

#### F26 — Missing `.env.local`, `.env.dev`, `.env.prod`; run script and Docker Compose fail on a clean clone

| Field | Value |
|---|---|
| Severity | High |
| Category | DevOps / Deployment readiness |
| Release-blocking | Yes |
| Affected roles | All users, operators, CI deploys |
| Affected files/routes | `scripts/run.sh:13-16`, `docker-compose.yml:25`, `docs/deployment.md:5-11`, `tasks/backlog.md` (TS-089), `.gitignore:19-21` |

**Evidence and reproduction:**

```text
$ find . -maxdepth 2 -name '.env*' -type f | sort
./.env.example
```

`scripts/run.sh` does:

```bash
ENV=${1:-local}
ENV_FILE=".env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
    echo "Missing env file: $ENV_FILE" >&2
    exit 1
fi
```

`docker-compose.yml:25` references `env_file: [.env.local]`. `docs/deployment.md` and `CHANGELOG.md` (TS-089) state the three env files exist.

**Root cause:** The files are listed in `.gitignore` (`.env.*` with `!.env.example`) and were never committed, but documentation/scripts assume they are present.

**Impact:** A new engineer or CI pipeline cannot run the local stack; `docker compose` fails; the repository is not self-bootstrapping.

**Recommended solution:**

1. Create safe, non-secret `.env.local`/`.env.dev`/`.env.prod` templates (placeholders for secrets, local SQLite/Postgres defaults, `localhost` CORS, `dev`/`prod` env).
2. Update `.gitignore`:
   ```gitignore
   .env
   .env.local
   .env.dev
   .env.prod
   !.env.example
   ```
3. Or commit `.env.local.example`/`.env.dev.example`/`.env.prod.example` and make `run.sh` fall back to `.env.${ENV}.example` if the real file is missing.

**Verification:** Clone repo to a fresh directory, run `./scripts/run.sh local` and `docker compose --env-file .env.local up --build` successfully.

**Similar locations:** `backend/Dockerfile`, `frontend/Dockerfile`, `README.md` quick-start.

---

#### F27 — Every rulepack pattern is still `confidence: unvalidated`; paying workspaces receive zero validated risk findings

| Field | Value |
|---|---|
| Severity | Critical |
| Category | Product correctness / Business logic |
| Release-blocking | Yes |
| Affected roles | All paid users (pro, scale, paygo) |
| Affected files/routes | `backend/app/modules/risk/service.py:36-65`, `backend/app/modules/rulepacks/loader.py:134-138`, `rulepacks/in-works/risk_patterns/*.yaml:4`, `rulepacks/in-works/boq/trade_checklists/*.yaml:4-5`, `rulepacks/in-works/pack.yaml:8-10`, `docs/TenderShield_Full_Build_Doc.md:773-776,916` |

**Evidence and reproduction:**

All `confidence:` values in the shipped `in-works` pack are `unvalidated`:

```text
$ grep -R "^confidence:" rulepacks/in-works/
confidence: unvalidated
... (every file)
```

`loader.py` filters paying users to validated only:

```python
def list_patterns(self, pack_id: str, *, validated_only: bool = False) -> list[RiskPattern]:
    patterns = self.get_pack(pack_id).patterns.values()
    if validated_only:
        return [p for p in patterns if p.confidence == "validated"]
    return list(patterns)
```

`risk/service.py` sets `validated_only = True` for paying workspaces:

```python
def _is_paying(self, workspace_id) -> bool:
    ...
    return self._workspace_factory(self.session).is_paying(workspace_id)

def run_opportunity(self, workspace_id, opportunity_id) -> list[Finding]:
    validated_only = self._is_paying(workspace_id)
    patterns = self._loader.list_patterns(self._pack_id, validated_only=validated_only)
    ...
```

The existing test `test_risk.py` uses a free workspace (`plan: "free"`), so it does not exercise the paying path.

**Root cause:** The Phase-1 QS validation checkpoint (Build Doc §14.2–14.3) has not been completed; the code correctly enforces the validation gate but the data is not yet valid.

**Impact:** Any workspace that upgrades to a paid plan will get an empty risk register. This violates the product value proposition and the documented Phase-1 exit gate: "all patterns shown to paying users are `validated`". It also creates a liability gap: free users see unvalidated patterns, while paid users see nothing.

**Recommended solution:**

1. Run the Phase-1 validation checkpoint with a retained QS/contracts manager on 8–10 real tenders.
2. Flip vetted patterns to `confidence: validated` in their YAML files.
3. Add a CI-eval job (`scripts/phase0_accuracy_test.py` or similar) with a golden tender corpus; block merge if F1 on deadlines or risk recall drops.
4. Until validation is complete, add a feature flag / workspace setting that lets paid users optionally see unvalidated patterns clearly tagged "beta — unverified, confirm independently" (per Build Doc §14.3). Change `RiskService.run_opportunity` to respect that flag.

**Code example (illustrative):**

```python
# backend/app/modules/risk/service.py
class RiskService:
    def run_opportunity(self, workspace_id, opportunity_id) -> list[Finding]:
        if not self._loader:
            return []
        # Respect an explicit beta flag per workspace; otherwise validated-only for paying.
        show_beta = self._workspace_factory(self.session).show_beta_risk_patterns(workspace_id)
        validated_only = self._is_paying(workspace_id) and not show_beta
        patterns = self._loader.list_patterns(self._pack_id, validated_only=validated_only)
        ...
```

**Verification:** Create a pro workspace, upload a tender with known risky clauses, run `/api/risk/opportunities/{id}/run`, and assert non-empty findings. Add a paying-workspace test to `test_risk.py`.

**Regression risks:** Changing the validation logic must not accidentally expose unvalidated patterns to paying users without the beta badge; ensure the flag defaults to validated-only.

---

#### F28 — Password-reset and invitation tokens leak through unconfigured integrations; checkout accepts mock money

| Field | Value |
|---|---|
| Severity | High |
| Category | Security / Authentication / Payments |
| Release-blocking | Yes |
| Affected roles | All users when email/payment credentials are absent |
| Affected files/routes | `backend/app/modules/auth/service.py:705-728` (`forgot_password`), `backend/app/modules/auth/service.py:486-506` (`create_invitation`), `backend/app/modules/notifications/adapters.py:21-38`, `backend/app/modules/billing/providers.py:33-45,76-91`, `/api/auth/forgot-password`, `/api/auth/invitations`, `/api/billing/checkout` |

**Evidence and reproduction:**

`forgot_password` returns the raw token when the sender is `ConsoleSender` (the default when SES/MSG91 are not configured):

```python
def forgot_password(self, email: str) -> dict:
    ...
    if self._sender and self._sender.__class__.__name__ != "ConsoleSender":
        self._sender.send(...)
        return {"ok": True}
    # dev/test fallback: return the token so UI tests can proceed without email
    return {"ok": True, "token": raw}
```

`create_invitation` always returns the raw token:

```python
return {"token": token, "expires_at": expires_at.isoformat()}
```

`RazorpayProvider.create_order` and `StripeProvider.create_session` return mock `order_id`/`session_id` when keys are absent:

```python
def create_order(self, amount_minor: int, currency: str, notes: dict) -> dict:
    if not self._client:
        return {"provider": "razorpay", "order_id": f"order_mock_{uuid.uuid4().hex[:12]}", ...}
```

**Root cause:** The application is designed to degrade gracefully for local development, but there is no production guard that refuses these fallback paths when `TS_ENV=prod`.

**Impact:** If an operator deploys to production without configuring SES/MSG91 or Razorpay/Stripe keys, the API will expose password-reset and invitation tokens and accept non-existent payments. This is a broken access-control / financial-integrity issue.

**Recommended solution:**

1. In production (`settings.is_prod()`), raise at startup if `TS_RAZORPAY_KEY_ID`/`TS_RAZORPAY_KEY_SECRET` or `TS_STRIPE_SECRET_KEY` are missing (for the relevant `Workspace.country`).
2. In `forgot_password`, never return the token. Send it only via the configured sender. If no sender is configured in production, return `503` or log an error.
3. In `create_invitation`, do not return the token. Send it by email/SMS; if that fails, return a generic `ok` and a `delivery_pending` flag.
4. In `billing/providers.py`, if `settings.is_prod()` and the client cannot be initialised, raise rather than return a mock.

**Code example (illustrative):**

```python
# backend/app/modules/auth/service.py
def forgot_password(self, email: str) -> dict:
    ...
    if not self._sender or self._sender.__class__.__name__ == "ConsoleSender":
        if self._settings.is_prod():
            raise AuthError("email_not_configured")
        # dev/test: log token to console only (never HTTP body)
        logger.info("[dev] password reset token for %s: %s", email, raw)
        return {"ok": True}
    self._sender.send(...)
    return {"ok": True}
```

**Verification:**

- `pytest` with `Settings(TS_ENV="prod")` and no email keys: `POST /api/auth/forgot-password` returns `503` and no token.
- `pytest` with prod and no payment keys: `POST /api/billing/checkout` returns `503`.

**Regression risks:** Existing dev/tests that rely on the fallback will need explicit test-only configuration (`Settings(env="dev")`) or test stubs.

---

#### F29 — Virus scanning is a stub; S3 I/O blocks the async loop; BOQ upload skips the scan

| Field | Value |
|---|---|
| Severity | High |
| Category | Security / File upload / Performance |
| Release-blocking | Yes |
| Affected roles | All users uploading files; operators running S3 |
| Affected files/routes | `backend/app/core/storage.py:156-173` (S3 sync calls), `backend/app/core/storage.py:186-188` (`_scan_stub`), `backend/app/modules/boq/router.py:73-81` (`scan=False`), `backend/app/core/storage.py:259-260` (dead local URL), `/api/ingestion/opportunities/{id}/upload`, `/api/ingestion/tus/{id}`, `/api/boq/opportunities/{id}/upload` |

**Evidence and reproduction:**

```python
def _scan_stub(_data: bytes) -> None:
    """Placeholder virus scan. Production should call a sandboxed scanner or API."""
    return
```

`S3Storage` methods are `async` but call synchronous boto3:

```python
async def write(self, key: str, data: bytes, content_type: str) -> str:
    full = self._full_key(key)
    self.client.put_object(Bucket=self.bucket, Key=full, Body=data, ContentType=content_type)
    return full
```

BOQ upload disables the scan:

```python
await validate_and_store(
    ...,
    scan=False,  # BOQ CSV text is generated locally; no user-executable upload here
    ...
)
```

(The comment is incorrect: `data` is the original uploaded PDF/XLSX/CSV bytes.)

`validate_and_store` also returns `url = await storage.url(stored_key) or f"/api/files/{stored_key}"` for local storage, but no `/api/files/{key}` route exists.

**Root cause:** Security and async I/O are not production-hardened; the S3 implementation was added quickly without non-blocking I/O; the BOQ route misinterpreted the `scan` flag.

**Impact:** Malware can reach storage; large S3 uploads/downloads block the event loop; BOQ files bypass malware scanning; local file URLs are dead.

**Recommended solution:**

1. Integrate a sandboxed virus scanner (ClamAV daemon, `clamdasync`, or a cloud API) and call it in `validate_and_store` before writing.
2. Run boto3 calls in a threadpool (`asyncio.to_thread(...)`) or switch to `aiobotocore`.
3. Remove `scan=False` from `boq/router.py`.
4. Implement `GET /api/files/{key}` (RLS-bound, content-type aware) or make `LocalStorage.url` return a route that exists.

**Code example (illustrative for S3):**

```python
# backend/app/core/storage.py
import asyncio

async def write(self, key: str, data: bytes, content_type: str) -> str:
    full = self._full_key(key)
    await asyncio.to_thread(
        self.client.put_object,
        Bucket=self.bucket, Key=full, Body=data, ContentType=content_type,
    )
    return full
```

**Verification:** Upload an EICAR test file and assert `ValidationError` / `VirusScanError`; benchmark a 50 MB PDF upload under load and confirm non-blocking behaviour.

**Regression risks:** Adding real scanning will increase upload latency; make it async and add a `scan_status` column if needed.

---

#### F30 — tus resumable upload has no authentication and no chunk-level size cap

| Field | Value |
|---|---|
| Severity | High |
| Category | Security / File upload / DoS |
| Release-blocking | Yes |
| Affected roles | Anyone who can guess/obtain an upload ID |
| Affected files/routes | `backend/app/modules/ingestion/tus.py:81-145`, `PATCH /api/ingestion/tus/{upload_id}`, `HEAD /api/ingestion/tus/{upload_id}` |

**Evidence and reproduction:**

`tus_create` requires `require("estimator")`, but `tus_patch` and `tus_status` have no authentication or workspace binding:

```python
@router.patch("/{upload_id}")
async def tus_patch(
    upload_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    session: Session = Depends(get_session),
):
    state = _load_state(upload_id)
    if upload_offset != state["offset"]:
        raise HTTPException(409, "offset_conflict")
    data = await request.body()
    file_path = _file_path(upload_id)
    with file_path.open("ab") as f:
        f.write(data)
    ...
```

There is no `Upload-Length` validation against per-type max sizes at creation, and no cumulative-size check during `PATCH`. The chunks are appended to `/tmp/tender-shield-tus/`.

**Root cause:** The tus implementation is minimal; auth and size enforcement were not carried from the multipart upload endpoint.

**Impact:** An unauthenticated attacker who obtains an upload ID can append arbitrary data, corrupt another user's upload, or exhaust disk space. The endpoint is also a DoS vector.

**Recommended solution:**

1. Add `Depends(require("estimator"))` to `tus_patch` and `tus_status`.
2. Verify `state["workspace_id"] == principal.workspace_id` in `tus_patch`.
3. Validate `Upload-Length` against `MAX_UPLOAD_SIZES` in `tus_create` and store the cap in state.
4. In `tus_patch`, reject chunks that would exceed the cap.

**Code example (illustrative):**

```python
# backend/app/modules/ingestion/tus.py
@router.patch("/{upload_id}")
async def tus_patch(
    upload_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    state = _load_state(upload_id)
    if str(principal.workspace_id) != state["workspace_id"]:
        raise HTTPException(403, "workspace_mismatch")
    if state["length"] and upload_offset + len(await request.body()) > state["length"]:
        raise HTTPException(413, "upload_too_large")
    ...
```

**Verification:** `pytest` unauthenticated `PATCH /api/ingestion/tus/{id}` returns 401/403; oversized `Upload-Length` returns 413.

---

#### F31 — Stripe checkout is hardcoded to INR regardless of workspace country

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Business logic / Internationalisation |
| Release-blocking | No (India-only launch blocker if Stripe unused) |
| Affected roles | GCC/UK paying users |
| Affected files/routes | `backend/app/modules/billing/router.py:67-71`, `backend/app/modules/billing/providers.py:76-120`, `/api/billing/checkout` |

**Evidence and reproduction:**

```python
provider = request.app.state.ctx.registry.get("billing.provider_factory")(body.provider)
if body.provider == "stripe":
    result = provider.create_session(amount, "INR", notes)
else:
    result = provider.create_order(amount, "INR", notes)
```

`Workspace.country` supports `("IN", "AE", "SA", "QA", "GB")`. The Build Doc §15 specifies a checkout modal that "picks provider by org.country: IN→Razorpay, AE/SA/QA/GB→Stripe" with appropriate currencies.

**Root cause:** The billing router passes a constant `"INR"` to both providers.

**Impact:** UAE/UK customers will be charged in Indian Rupees, breaking pricing and tax expectations.

**Recommended solution:**

Map `country` to currency and default provider:

```python
# backend/app/modules/billing/router.py
def _currency_for_country(country: str) -> str:
    return {"IN": "inr", "AE": "aed", "SA": "sar", "QA": "qar", "GB": "gbp"}.get(country, "inr")

def _default_provider(country: str) -> str:
    return "razorpay" if country == "IN" else "stripe"
```

Then pass `currency = _currency_for_country(workspace.country)` to `create_order`/`create_session`.

**Verification:** `pytest` for a `GB` workspace checkout creates a Stripe session in `gbp`.

---

#### F32 — `mypy` disables most error codes, reducing static type safety

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Code quality / Type safety |
| Release-blocking | No |
| Affected roles | Developers |
| Affected files/routes | `backend/pyproject.toml:79` |

**Evidence:**

```toml
disable_error_code = ["attr-defined", "arg-type", "union-attr", "valid-type", "operator", "index", "assignment", "name-defined", "annotation-unchecked"]
ignore_missing_imports = true
```

**Root cause:** The project disabled many mypy error categories to pass type checking, likely to accommodate incomplete types.

**Impact:** Type errors that could catch bugs at build time are silently ignored; CI `mypy app` passing is not strong evidence of type safety.

**Recommended solution:**

1. Remove `disable_error_code` entries one category at a time and fix the reported issues.
2. Keep `ignore_missing_imports` for third-party packages without stubs.
3. Consider using `pydantic.mypy` plugin and `strict = true` gradually.

**Verification:** After removing each code, `mypy app` is clean; no new runtime regressions.

---

#### F33 — Frontend tender upload `accept` list includes file types rejected by the backend

| Field | Value |
|---|---|
| Severity | Low |
| Category | UX / Frontend validation |
| Release-blocking | No |
| Affected roles | Estimators uploading tenders |
| Affected files/routes | `frontend/app/opportunities/[id]/page.tsx:179` |

**Evidence:**

```tsx
<input
  type="file"
  accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx,.xls"
  ...
/>
```

`backend/app/core/storage.py:19-31` `ALLOWED_UPLOAD_EXTENSIONS`:

```python
ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".zip",
}
```

`.doc`, `.txt`, and `.md` are not allowed. The user can select them but will receive a `422 file_type_not_allowed` from the backend.

**Recommended solution:** Align the frontend `accept` attribute with `ALLOWED_UPLOAD_EXTENSIONS`. If `.doc`/`.txt`/`.md` are product requirements, add them to the backend allow-list and converters.

**Verification:** Select a `.txt` file in the UI and verify it is rejected before upload or supported end-to-end.

---

#### F34 — `email_verified` is stored but never enforced

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Security / Account lifecycle |
| Release-blocking | No (for MVP) / Yes for compliance-sensitive launch |
| Affected roles | All signed-up users |
| Affected files/routes | `backend/app/modules/auth/models.py:27`, `backend/app/modules/auth/service.py` (signup/login) |

**Evidence:**

`User.email_verified` defaults to `False`. No verification email is sent, and login, password reset, billing, or member invitation do not check it.

**Impact:** Account takeover via unverified email addresses; password reset to a typo/unowned email; incorrect notifications.

**Recommended solution:**

1. Send a verification email with a time-limited token on sign-up.
2. Set `email_verified=True` after token confirmation.
3. Optionally gate billing/checkout and member invitation on `email_verified`.

**Verification:** Sign up with an unverified email; attempt a sensitive action and receive a `403 email_not_verified`.

---

#### F35 — No end-to-end, accessibility, or performance tests

| Field | Value |
|---|---|
| Severity | Low (currently) / Medium (at scale) |
| Category | QA / UX / Accessibility |
| Release-blocking | No for internal launch; Yes for public launch |
| Affected roles | All users |
| Affected files/routes | `.github/workflows/ci.yml`, `frontend/package.json` |

**Evidence:** No Playwright/Cypress tests, no `axe-core`/Lighthouse CI steps, no load tests. `npm run build` and `pytest` are unit/integration only.

**Impact:** Critical user journeys (signup → upload → review → export) are not automatically verified; accessibility violations may exist; performance regressions are not caught.

**Recommended solution:**

1. Add Playwright E2E covering: sign-up, workspace switch, tender upload, risk review, accept/reject findings, export.
2. Add `axe-core` or `@axe-core/react` checks.
3. Add Lighthouse CI budget for First Contentful Paint / Time to Interactive.

**Verification:** New E2E tests pass in CI; Lighthouse scores ≥90 for key pages.

---

#### F36 — Production operations (IaC, backups, monitoring, runbooks) are not present

| Field | Value |
|---|---|
| Severity | Medium (becomes High at scale) |
| Category | DevOps / SRE |
| Release-blocking | No for design-partner staging; Yes for production |
| Affected roles | Operators |
| Affected files/routes | `docs/deployment.md`, `.github/workflows/ci.yml` |

**Evidence:** No Terraform/CDK, no Kubernetes/ECS manifests, no backup/restore scripts, no Prometheus/Datadog config, no PagerDuty/alerting, no RTO/RPO runbooks. `docs/deployment.md` describes Docker only.

**Impact:** No reproducible infrastructure, no disaster recovery, no incident response, no SLO monitoring.

**Recommended solution:**

1. Add Terraform/CDK for AWS/GCP infra (Postgres, Redis, S3, ECS/Fargate or Kubernetes).
2. Add automated nightly DB backups and S3 cross-region replication.
3. Add structured logging, metrics (Prometheus/OpenTelemetry), and alerts for error rate, p95 latency, deadline-alert failures, Celery queue depth.
4. Write runbooks for restore, rollback, and breach notification.

**Verification:** Deploy to staging via IaC; run backup restore drill; verify alerts fire on synthetic failures.

---

#### F37 — Deadline-alert scheduler runs in-process and will duplicate in multi-instance deployments

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Reliability / Scaling |
| Release-blocking | No for single-instance staging; Yes for multi-instance production |
| Affected roles | All users |
| Affected files/routes | `backend/app/core/scheduler.py`, `backend/app/modules/notifications/module.py:56` |

**Evidence:**

```python
scheduler.add_job(_deadline_alert_tick, "interval", hours=24)
```

The scheduler uses APScheduler in-process when installed. There is no leader election or distributed locking. If two backend containers run, both will scan and email the same deadlines.

**Impact:** Duplicate deadline-alert emails; duplicate work in any scaled-out deployment.

**Recommended solution:**

Use Celery Beat with a single scheduler lock in Redis, or implement a leader-election lease in Postgres/Redis.

**Verification:** Run two backend instances and verify only one sends alerts per window.

---

#### F38 — S3 storage silently falls back to local filesystem on init failure

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Reliability / Data residency |
| Release-blocking | No (if local fallback is acceptable) |
| Affected roles | Operators |
| Affected files/routes | `backend/app/core/storage.py:176-183` |

**Evidence:**

```python
def get_storage(settings: Settings) -> StorageBackend:
    if settings.storage_type == "s3":
        try:
            return S3Storage(settings)
        except Exception as exc:
            logger.warning("s3 storage failed, falling back to local: %s", exc)
    root = pathlib.Path(settings.storage_dir)
    return LocalStorage(root)
```

**Impact:** If `TS_STORAGE_TYPE=s3` but credentials are wrong, the app silently writes files to local disk, breaking durability, data-residency promises, and URL generation (local URLs are dead — see F40).

**Recommended solution:** In production (`settings.is_prod()`), raise `StorageError` if S3 initialisation fails. Fallback to local only in `dev`.

**Verification:** Set `TS_STORAGE_TYPE=s3` with invalid keys in prod; app fails to start with a clear error.

---

#### F39 — Rulepack list/patterns endpoints are public

| Field | Value |
|---|---|
| Severity | Low |
| Category | Information disclosure |
| Release-blocking | No |
| Affected roles | Anonymous users |
| Affected files/routes | `backend/app/modules/rulepacks/router.py:10-45`, `/api/rulepacks`, `/api/rulepacks/{id}/patterns` |

**Evidence:** `rulepacks/router.py` has no `Depends(require(...))` dependencies. Any visitor can list pack metadata and pattern titles/sources.

**Impact:** Low (no sensitive data), but exposes internal rule taxonomy and source references to competitors.

**Recommended solution:** Add `Depends(require("viewer"))` to both routes, or add a public "catalog" subset and a protected admin subset.

**Verification:** `GET /api/rulepacks` without auth returns 401.

---

#### F40 — Document download endpoint is missing; local storage URLs are dead

| Field | Value |
|---|---|
| Severity | Medium |
| Category | Product completeness / File access |
| Release-blocking | No (if product does not claim downloads) |
| Affected roles | Users wanting to retrieve original uploads |
| Affected files/routes | `backend/app/core/storage.py:259-260`, `/api/ingestion/opportunities/{id}/documents` (no download route) |

**Evidence:**

```python
stored_key = await storage.write(key, data, expected_ct)
url = await storage.url(stored_key) or f"/api/files/{stored_key}"
```

`LocalStorage.url()` returns `None`, so `url` becomes `/api/files/{key}`. There is no `GET /api/files/{key}` route in any module.

**Impact:** With local storage (the default), uploaded documents cannot be downloaded or previewed. The `url` field in upload responses is a dead link.

**Recommended solution:**

1. Implement `GET /api/files/{key}` in the ingestion/storage module, RLS-bound, with `Content-Type` and `Content-Disposition` headers.
2. Or make `LocalStorage.url` return a route that exists and stream from `storage_dir`.

**Verification:** Upload a file with `TS_STORAGE_TYPE=local`; `GET` the returned `url` returns the original bytes with correct `Content-Type`.

---

#### F41 — Celery document-processing SSE stream has no authentication

| Field | Value |
|---|---|
| Severity | Low |
| Category | Information disclosure |
| Release-blocking | No (task IDs are UUIDs) |
| Affected roles | Anyone who knows a task_id |
| Affected files/routes | `backend/app/modules/ingestion/router.py:184-211`, `/api/ingestion/opportunities/{id}/documents/{doc_id}/stream?task_id=...` |

**Evidence:** `document_stream` has no `Depends(require("viewer"))` or workspace check. It streams AsyncResult metadata for any known `task_id`.

**Impact:** Low because task IDs are unguessable, but if leaked (e.g. in logs or browser dev tools), task progress/results are exposed.

**Recommended solution:** Add `Depends(require("viewer"))` and verify the `task_id` belongs to the caller's workspace/opportunity (store task metadata with `workspace_id`).

**Verification:** Request SSE stream without auth returns 401; with auth but wrong workspace returns 403.

---

## 5. Remediation Plan

### 5.1 Immediate release blockers (must fix before any production launch)

| Priority | Finding | Task type | Owner suggestion |
|---|---|---|---|
| 1 | F27 | Data / Product | Complete Phase-1 QS validation or add a beta-unvalidated flag for paid workspaces; add paying-workspace test. |
| 2 | F26 | DevOps | Commit `.env.*` templates; fix `.gitignore`; verify `run.sh` and `docker compose` on a clean machine. |
| 3 | F28 | Security | Refuse production boot without real email/payment credentials; never return reset/invite tokens in HTTP responses. |
| 4 | F29 | Security / Performance | Replace virus-scan stub; make S3 I/O non-blocking; enable `scan=True` for BOQ; fix local file URL. |
| 5 | F30 | Security | Add auth and workspace binding to tus `PATCH`/`HEAD`; enforce chunk-level size caps. |

### 5.2 Required pre-release fixes (before public launch)

| Priority | Finding | Notes |
|---|---|---|
| 6 | F31 | Currency-aware Stripe/Razorpay routing. |
| 7 | F34 | Email verification flow. |
| 8 | F32 | Remove `mypy` disable list; improve type safety. |
| 9 | F40 | Document download endpoint for local storage. |
| 10 | F36 | Production operations: IaC, backups, monitoring, runbooks. |
| 11 | F37 | Distributed scheduler (Celery Beat + Redis lock). |
| 12 | F35 | E2E, accessibility, and Lighthouse CI. |

### 5.3 Short-term improvements

- F33: Align frontend upload `accept` list with backend allow-list.
- F38: Fail hard in production when S3 init fails.
- F39: Protect rulepack list/patterns endpoints.
- F41: Authenticate the Celery SSE stream.
- Add DPDP/GDPR data-export and deletion endpoints.
- Add real-time notification preferences and per-tender activity feed.

### 5.4 Long-term architectural improvements

- Move rulepack validation into a CI-eval pipeline with golden tender corpus and per-pattern precision/recall dashboards.
- Replace in-process APScheduler entirely with Celery Beat for all background jobs.
- Add tenant-specific KMS keys for enterprise tier storage.
- Build a dedicated document viewer/preview service (PDF + extracted text side-by-side).
- Implement multi-region support with per-country currency, tax, and data-residency configuration.

---

## 6. Residual Risks and Final Checklist

### 6.1 Residual risks

1. **Rulepack accuracy is unverified.** Even after the code is correct, the legal/QS validity of every pattern must be confirmed before customers rely on it.
2. **Live integrations not tested.** SES, MSG91, Razorpay, Stripe, S3, RapidOCR, and Anthropic paths were only code-reviewed and unit-tested with mocks.
3. **Scalability not measured.** The tus upload path and the Celery/RapidOCR pipeline have not been load-tested.
4. **Accessibility unverified.** No automated or manual a11y audit has been performed.
5. **Operational maturity.** Backup/restore, incident response, and SLO monitoring are not yet in place.

### 6.2 Final readiness checklist

| Area | Status | Evidence |
|---|---|---|
| Code compiles / builds | Pass | `npm run build`, `mypy app` clean |
| Linting | Pass | `ruff` clean, `npm run lint` clean |
| Unit/integration tests | Pass | `pytest -q` 145 passed |
| Vulnerability scans | Pass | `npm audit` 0, `pip-audit` 0 |
| Migrations | Pass | `alembic upgrade head/downgrade base/upgrade head` clean |
| Type safety | Partial | `mypy` passes but many error codes disabled (F32) |
| Architecture compliance | Pass | Module isolation enforced; `test_architecture.py` passes |
| Authentication | Pass | RS256 JWT, httpOnly refresh, rotation, MFA, lockout |
| Authorization / RLS | Partial | Code enforces RLS on Postgres; auth gaps in tus/SSE (F30, F41) |
| Security headers / HTTPS | Pass | `SecurityHeadersMiddleware`, `HTTPSRedirectMiddleware` in prod |
| Rate limiting | Pass | Sliding-window limiter on auth/billing endpoints |
| File upload validation | Partial | Ext/magic/size validated; virus scan and tus auth/size missing (F29, F30) |
| Payment safety | Partial | Webhook HMAC verified; mock fallback and currency bug remain (F28, F31) |
| Data integrity | Pass | SHA256 keys, audit log, export gate, baseline hashes |
| Product completeness | Partial | Core journeys present; document download and email verification missing |
| Rulepack validation | Fail | All patterns `confidence: unvalidated` (F27) |
| Deployment readiness | Fail | Missing `.env.*` files (F26) |
| E2E / accessibility | Not tested | No Playwright/axe/Lighthouse |
| Performance / load | Not tested | No benchmarks |
| Observability / backups | Not present | No IaC, monitoring, or runbooks (F36) |

### 6.3 Final recommendation

**CONDITIONAL GO for controlled internal / design-partner staging use; NO-GO for public production launch.**

The application is structurally sound, the critical architectural invariants are enforced in code, and the recent hardening commits resolved many severe security and product gaps. However, **the combination of unvalidated rulepacks, missing deployment files, and remaining security/operational stubs means it is not ready to accept paying customers or public sign-ups.**

The fastest path to production is:

1. Fix F26, F27, F28, F29, F30 (env templates, rulepack validation, integration guards, virus scan, tus auth/size).
2. Run a design-partner pilot with free workspaces to gather real tender feedback and validate rulepacks.
3. Address F31–F41 and add E2E/observability before opening billing to the public.
