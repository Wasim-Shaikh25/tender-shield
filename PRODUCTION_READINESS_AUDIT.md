# TenderShield — End-to-End Production Readiness Audit

**Repository:** `Wasim-Shaikh25/tender-shield`
**Commit audited:** `d651d00` — `feat(modules): post-audit quick wins (TS-093)`
**Branch audited:** `claude/dev-workflow-modules-58dpqw` (the repository's trunk — see §2.0)
**Audit date:** 2026-07-29
**Roles applied:** Principal Software Engineer, Security Engineer, QA Engineer, DevOps/SRE, Database Architect, Product Manager, UX Designer, Accessibility Specialist, Performance Engineer.
**Source changes made:** none. This report is the only file added or modified.

> **This report supersedes the previous `PRODUCTION_READINESS_AUDIT.md`.** Several of that
> report's findings no longer reproduce at this commit and are explicitly retired in §2.6
> (`.env.*` templates now exist and are tracked; the tus `PATCH` endpoint now requires
> `estimator`; S3 calls now use `asyncio.to_thread`). Its finding IDs (`F26`–`F41`) are not
> reused. New findings use the `TS-*` prefix.

---

## 1. Executive Summary

### 1.1 Recommendation

# NO-GO

Not for public launch, and not for any deployment holding more than one customer's data.

This is not a judgement about polish or completeness. The audit **empirically reproduced a
full cross-tenant takeover**: any user who owns a free workspace can, with a single
authenticated HTTP request and no special tooling, make themselves `owner` of any other
workspace whose UUID they know, gaining read/write access to that tenant's tender packs,
findings, BOQ data, and invoices. The database-level backstop that was designed to contain
exactly this failure (PostgreSQL row-level security) is **structurally inoperative** in the
deployed configuration, so nothing catches it. A second, independent path escalates a
`viewer` to `owner` through Google sign-in.

For a product whose own governing rules state that "cross-tenant leakage is company-ending"
(`CLAUDE.md` §4, Build Doc §3.2), these are release blockers by the project's own standard.

The codebase is otherwise in genuinely good shape — see §1.5. The blockers are concentrated
in a small number of files and are all fixable within days, not months. The recommendation is
NO-GO on the current commit, not a judgement that the architecture is unsound.

A second-round pass (§7) re-verified the findings above and reproduced three additional
release-blocking regressions: the workspace-switch refresh path does not commit the rotated
refresh token (`TS-A06`), `POST /api/auth/resend-verification` returns the raw verification
token in the response body (`TS-A07`), and the backend `Dockerfile` omits the extras required
to boot the container or enable Celery, billing, scheduling, and OCR (`TS-O04`). Two
medium-hardening auth items (`TS-A08`, `TS-A09`) and the unvalidated-rulepack product blocker
(`TS-P02`) were also confirmed.

### 1.2 Finding count by severity

| Severity | Count | Release-blocking | IDs |
|---|---|---|---|
| **Critical** | 5 | 5 | TS-A01, TS-A02, TS-A03, TS-B01, TS-P02 |
| **High** | 10 | 8 | TS-A04, TS-A05, TS-I01, TS-I02, TS-B02, TS-F01, TS-O01, TS-A06, TS-A07, TS-O04 |
| **Medium** | 11 | 0 | TS-O02, TS-I03, TS-N01, TS-P01, TS-S01, TS-X01, TS-B03, TS-S02, TS-O03, TS-A08, TS-A09 |
| **Low** | 4 | 0 | TS-L01, TS-L02, TS-L03, TS-L04 |
| **Total** | **30** | **13** | |

Product-completeness gaps are tracked separately in §3.5 (they are capability gaps, not
defects, and are not counted above).

### 1.3 Major technical risks

| Risk | Evidence | Severity |
|---|---|---|
| Any user can join any workspace as owner | Reproduced end-to-end (§4 TS-A01) | Critical |
| RLS never actually enforces — `ENABLE` without `FORCE`, app connects as table owner | `core/db.py:59-67` + `docker-compose.yml` (§4 TS-A03) | Critical |
| Google sign-in hardcodes `role="owner"` | Reproduced: `viewer` received an `owner` token (§4 TS-A02) | Critical |
| Client sets its own subscription price; webhook activates without price check | `billing/router.py:47,71-73` → `billing/service.py:161-173` (§4 TS-B01) | Critical |
| Workspace/project member lists readable cross-tenant | Reproduced: victim emails returned (§4 TS-A04) | High |
| Uploads fully buffered in memory before any size check | `ingestion/router.py:126` (§4 TS-I01) | High |
| SSE progress endpoint busy-spins a CPU core per client | `ingestion/router.py:199-207` (§4 TS-I02) | High |
| Session broken after workspace switch | `auth/service.py` `switch_workspace` does not commit rotated refresh token (§7 TS-A06) | High |
| Verification token leaked by resend endpoint | `auth/router.py` `resend_verification` returns raw token (§7 TS-A07) | High |
| Container image missing runtime extras | `backend/Dockerfile` omits `celery`, `billing`, `scheduler`, `ocr` extras (§7 TS-O04) | High |

### 1.4 Major product risks

| Risk | Impact |
|---|---|
| No team-management UI at all | Backend supports invitations, members, and roles; there is no page for any of it. A workspace owner cannot add a colleague without calling the API directly. |
| No account/security settings page | Users cannot change a password, enrol MFA, view sessions, or verify email from the UI. MFA can only be *used* at login, never *enabled*. |
| Audit log covers only finding decisions | No audit record for logins, member additions, role changes, super-admin grants, billing changes, or exports — the events an incident response would need most, and the ones most relevant given TS-A01. |
| No data export or account deletion | Blocks GDPR/DPDP compliance for a product that ingests customer commercial documents. |
| Unvalidated rulepacks deliver zero risk findings to paid workspaces | `risk/service.py` filters paying users to `validated_only`; every `in-works` pattern is `confidence: unvalidated` (§7 TS-P02). |

### 1.5 What is genuinely solid

Stated plainly so the NO-GO is not read as a verdict on the whole codebase:

- **Baseline is fully green.** `ruff` clean, `mypy` clean across 143 files, 145 backend tests
  passing, frontend lint/typecheck/build clean, `npm audit` reports 0 vulnerabilities.
- **Defense-in-depth workspace filtering is real and consistent.** Every domain service
  (`ingestion`, `findings`, `risk`, `drafting`, `export`, `assistant`, `review`, `billing`)
  filters explicitly on `workspace_id` in SQL rather than relying on RLS. This is why the
  blast radius of TS-A03 is "membership tables and the RLS backstop" rather than "everything".
- **The product's core invariants are implemented properly.** BOQ arithmetic, date arithmetic,
  and severity scoring are deterministic code with no LLM involvement. The three artifact
  validators (`drafting/validators.py`) genuinely enforce no-invented-quotes,
  no-uncited-clauses, no-invented-numbers. Money is in minor units throughout.
- **Webhook signature verification is correct and fails closed** — HMAC over the raw body with
  `hmac.compare_digest`, and an unset secret returns `False` rather than skipping the check.
- **Auth primitives are well built** — Argon2id, RS256 with `iss`/`aud` verification, refresh
  rotation with family-wide revocation on reuse detection, account lockout, a real password
  policy, and access tokens held in memory with the refresh token in an httpOnly cookie.
- **The modular architecture is enforced, not aspirational** — `tests/test_architecture.py`
  fails the build on cross-module imports, and it works (the one violation found, TS-X01, is a
  database foreign key, which that test cannot see).

### 1.6 Scope limitations

Stated up front so the recommendation is read against what was actually tested:

- **No PostgreSQL instance was available.** All tests ran on SQLite, where
  `bind_workspace_context` is a documented no-op. RLS behaviour (TS-A03) is therefore assessed
  **by code and configuration inspection, not by execution.** This is the single most important
  limitation in this report — see §6.2.
- **No running deployment, no browser.** Frontend findings come from source inspection plus a
  production build. No runtime rendering, screen-reader, or keyboard testing was performed.
- **No load, soak, or concurrency testing.** Race conditions (TS-B02) are identified by code
  inspection of transaction boundaries, not reproduced under load.
- **Third-party integrations were not exercised live.** Razorpay, Stripe, SES, MSG91, Google,
  and Apple were tested only through their local code paths and mocks.

### 1.7 Release conditions

Ship only when **all thirteen** release-blocking findings in §5.1, §5.2, and §7.3 are fixed,
each with a regression test, **and** the RLS behaviour in TS-A03 has been verified against a real
PostgreSQL instance using a non-owner application role (§6.2). Fixing the application-layer
checks without fixing RLS leaves the product one missing `if` statement away from the same
outcome.

---

## 2. System and Audit Overview

### 2.0 Branch situation

The task asked to "check main branch". **There is no `main` branch in this repository.**
`git ls-remote` and the GitHub branch list return 13 branches, none named `main`, `master`, or
`trunk`. The de-facto trunk is `claude/dev-workflow-modules-58dpqw` — it is the branch carrying
the merge commits for PRs #11, #12, and #13. The audit branch
`claude/production-readiness-audit-057y3a` is at the identical commit (`d651d00`, empty diff),
so this audit reflects current trunk exactly.

> **Operational note:** a repository with no default-named branch and no branch protection on
> any of the 13 branches is itself a release-readiness gap. See TS-O03.

### 2.1 Architecture

A **modular monolith**. FastAPI backend (Python 3.11, SQLAlchemy 2, Pydantic v2) plus a
Next.js 15 / TypeScript / Tailwind frontend.

```
Browser (Next.js 15, 12 routes)
   │  Bearer access token (in memory) + httpOnly refresh cookie (path=/api/auth)
   ▼
FastAPI app factory  ── app/main.py
   │   middleware: HTTPSRedirect (prod) → TrustedHost → CORS → SecurityHeaders
   │   AppContext { Settings, ServiceRegistry, EventBus }
   ├── ServiceRegistry ......... the only sanctioned cross-module call channel
   ├── EventBus ................ publish/subscribe, fail-isolated handlers
   ├── Celery .................. async doc processing (eager without Redis)
   ├── Scheduler ............... APScheduler, no-op stub when absent
   └── 20 pluggable modules mounted at /api/<name>
          analytics assistant auth baseline billing boq comparison crossref
          drafting export findings health ingestion notifications qualification
          review risk rulepacks standards timeline
   ▼
PostgreSQL 16 (prod) / SQLite (tests)   +   Local FS or S3 object storage
```

Each module exposes exactly one entry point (`module: ModuleSpec` in `module.py`) and may
import only `app.core.*` and its own package. `tests/test_architecture.py` enforces this.

### 2.2 Roles and trust boundaries

**Roles** (`auth/rbac.py`, ranked): `viewer` (0) < `reviewer` (1) < `estimator` (2) <
`admin` (3) < `owner` (4). Orthogonal to these: `is_superadmin` (platform operator) and
`email_verified` (gates sensitive mutations).

**Trust boundaries crossed:**

| Boundary | Direction | Control | Assessment |
|---|---|---|---|
| Browser → API | inbound | RS256 JWT, per-route role guard | Guard present everywhere; **TS-A01/A04 show the guard checks the wrong workspace** |
| Tenant → Tenant | lateral | Explicit `workspace_id` SQL filters + RLS | Filters good; **RLS inoperative (TS-A03)**; membership endpoints unfiltered (TS-A01/A04) |
| Payment provider → API | inbound | HMAC over raw body, idempotency | Signature correct; **amount never validated (TS-B01)** |
| OIDC provider → API | inbound | JWKS signature, `aud`/`iss` verified | Verification correct; **role assignment broken (TS-A02)** |
| Tender document → LLM | inbound | Grounded-only system prompt | **No delimiting/neutralization of untrusted text (TS-P01)** |
| Uploaded file → storage | inbound | ext + magic + size + scan stub | **Size checked after full buffering (TS-I01); scan is a no-op (TS-S01)** |

### 2.3 Coverage — what was actually reviewed

**Fully read (line by line):** all 12 files in `app/core/`; all 12 files in `app/modules/auth/`;
`billing/{router,service,webhook,plans}.py`; `ingestion/{router,tus,service}.py` and
`ingestion/tasks.py`; `storage.py`; `notifications/module.py`; `drafting/validators.py`;
`assistant/{agent,service}.py`; `health/router.py`; `boq/router.py`; `review/{models,service}.py`;
`migrations/env.py` and all 6 migration files; `main.py`; `docker-compose.yml`; `.github/workflows/ci.yml`;
`pyproject.toml`; all four `.env.*` files; `frontend/lib/api.ts`; `frontend/components/session.tsx`;
`frontend/app/login/page.tsx`.

**Systematically surveyed:** every route across all 20 modules with its authorization guard
(complete inventory produced — 84 routes); `workspace_id` filtering in all domain services;
`index=True`/`Index(...)` declarations across all model files; every `.env.*` file for secrets.

**Not reviewed in depth (declared, not claimed):** `analytics`, `comparison`, `crossref`,
`qualification`, `standards`, `timeline`, `rulepacks` internals; `risk/{engine,classifier,severity}.py`;
`boq/engine.py`; `export/render.py`; `ingestion/{ocr,tables,segment,classify,extract}.py`;
frontend page components other than `login`; the 32 YAML rulepack files; `evals/`.

### 2.4 Commands executed and results

All commands run from a clean checkout of `d651d00` in an isolated venv.

| # | Command | Result |
|---|---|---|
| 1 | `pip install -e ".[dev,storage,redis,billing,scheduler,celery,auth]"` | Success (in venv; **fails on system Python** — see TS-L04) |
| 2 | `ruff check .` | **PASS** — All checks passed |
| 3 | `mypy app` | **PASS** — no issues in 143 source files |
| 4 | `pytest -q` | **PASS** — 145 passed, 1 skipped, 36.51s |
| 5 | `npm ci` (frontend) | Success |
| 6 | `npm run lint` | **PASS** — no ESLint errors |
| 7 | `npm run typecheck` (`tsc --noEmit`) | **PASS** |
| 8 | `npm audit --audit-level=high` | **PASS** — 0 vulnerabilities |
| 9 | `npm run build` | **PASS** — 12 routes, 102 kB shared JS |
| 10 | Custom exploit probes (3 files, 12 probes) | **4 confirmed exploits, 3 defenses confirmed working** |

**Not run, with reason:**

| Check | Why not |
|---|---|
| `alembic upgrade head && alembic downgrade base` | Runs in CI on SQLite. Re-running adds nothing; the RLS block it would exercise is PostgreSQL-only and would be skipped. |
| `pip-audit --desc --local` | Runs in CI on every push and is green at this commit. Not re-run offline; **dependency CVE status is therefore CI-attested, not independently verified here.** |
| PostgreSQL integration / RLS verification | No PostgreSQL instance available. **This is the critical gap — see §6.2.** |
| Load, soak, concurrency, browser, a11y, screen-reader | No deployment or browser available. |

### 2.5 Exploit probes — method and results

Probes were written as pytest files against the real app via `TestClient`, using only the
public HTTP API (except where noted). They are **audit artifacts, not committed to the
repository** — no source file was modified.

| Probe | Attempt | Result |
|---|---|---|
| A | Verified owner of workspace A adds self as `owner` to workspace B by UUID | ⚠️ **EXPLOITED** — HTTP 200; `GET /auth/workspaces` then lists "Victim Corp" with role `owner` |
| B | Read `GET /auth/workspaces/{victim_id}/members` from a foreign workspace | ⚠️ **EXPLOITED** — HTTP 200, victim's email and role returned |
| C | Google sign-in as a user whose only membership is `viewer` | ⚠️ **EXPLOITED** — `/auth/me` returns `"role": "owner"` |
| E | Read `GET /auth/projects/{victim_project}/members` cross-tenant | ⚠️ **EXPLOITED** — HTTP 200, victim owner's email returned |
| H | Google sign-in with an email that already has a password account | ⚠️ **DEFECT** — unhandled `IntegrityError` (HTTP 500), no account linking |
| D | Path traversal in `/api/files/{key}` — `../`, `%2f..%2f`, and prefix-confusion variants | ✅ **BLOCKED** (404) — Starlette normalizes before routing |
| F | Escape the storage prefix to `../../uploads/` | ✅ **BLOCKED** (404) |
| G | `POST /auth/workspaces/{victim_id}/switch` without membership | ✅ **BLOCKED** (403 `not_workspace_member`) |

Probe D/F/G results are reported as **verified working defenses**, not assumptions.

### 2.6 Prior audit findings retired at this commit

| Prior claim | Status now | Evidence |
|---|---|---|
| `.env.local`, `.env.dev`, `.env.prod` missing → deployment broken | **RETIRED** | All four tracked (`git ls-files`); all are placeholder templates, **no real secrets committed** — verified by reading each in full |
| tus `PATCH` unauthenticated | **RETIRED** | `tus.py:143` — `Depends(require("estimator"))` plus a `workspace_mismatch` check |
| Celery SSE endpoint unauthenticated | **RETIRED** | `ingestion/router.py:191` — `Depends(require("viewer"))` plus document ownership check |
| S3 calls block the event loop | **RETIRED** | `core/storage.py:157-185` — all calls wrapped in `asyncio.to_thread` |
| Virus scanning is a no-op | **STILL TRUE** | Re-filed as TS-S01 |

### 2.7 Assumptions

1. Production runs PostgreSQL 16 as configured in `docker-compose.yml`, with the application
   connecting as the same role that ran the migrations (`tendershield`). **TS-A03's severity
   depends on this assumption** — if a separate non-owner application role is used, TS-A03
   drops from Critical to Medium. This must be confirmed (§3.6, Q1).
2. `TS_ENV=prod` is set in production, activating `_validate_prod_settings`, HTTPS redirect,
   and secure cookies.
3. The application is deployed behind a TLS-terminating load balancer (relevant to TS-O01).
4. Workspace UUIDs are not public, but are **not treated as secrets** — they appear in API
   responses, JWTs, and file URLs. TS-A01 needs only a UUID, which any collaborator, former
   member, or shared export recipient already has.

---

## 3. Product Completeness

Legend: **I** Implemented · **P** Partial · **M** Missing · **U** Unverified · **N/A** Not applicable

### 3.1 Role-to-Capability Matrix

| Capability | viewer | reviewer | estimator | admin | owner | superadmin |
|---|---|---|---|---|---|---|
| Sign up / sign in (password) | I | I | I | I | I | I |
| Sign in via Google / Apple | P¹ | P¹ | P¹ | P¹ | P¹ | P¹ |
| MFA at login | I | I | I | I | I | I |
| **Enrol in MFA (UI)** | **M** | **M** | **M** | **M** | **M** | **M** |
| **Verify email (UI)** | **M** | **M** | **M** | **M** | **M** | **M** |
| **Change password while signed in** | **M** | **M** | **M** | **M** | **M** | **M** |
| Reset forgotten password | I | I | I | I | I | I |
| Landing page / dashboard | P² | P² | P² | P² | P² | I³ |
| View opportunities & findings | I | I | I | I | I | I |
| Upload documents / run analysis | N/A | N/A | I | I | I | N/A |
| Accept or reject findings | N/A | I | I | I | I | N/A |
| Generate & export artifacts | N/A | N/A | I | I | I | N/A |
| **Invite a colleague (UI)** | N/A | N/A | N/A | **M**⁴ | **M**⁴ | N/A |
| **Manage members / change roles (UI)** | N/A | N/A | N/A | **M**⁴ | **M**⁴ | N/A |
| **Remove a member** | N/A | N/A | N/A | **M**⁵ | **M**⁵ | N/A |
| **Create / manage projects (UI)** | N/A | N/A | N/A | **M**⁴ | **M**⁴ | N/A |
| Switch workspace | P⁶ | P⁶ | P⁶ | P⁶ | P⁶ | P⁶ |
| **Create a workspace (UI)** | **M**⁴ | **M**⁴ | **M**⁴ | **M**⁴ | **M**⁴ | N/A |
| View billing status & invoices | I | I | I | I | I | N/A |
| Start checkout | N/A | N/A | N/A | I | I | N/A |
| **Cancel subscription** | N/A | N/A | N/A | **M**⁵ | **M**⁵ | N/A |
| **Notification preferences** | **M**⁵ | **M**⁵ | **M**⁵ | **M**⁵ | **M**⁵ | N/A |
| **Export my data / delete account** | **M**⁵ | **M**⁵ | **M**⁵ | **M**⁵ | **M**⁵ | N/A |
| Platform admin (users, workspaces) | N/A | N/A | N/A | N/A | N/A | I |
| **Platform ops dashboard** | N/A | N/A | N/A | N/A | N/A | **M**⁵ |

¹ Google is exploitable (TS-A02) and 500s on existing emails (TS-A05); Apple has no frontend entry point.
² `/opportunities` is a list, not a dashboard — no pending-actions queue, no alerts, no recent activity.
³ `/admin` page exists and is functional.
⁴ **API exists, no UI.** ⁵ **Neither API nor UI.** ⁶ API works and is correctly guarded, but the UI switcher is broken by TS-F01.

### 3.2 Entity-to-Operation Matrix

| Entity | Create | List | View | Update | Delete | Archive | Search | Export | History |
|---|---|---|---|---|---|---|---|---|---|
| User | I | I³ | I | P¹ | **M** | **M** | **M** | **M** | **M** |
| Workspace | P⁴ | I | I | **M** | **M** | **M** | N/A | **M** | **M** |
| Workspace member | I⁵ | I⁵ | I | I | **M** | N/A | **M** | **M** | **M** |
| Project | P⁴ | I | I | **M** | **M** | **M** | **M** | **M** | **M** |
| Invitation | P⁴ | **M** | **M** | **M** | **M**² | N/A | N/A | N/A | **M** |
| Opportunity | I | I | I | **M** | **M** | **M** | **M** | I | P |
| Document | I | I | I | P⁶ | **M** | **M** | **M** | **M** | **M** |
| Finding | I | I | I | I⁷ | N/A | N/A | P | I | I⁸ |
| Artifact | I | I | I | **M** | **M** | **M** | **M** | I | **M** |
| Baseline | I | I | I | N/A⁹ | N/A⁹ | N/A⁹ | N/A | I | I |
| Invoice | I⁵ | I | I | N/A⁹ | N/A⁹ | N/A | **M** | **M** | I |
| Chat session | I | I | I | **M** | **M** | **M** | **M** | **M** | I |

¹ Only `is_superadmin` and MFA method. ² **No invitation revocation — a leaked invite token is valid for 7 days with no way to cancel it.**
³ Super-admin only. ⁴ API only, no UI. ⁵ Created/listed via API. ⁶ Supersede only. ⁷ Accept/reject. ⁸ Via `audit_log`. ⁹ Immutable by design (correct).

### 3.3 Workflow Completeness Matrix

| Workflow | Entry | Authz | Validation | Success | Failure | Cancel | Retry | Notify | History |
|---|---|---|---|---|---|---|---|---|---|
| Sign up → verify → first review | I | I | I | I | I | N/A | I | P¹ | **M** |
| Password reset | I | N/A | I | I | I | **M** | I | I | **M** |
| MFA enrolment → challenge | P² | I | I | I | I | **M** | I | I | **M** |
| Invite → accept → collaborate | P³ | ⚠️⁴ | I | I | I | **M**⁵ | I | P | **M** |
| Upload → OCR → classify → findings | I | I | I | I | I | **M** | P⁶ | **M** | P |
| Review queue → accept/reject → gate | I | I | I | I | I | N/A | I | **M** | I |
| Generate artifact → validate → export | I | I | I | I | I | N/A | I | **M** | P |
| Checkout → webhook → activate plan | I | ⚠️⁷ | ⚠️⁷ | I | I | **M**⁸ | P⁹ | **M** | I |
| Freeze baseline → compare → handover | I | I | I | I | I | N/A | I | **M** | I |
| Deadline alert scheduling | I | I | I | P¹⁰ | P | **M** | **M** | I | **M** |

¹ Verification token returned in the response body in dev; email only in prod.
² No enrolment UI. ³ API only. ⁴ **TS-A01: authorization checks the caller's own workspace, not the target.**
⁵ No invitation revocation. ⁶ Celery retries not configured. ⁷ **TS-B01: client sets the price; webhook never validates it.**
⁸ No cancellation endpoint — only an inbound provider webhook can downgrade a plan.
⁹ Idempotency present but racy (TS-B02). ¹⁰ Re-sends the same alert daily with no dedup (TS-N01).

### 3.4 Dashboard and Reporting Matrix

Assessed against the task the dashboard would support, not against convention.

| Surface | Status | Task it supports | Verdict |
|---|---|---|---|
| Opportunity list (`/opportunities`) | I | Pick a tender to work on | Adequate |
| Opportunity detail (`/opportunities/[id]`) | I | Review findings, deadlines, BOQ | Adequate — the product's core screen |
| Billing (`/billing`) | I | Check plan and invoices | Adequate |
| Platform admin (`/admin`) | I | Operator manages users/workspaces | Adequate |
| Accuracy analytics (`/analytics`) | I | Measure finding precision | Adequate |
| Standards (`/standards`) | I | Configure notice/commercial standards | Adequate |
| **Estimator work queue** | **M** | *"Which of my tenders need action before their deadline?"* — the daily job of the primary user. Deadline data exists (`deadlines` table, `/timeline`) but is only reachable per-opportunity, so a user juggling 10 live tenders must open each one to find what is due. **Recommended.** |
| **Reviewer queue (cross-opportunity)** | **M** | *"What is waiting on my sign-off?"* — `review/queue` exists but is per-opportunity only. A reviewer covering several bids has no single inbox. **Recommended.** |
| **Workspace/team management** | **M** | *"Add my estimator to this workspace."* Backend supports it; there is no page. **Required before multi-user launch.** |
| **Account & security settings** | **M** | *"Change my password, turn on MFA."* **Required.** |
| Usage/quota reporting | P | `/billing` shows `reviews_this_month`; no trend or per-user breakdown. Acceptable for launch. |
| **Security/audit report** | **M** | *"Who accessed this tender, and who changed roles?"* Especially needed given TS-A01. **Recommended.** |
| Operational dashboard | **M** | Error rates, queue depth, processing latency. No metrics exist at all (TS-O02). **Recommended.** |

### 3.5 Missing capabilities (ranked)

**Required before a multi-user public launch**

1. **Team management UI** — invite, list, change role, remove member. Backend exists; no page.
   (Domain-Expected Capability + Strongly Implied Requirement — the product is priced per seat:
   `PLAN_LIMITS` defines 2/3/10/25 seats, so seat management is implied by the pricing model.)
2. **Account & security settings** — change password, enrol MFA, resend verification, view/revoke
   sessions. `POST /auth/mfa/enroll` exists with no caller. (Domain-Expected Capability)
3. **Member removal + invitation revocation** — neither API nor UI. An employee who leaves cannot
   be removed from a workspace; a leaked invite token cannot be cancelled for 7 days.
   (Strongly Implied Requirement — offboarding is not optional for B2B.)
4. **Seat limit enforcement** — `PLAN_LIMITS[*]["seats"]` is defined but **never read anywhere in
   the codebase**. A free workspace (2 seats) can add unlimited members. (Confirmed Defect against
   the documented plan model — filed as TS-B03.)

**Required for compliance**

5. **Data export and account deletion** — GDPR/DPDP. No API, no UI.
6. **Comprehensive audit log** — `audit_log` is written only by `review/service.py:38`. No record
   of authentication, member/role changes, super-admin grants, billing changes, or exports.

**Strongly recommended**

7. Cross-opportunity work queue and reviewer inbox (see §3.4).
8. Subscription cancellation/downgrade from the UI.
9. Notification preferences — users are auto-subscribed to deadline alerts with no opt-out.

### 3.6 Product Decisions Required

| # | Question | Why it matters | Cannot be answered from the repo because |
|---|---|---|---|
| Q1 | Does the production app connect to PostgreSQL as the **table-owning** role, or a separate least-privilege role? | **Determines whether TS-A03 is Critical or Medium.** RLS is bypassed for the table owner unless `FORCE` is set. | Only `docker-compose.yml` (single `tendershield` role) is in the repo; production infra is not. |
| Q2 | Should a workspace `admin` be able to add members to **any** workspace, or only their own? | Current behaviour is "any" (TS-A01). The fix depends on whether cross-workspace administration is ever intended. | No spec statement either way; `specs/modules/auth.md` does not address it. |
| Q3 | When a user with an existing password account signs in with Google, should the accounts **link**, or should it be rejected? | Currently 500s (TS-A05). Auto-linking on an unverified email is an account-takeover vector; rejecting is safe but poor UX. | Build Doc §5 does not specify OIDC account-linking policy. |
| Q4 | Is `checkout.amount_minor` intended as a client input at all (e.g. for partial top-ups)? | If not, delete it. If yes, it needs a server-side allow-list. | The field exists with no spec reference. |
| Q5 | Are seat limits meant to be enforced, or advisory? | `PLAN_LIMITS[*]["seats"]` is defined but never read (TS-B03). | Build Doc §7 lists the limits without stating enforcement. |
| Q6 | What is the intended alert cadence — once per deadline, or a daily digest until resolved? | Determines whether TS-N01 is a bug or the design. | `specs/modules/notifications.md` does not state a dedup policy. |

---

## 4. Detailed Findings

---

### TS-A01 — Any authenticated user can join any workspace as owner

| | |
|---|---|
| **Status** | Confirmed Defect — **reproduced end-to-end** |
| **Severity** | **Critical** |
| **Category** | Broken Access Control / Tenant Isolation (OWASP A01) |
| **Release-blocking** | **YES** |
| **Affected roles** | All — any user who can reach `admin` in their own (free, self-created) workspace |

**Location**

- `backend/app/modules/auth/router.py:394-406` — `add_workspace_member`
- `backend/app/modules/auth/service.py` — `add_workspace_member(workspace_id, email, role)`
- Same pattern: `router.py:547-560` (`POST /members`, legacy route)

**Evidence**

```python
# router.py:394
@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,                                    # ← attacker-controlled
    body: AddMemberBody,
    principal: Principal = Depends(require("admin")),     # ← role in the CALLER's OWN workspace
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).add_workspace_member(workspace_id, body.email, body.role)
    )
```

The service then writes the membership row with no membership check on `workspace_id`:

```python
def add_workspace_member(self, workspace_id, email: str, role: str) -> dict:
    if role not in ROLES:
        raise AuthError("bad_role")
    workspace_id = uuid.UUID(str(workspace_id))          # ← trusted verbatim
    user = self.s.scalar(select(User).where(User.email == email.strip().lower()))
    ...
    self.s.add(WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role))
```

`require("admin")` verifies the caller's role **claim from their own JWT**. Since every user
becomes `owner` of the personal workspace created at signup, **every user in the system passes
this guard.** The path parameter is never compared to `principal.workspace_id`.

**Reproduction** (probe A, verified):

```
1. Victim signs up  → workspace 8d1d91be-…  ("Victim Corp")
2. Attacker signs up → workspace 52b427fd-…  ("Attacker Ltd"), verifies email
3. POST /api/auth/workspaces/8d1d91be-…/members
   Authorization: Bearer <attacker token>
   {"email": "attacker@example.com", "role": "owner"}

   → HTTP 200 {"workspace_id":"8d1d91be-…","user_id":"0fcb…","role":"owner"}

4. GET /api/auth/workspaces  (attacker token)
   → [{"workspace_id":"52b427fd-…","name":"Attacker Ltd","role":"owner"},
      {"workspace_id":"8d1d91be-…","name":"Victim Corp","role":"owner"}]   ← TAKEOVER
```

After step 4 the attacker calls `POST /auth/workspaces/{victim}/switch` — which *does* check
membership, and now correctly passes, because the attacker is genuinely a member. They receive
a legitimate `owner` token for the victim workspace and can read every tender pack, finding,
BOQ, artifact, and invoice, and can add or remove further members.

**Root cause**

Authorization is *authenticated but not associated*: the role guard proves the caller has a
role **somewhere**, and the handler then applies it **elsewhere**. This is the classic
"role check without resource binding" defect. `create_project` in the same file gets it right
(`if not self._workspace_member(workspace_id, user_id): raise AuthError("not_workspace_member")`),
which shows the correct pattern already exists in the codebase and was simply not applied here.

**Impact**

*Technical:* Total collapse of tenant isolation for every workspace whose UUID is known.
Read and write access to all workspace-scoped data. Self-granted `owner` allows locking the
legitimate owner out by role downgrade.

*Business:* Company-ending by the project's own standard (`CLAUDE.md` §4). Tender packs are
pre-award commercial documents; leakage between contractors bidding the same tender is direct
competitive harm and near-certain contractual breach. Under India's DPDP Act and GDPR this is a
reportable personal-data breach. The `audit_log` would not record it (§3.5 item 6).

**Recommended solution**

Bind every workspace-scoped route to the caller's active workspace, and add a defence-in-depth
membership check in the service. Illustrative patch:

```python
# backend/app/modules/auth/deps.py  — new shared guard
def require_in_workspace(min_role: str):
    """Role guard bound to the workspace named in the path (never just the token)."""
    def guard(
        workspace_id: str,
        principal: Principal = Depends(current_principal),
        session: Session = Depends(get_session),
    ) -> Principal:
        if str(principal.workspace_id) != str(workspace_id):
            # 404, not 403 — do not confirm that an unknown workspace exists.
            raise HTTPException(404, "not_found")
        if not role_at_least(principal.role, min_role):
            raise HTTPException(403, "insufficient_role")
        return principal
    return guard
```

```python
# backend/app/modules/auth/router.py:394
@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_in_workspace("admin")),   # ← bound to the path
):
```

```python
# backend/app/modules/auth/service.py — defence in depth
def add_workspace_member(self, workspace_id, email, role, *, actor_user_id):
    if role not in ROLES:
        raise AuthError("bad_role")
    workspace_id = uuid.UUID(str(workspace_id))
    actor = self._workspace_member(workspace_id, actor_user_id)
    if actor is None or not role_at_least(actor.role, "admin"):
        raise AuthError("not_workspace_member")
    if ROLE_RANK[role] > ROLE_RANK[actor.role]:
        raise AuthError("cannot_grant_higher_role")   # no self-escalation past your own rank
    ...
```

**Database / security / deployment considerations**

Deploy with TS-A03 (RLS) so the database independently rejects this class of bug.
**Before deploying the fix, audit existing `workspace_members` rows** for memberships whose
`user_id` has no plausible relationship to the workspace (e.g. a user who is `owner` of several
workspaces they did not create). Any such row may be an exploited membership and must be
removed, not just blocked going forward.

**Regression risks**

Medium. If any legitimate flow adds members to a workspace other than the token's active one,
it will now 404. Grep confirms only the two routes above and `accept_invitation` write
`WorkspaceMember`; `accept_invitation` is correctly driven by the invitation record and is
unaffected. The super-admin path must be exempted explicitly if platform operators are meant
to administer tenant workspaces.

**Tests to add**

1. `test_cannot_add_member_to_foreign_workspace` — probe A, asserting 404 **and** that
   `GET /auth/workspaces` for the attacker is unchanged.
2. `test_cannot_grant_role_above_own_rank` — an `admin` may not mint an `owner`.
3. `test_legacy_members_route_uses_token_workspace`.
4. A parametrized test over **every** route carrying a `{workspace_id}` or `{project_id}` path
   parameter, asserting a foreign ID returns 404. This prevents the whole class from recurring.

**Verification steps**

```bash
cd backend && pytest tests/test_auth_module.py -k foreign_workspace -q
# then re-run probe A end-to-end and confirm:
#   step 3 → HTTP 404
#   step 4 → attacker still sees exactly one workspace
```

**Similar locations to inspect**

`GET /workspaces/{workspace_id}/members` (TS-A04), `GET /workspaces/{workspace_id}/projects`,
`GET /projects/{project_id}/members` (TS-A04), `POST /projects/{project_id}/members`
(uses `principal.workspace_id` — correct, but the project itself is not verified to belong to
it before the service call; the service does check, so this one is safe).

---

### TS-A02 — Google sign-in grants `owner` to every user regardless of actual role

| | |
|---|---|
| **Status** | Confirmed Defect — **reproduced end-to-end** |
| **Severity** | **Critical** |
| **Category** | Privilege Escalation / Broken Access Control |
| **Release-blocking** | **YES** |
| **Affected roles** | Any `viewer`, `reviewer`, or `estimator` with a Google account |

**Location** — `backend/app/modules/auth/service.py`, `google_login()`

**Evidence**

```python
return self._issue_tokens(
    user.id,
    self.s.scalar(
        select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    ),
    "owner",                       # ← role hardcoded, actual membership role ignored
    is_superadmin=user.is_superadmin,
    new_family=True,
)
```

Two defects in one statement:

1. The role is the **string literal `"owner"`**, not `member.role`.
2. The workspace is `select(...).where(user_id == …)` with **no `ORDER BY` and no `LIMIT`** — for
   a multi-workspace user this returns an arbitrary row, so which workspace the token addresses
   is non-deterministic.

Compare `login()` in the same file, which correctly uses `member.role`. Apple sign-in
(`apple_callback`) is also correct. Google is the only broken provider.

**Reproduction** (probe C, verified):

```
1. lowpriv@example.com is added to "Victim Corp" with role "viewer"
2. Their only membership is that viewer row; google_sub is linked
3. POST /api/auth/google {"id_token": "<valid Google token>"}   → HTTP 200
4. GET /api/auth/me with the returned token
   → {"user_id":"d56b3054-…","workspace_id":"d469c399-…","role":"owner",…}
                                                          ^^^^^^^^^^^^^^^ was "viewer"
```

The JWT is validly signed by the server, so every downstream `require(...)` guard honours it.

**Root cause**

Copy-paste from the first-sign-in branch, where `"owner"` is correct (a brand-new user *is*
owner of the personal workspace just created for them). The existing-user branch reuses the
same literal instead of reading the membership row.

**Impact**

*Technical:* Any user with the lowest role escalates to full workspace control by signing in
through a different, legitimate front door. Combined with TS-A01, an escalated `owner` can then
reach into other workspaces entirely.

*Business:* The role model — the basis of seat pricing and of every "who may approve this bid"
control — is unenforceable for Google users. A junior estimator can approve findings, generate
artifacts, alter billing, and remove the workspace owner.

**Recommended solution**

```python
# backend/app/modules/auth/service.py — google_login(), existing-user branch
member = self.s.scalar(
    select(WorkspaceMember)
    .where(WorkspaceMember.user_id == user.id)
    .order_by(WorkspaceMember.workspace_id)     # deterministic selection
)
if not member:
    if user.is_superadmin:
        return self._issue_tokens(user.id, None, "owner", is_superadmin=True, new_family=True)
    raise AuthError("no_workspace")
return self._issue_tokens(
    user.id,
    member.workspace_id,
    member.role,                                 # ← the actual role
    is_superadmin=user.is_superadmin,
    new_family=True,
)
```

This makes `google_login` structurally identical to `login()`. Better still, extract the shared
tail of `login`, `google_login`, and `apple_callback` into one `_issue_for_user(user)` helper so
the three providers cannot drift again — that drift is the root cause.

**Regression risks**

Low. Genuine owners still receive `owner` because their membership row says so. Users whose only
membership was implicitly assumed will now correctly receive their real role — which is the fix,
though it may surface as "Google users lost permissions" in support channels. Note it in release
notes.

**Tests to add**

1. `test_google_login_preserves_membership_role` (probe C) — a `viewer` receives `viewer`.
2. `test_google_login_deterministic_workspace` — a multi-workspace user gets a stable workspace.
3. A parametrized test across all three providers asserting identical role/workspace resolution.

**Verification** — `pytest tests/test_auth_module.py -k google -q`, then re-run probe C and
assert `/auth/me` returns `"role": "viewer"`.

**Similar locations** — audit `apple_callback` (correct today) and any future OIDC provider
against the same checklist. Grep for `"owner"` as a literal argument:
`grep -rn '"owner"' backend/app/modules/auth/service.py`.

---

### TS-A03 — Row-Level Security is defined but structurally inoperative

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) — **not verified against PostgreSQL** (§6.2) |
| **Severity** | **Critical** (conditional — see Q1 in §3.6) |
| **Category** | Tenant Isolation / Database Security |
| **Release-blocking** | **YES** |
| **Affected roles** | All tenants |

**Location** — `backend/app/core/db.py:59-67`;
`backend/migrations/versions/e26e85245237_workspace_tenant.py:378-382`; `docker-compose.yml`

**Evidence** — four independent defects in the RLS implementation:

```python
# backend/app/core/db.py:59
def rls_statements(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",          # ← defect 1
        (
            f"CREATE POLICY workspace_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id')::uuid)"  # ← defects 2, 3
        ),
    ]
```

**Defect 1 — `ENABLE` without `FORCE`.** In PostgreSQL, row-level security **does not apply to
the table's owner**. `docker-compose.yml` defines exactly one role (`tendershield`) which both
runs the migrations (owning every table) and serves the application. Under that configuration
**every RLS policy in this codebase is silently bypassed for every query.** `FORCE ROW LEVEL
SECURITY` is required, or the app must connect as a separate non-owner role. This also means the
policies have almost certainly never actually been exercised — they would be invisible in
testing, which is consistent with defects 2–4 going unnoticed.

**Defect 2 — `USING` without `WITH CHECK`.** `USING` filters rows that are *read*. Without
`WITH CHECK`, `INSERT` and `UPDATE` may still **write** rows carrying another workspace's
`workspace_id`. The read-side and write-side halves of isolation are not symmetric.

**Defect 3 — `current_setting()` without the missing-OK argument.** `current_setting('app.workspace_id')`
raises `unrecognized configuration parameter` when the GUC was never set. Any code path reaching
a workspace-scoped table without first calling `bind_workspace_context` will error at runtime
rather than fail closed. The billing webhook path is exactly such a caller — it is unauthenticated
by design and never binds. The correct form is `current_setting('app.workspace_id', true)`
combined with a null check.

**Defect 4 — membership tables are not covered.** Only classes mixing in `WorkspaceScopedMixin`
register in `WORKSPACE_SCOPED_TABLES`. `workspace_members` and `project_members` declare
`__tablename__` directly (`auth/models.py`) and therefore **receive no policy at all**, despite
both carrying a `workspace_id` column. These are precisely the tables that TS-A01 and TS-A04
abuse. `users`, `workspaces`, `refresh_tokens`, `password_resets`, and `email_verifications` are
likewise uncovered — defensible for global tables, but it means the membership graph has no
database-level protection whatsoever.

**Compounding:** `bind_workspace_context` is a documented no-op on SQLite (`db.py:77-79`) and the
entire 145-test suite runs on SQLite. **No test in the repository exercises RLS behaviour.**
`tests/test_db.py:29` asserts only the *shape* of the generated SQL strings, never their effect.

**Root cause**

RLS was implemented as a code artifact and validated by asserting on generated SQL text, rather
than by executing it against PostgreSQL and observing that a cross-tenant read is actually
refused. Every one of the four defects would have been caught by a single integration test that
binds workspace A and then attempts to `SELECT` a workspace-B row.

**Impact**

The database-level backstop for tenant isolation provides **no protection in the deployed
configuration**. Application-level `workspace_id` filters (which are consistent and good — §1.5)
are the *only* line of defence, so any single missing filter becomes a full isolation breach.
TS-A01 and TS-A04 are exactly that, and RLS did not contain either.

**Recommended solution**

```python
# backend/app/core/db.py
def rls_statements(table: str) -> list[str]:
    """RLS enable + workspace-isolation policy for one table (PostgreSQL only).

    FORCE is required: without it the policy does not apply to the table owner,
    and the application role owns these tables.
    """
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        (
            f"CREATE POLICY workspace_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id', true)::uuid) "
            "WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid)"
        ),
    ]
```

Cover the membership tables by giving them the mixin (they already have the column):

```python
# backend/app/modules/auth/models.py
class WorkspaceMember(Base, WorkspaceScopedMixin):
    _tablename_ = "workspace_members"
    # workspace_id now supplied by the mixin — drop the local declaration
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
```

Then handle the unbound-session case explicitly. With `current_setting(..., true)` an unbound
session yields `NULL`, and `workspace_id = NULL` is never true — so the table reads as empty
rather than erroring. That is the correct fail-closed behaviour, but the billing webhook must be
audited to confirm it does not silently read zero rows (it writes via `_workspaces()`, which
should be given an explicit privileged path).

**Deployment considerations**

Strongly prefer a **separate least-privilege application role** that does not own the tables, in
addition to `FORCE`. Belt and braces: `FORCE` protects against the owner case, a non-owner role
protects against `FORCE` being dropped by a future migration.

Ordering matters: `FORCE` on tables the app then cannot read will cause an immediate outage if
any code path fails to bind. **Deploy to staging and exercise every endpoint before production**,
including Celery workers (`ingestion/tasks.py:32` binds — good) and the scheduler
(`notifications/module.py:50` binds — good).

**Regression risks**

**High — this is the riskiest fix in the report.** Any unbound code path that currently works
will start returning empty results or failing. Roll out behind a staging soak, and audit every
`sessionmaker()` call site for a corresponding `bind_workspace_context`.

**Tests to add** (these require a real PostgreSQL — see §6.2)

1. `test_rls_blocks_cross_workspace_select` — bind A, insert a row for B directly, assert A cannot see it.
2. `test_rls_blocks_cross_workspace_insert` — bind A, attempt to insert with B's `workspace_id`, assert rejection (this is the `WITH CHECK` test).
3. `test_rls_applies_to_table_owner` — connect as the owning role, assert the policy still applies (this is the `FORCE` test).
4. `test_unbound_session_reads_no_rows` — no `SET LOCAL`, assert empty rather than error.
5. `test_membership_tables_are_rls_covered` — assert `workspace_members` and `project_members` ∈ `WORKSPACE_SCOPED_TABLES`.

Add a PostgreSQL service container to `.github/workflows/ci.yml` and run these there. Without CI
coverage on PostgreSQL, this finding will silently regress.

**Verification steps**

```sql
-- as the application role, against a staging database
SELECT relname, relrowsecurity, relforcerowsecurity
  FROM pg_class WHERE relname IN ('findings','opportunities','workspace_members');
-- expect: relrowsecurity = t AND relforcerowsecurity = t for all three

SELECT polname, polcmd, pg_get_expr(polqual, polrelid)      AS using_expr,
                        pg_get_expr(polwithcheck, polrelid) AS check_expr
  FROM pg_policy;
-- expect: check_expr NOT NULL for every policy
```

**Similar locations** — every future workspace-scoped table. Consider a CI assertion that every
table with a `workspace_id` column appears in `WORKSPACE_SCOPED_TABLES`, so the mixin can never
be forgotten again.

---

### TS-B01 — Client controls the payment amount; the webhook activates plans without validating it

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection — end-to-end requires live provider credentials) |
| **Severity** | **Critical** |
| **Category** | Business Logic / Unsafe Financial Processing |
| **Release-blocking** | **YES** |
| **Affected roles** | `admin`, `owner` (any workspace) |

**Location** — `backend/app/modules/billing/router.py:47,70-77`;
`backend/app/modules/billing/service.py:161-173` and `:226-237`

**Evidence**

The checkout request body accepts a client-supplied amount:

```python
class CheckoutBody(BaseModel):
    provider: str | None = None
    kind: str                      # paygo | subscription
    plan: str | None = None
    opportunity_id: str | None = None
    amount_minor: int | None = None      # ← client-supplied price
```

```python
if body.kind == "paygo":
    amount = body.amount_minor or PAYGO_PRICE_INR_PAISE
elif body.kind == "subscription":
    amount = body.amount_minor or SUBSCRIPTION_PRICES_INR_PAISE.get(body.plan or "", 0)
    if not amount:
        raise HTTPException(400, "unknown_subscription_plan")
```

`amount` is passed straight to `provider.create_order(...)` / `create_session(...)`, so the
provider charges whatever the client asked for. Note the secondary effect: supplying
`amount_minor` makes `amount` truthy, so the `unknown_subscription_plan` guard is bypassed and
`body.plan` becomes an arbitrary unvalidated string.

The webhook then activates the plan **without ever comparing the amount paid to the plan's price**:

```python
# service.py:161 — Razorpay
elif typ == "subscription.charged" and workspace_id:
    self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))   # no price check
```

```python
# service.py:226 — Stripe
elif kind == "subscription":
    self._workspaces().set_plan(workspace_id, metadata.get("plan", "pro"))  # no price check
```

**Attack**

```
POST /api/billing/checkout
Authorization: Bearer <any workspace admin token>
{"kind": "subscription", "plan": "scale", "amount_minor": 100}

→ provider order for ₹1.00 with notes {"workspace_id": "...", "plan": "scale"}
→ attacker completes a genuine ₹1 payment
→ provider sends a genuine, correctly-signed subscription.charged webhook
→ set_plan(workspace, "scale")     # ₹14,999/month plan, activated for ₹1
```

The critical property: **the webhook signature is valid.** The payment is real. Every existing
control — HMAC verification, idempotency, "the webhook is the only billing truth" — behaves
exactly as designed and still lets this through, because none of them checks *how much* was paid.
`CLAUDE.md` §4 requires "webhook is the only billing truth"; that invariant is satisfied while
the truth being asserted is unvalidated.

**Root cause**

Price is treated as request data rather than server-owned reference data. `SUBSCRIPTION_PRICES_INR_PAISE`
exists in the codebase as the authoritative price list but is used only as a *default*, never as a
*constraint* — and never at all on the activation side.

**Impact**

*Technical:* Any workspace admin sets their own price. Invoices record the ₹1 actually paid, so
reconciliation shows a paid invoice and the books look internally consistent.

*Business:* Direct, unbounded revenue loss with no anomaly signal. Currency confusion compounds
it — `amount` is computed from an INR paise table while `currency` is derived from the workspace's
country, so a `GB` workspace is charged the paise figure denominated in GBP (₹4,999.00 → £4,999.00
or £49.99 depending on provider interpretation). That is a live billing-correctness bug even with
no attacker.

**Recommended solution**

Two independent server-side controls — reject the client price, and validate at activation.

```python
# backend/app/modules/billing/plans.py — server-owned price table
SUBSCRIPTION_PRICES_MINOR: dict[str, dict[str, int]] = {
    "inr": {"pro": 4_999_00, "scale": 14_999_00},
    "gbp": {"pro":    49_00, "scale":    149_00},
    # … one entry per supported currency; never derive one currency's price from another's
}

def price_for(plan: str, currency: str) -> int:
    try:
        return SUBSCRIPTION_PRICES_MINOR[currency.lower()][plan]
    except KeyError:
        raise PaywallError("unknown_plan_or_currency") from None
```

```python
# backend/app/modules/billing/router.py — drop amount_minor from the request model
class CheckoutBody(BaseModel):
    provider: str | None = None
    kind: Literal["paygo", "subscription"]
    plan: Literal["pro", "scale"] | None = None
    opportunity_id: str | None = None
    # amount_minor removed — the price is server-owned (see plans.py)

if body.kind == "subscription":
    if body.plan is None:
        raise HTTPException(400, "plan_required")
    amount = price_for(body.plan, currency)
else:
    amount = paygo_price_for(currency)
```

```python
# backend/app/modules/billing/service.py — validate at activation, both providers
def _activate_subscription(self, workspace_id, plan: str, amount_paid: int, currency: str) -> None:
    if plan not in PLAN_LIMITS:
        logger.error("webhook named unknown plan %r for workspace %s", plan, workspace_id)
        return
    expected = price_for(plan, currency)
    if amount_paid < expected:
        # Underpayment: log loudly, do NOT activate. The invoice still records the payment.
        logger.error(
            "underpayment for workspace %s: paid %d %s, plan %r requires %d",
            workspace_id, amount_paid, currency, plan, expected,
        )
        return
    self._workspaces().set_plan(workspace_id, plan)
```

**Deployment considerations**

Before deploying, **reconcile existing paid workspaces**: query `invoices` joined to workspace
plan and flag any workspace on `pro`/`scale` whose paid invoices are below the plan price. Those
are either exploited or legitimately discounted, and must be resolved manually before the check
starts rejecting their renewals.

**Regression risks**

Medium. Any legitimate flow that passes `amount_minor` (discounts, proration, partial top-ups)
will break — see Q4 in §3.6. Grep confirms the frontend does not currently send it, so the
in-repo risk is low.

**Tests to add**

1. `test_checkout_rejects_client_amount` — `amount_minor` in the body is ignored/rejected.
2. `test_checkout_rejects_unknown_plan` — including when an amount is supplied.
3. `test_webhook_underpayment_does_not_activate` — signed `subscription.charged` for ₹1 against `scale` leaves the plan unchanged.
4. `test_webhook_exact_payment_activates`.
5. `test_price_currency_matches_workspace_country` — a `GB` workspace is quoted GBP, not paise-as-GBP.

**Verification** — `pytest tests/test_billing.py -q`, then replay a captured `subscription.charged`
webhook with a reduced amount against staging and confirm the plan does not change and an error
is logged.

**Similar locations** — the `paygo` path (`service.py:150`) records `review_paid` usage on
`order.paid` with no amount check either: the same ₹1 attack buys a ₹7,500 pay-as-you-go review.
Fix both in one change.

---

### TS-A04 — Workspace and project member lists are readable cross-tenant

| | |
|---|---|
| **Status** | Confirmed Defect — **reproduced end-to-end** |
| **Severity** | **High** |
| **Category** | IDOR / Information Disclosure |
| **Release-blocking** | **YES** |
| **Affected roles** | Any authenticated user |

**Location** — `backend/app/modules/auth/router.py:409-416` (`list_workspace_members`) and
`:462-469` (`list_project_members`); service methods `list_workspace_members` /
`list_project_members` in `auth/service.py`

**Evidence**

Both routes guard with `Depends(current_principal)` — authentication only, **no role check and
no membership check** — and both services query by the path ID alone:

```python
def list_workspace_members(self, workspace_id) -> list[dict]:
    rows = self.s.execute(
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))  # path param only
    ).all()
    return [{"user_id": ..., "email": user.email, "role": member.role} for member, user in rows]
```

`list_project_members` does not filter on `workspace_id` **at all** — only `project_id`.

**Reproduction** (probes B and E, verified):

```
GET /api/auth/workspaces/<victim_ws>/members        (attacker token)
→ 200 [{"user_id":"9167fa8c-…","email":"victim2@example.com","role":"owner"}]

GET /api/auth/projects/<victim_project>/members     (attacker token)
→ 200 [{"user_id":"c3cc1e6c-…","email":"v4@example.com","role":"owner"}]
```

**Root cause** Same class as TS-A01: the resource is addressed by a path ID that is never
associated with the caller. RLS would normally contain this, but `workspace_members` and
`project_members` carry no RLS policy (TS-A03 defect 4).

**Impact**

*Technical:* Enumeration of every user's email address and role, workspace by workspace. Given a
workspace UUID, an attacker learns exactly who holds `owner` and `admin` — a targeting list for
TS-A01 and for phishing.

*Business:* Personal-data disclosure under GDPR/DPDP. Reveals which contractors are collaborating
on which projects — commercially sensitive in a competitive-bidding context. Notably, this
finding **makes TS-A01 substantially easier to exploit at scale**: an attacker who obtains one
workspace UUID can map the entire organisation before escalating.

**Recommended solution** Apply the same `require_in_workspace` guard from TS-A01:

```python
@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    principal: Principal = Depends(require_in_workspace("viewer")),   # bound to the path
): ...
```

For projects, verify the project belongs to the caller's workspace before returning members:

```python
def list_project_members(self, workspace_id, project_id) -> list[dict]:
    project_id = uuid.UUID(str(project_id))
    project = self.s.scalar(select(Project).where(
        Project.id == project_id,
        Project.workspace_id == uuid.UUID(str(workspace_id)),   # ← the missing filter
    ))
    if not project:
        raise AuthError("no_such_project")
    ...
```

**Regression risks** Low — both are read-only endpoints and the frontend has no members UI (§3.5)
so nothing currently consumes them.

**Tests to add** Probes B and E as regression tests, plus the parametrized "every `{workspace_id}`
/ `{project_id}` route rejects foreign IDs" test from TS-A01.

**Similar locations** `GET /workspaces/{workspace_id}/projects` — `list_projects` *does* filter on
both `workspace_id` and `ProjectMember.user_id`, so it is safe; verified by reading the service.

---

### TS-A05 — Google sign-in with an existing email raises an unhandled 500

| | |
|---|---|
| **Status** | Confirmed Defect — **reproduced** |
| **Severity** | **High** |
| **Category** | Error Handling / Account Lifecycle |
| **Release-blocking** | **YES** (a permanent lockout for affected users) |
| **Affected roles** | Any user with a password account whose email matches their Google account |

**Location** — `backend/app/modules/auth/service.py`, `google_login()`

**Evidence** The lookup is by `google_sub` only. When a password account already exists with the
same email, no match is found and the code takes the "new user" branch, inserting a duplicate
email:

```python
user = self.s.scalar(select(User).where(User.google_sub == google_sub))
if not user:
    user = User(email=email, google_sub=google_sub, ...)   # violates users.email UNIQUE
```

Probe H:

```
POST /api/auth/google  {"id_token": "<valid token for dual@example.com>"}
→ sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: users.email
→ HTTP 500 (unhandled)
```

**Root cause** No account-linking policy. `apple_callback` handles this correctly — it falls back
to an email lookup when the verified flag is set — so the correct pattern exists in the same file
and was not applied to Google.

**Impact** Any user who signed up with a password and later clicks "Sign in with Google" gets a
500 and can never use Google sign-in. The raw `IntegrityError` may surface in error tracking with
the email attached. On a per-request session this leaves the transaction dirty.

**Recommended solution** This is a **product decision (Q3, §3.6)**, not purely technical, because
auto-linking on an attacker-controlled email is itself a takeover vector. The safe default is to
link **only when Google asserts `email_verified`**, mirroring Apple:

```python
user = self.s.scalar(select(User).where(User.google_sub == google_sub))
if not user and email and claims.get("email_verified"):
    user = self.s.scalar(select(User).where(User.email == email))
    if user:
        user.google_sub = google_sub          # link the identity
        user.email_verified = True
if not user:
    ... # create as today
```

Additionally wrap the commit so an unexpected `IntegrityError` returns 409 rather than 500:

```python
from sqlalchemy.exc import IntegrityError
try:
    self.s.commit()
except IntegrityError as exc:
    self.s.rollback()
    raise AuthError("email_taken") from exc
```

**Regression risks** Low, but note the security trade-off: if Google ever asserts `email_verified`
for an address it has not truly verified, linking grants access to the existing account. Gating on
`email_verified` is the industry-standard mitigation and matches the Apple path already shipped.

**Tests to add** `test_google_login_links_existing_verified_email`;
`test_google_login_rejects_unverified_email_collision` (asserts 409, not 500, and no linking).

**Similar locations** `apple_callback` — correct, but note it links on `email_verified` from Apple
*or* an existing `apple_id`; worth a security review of that branch under the same policy.

---

### TS-I01 — Uploads are fully buffered in memory before any size check

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Denial of Service / Resource Exhaustion |
| **Release-blocking** | **YES** at "millions of users" scale |
| **Affected roles** | `estimator` and above (authenticated) |

**Location** — `backend/app/modules/ingestion/router.py:126`;
`backend/app/core/storage.py` (`validate_and_store`, size check); `boq/router.py` upload route

**Evidence**

```python
data = await file.read()          # ← entire body into RAM, unbounded
stored = await validate_and_store(settings, file.filename, file.content_type, data, ...)
```

and inside `validate_and_store`, the size limit is applied **after** the bytes are already resident:

```python
size = len(data)                                                   # already in memory
limit = max_size or MAX_UPLOAD_SIZES.get(ext, DEFAULT_MAX_UPLOAD_SIZE)
if size > limit:
    raise ValidationError(f"file_too_large: limit {limit} bytes")   # too late
```

`MAX_UPLOAD_SIZES` permits 50 MB PDFs and 100 MB ZIPs, and `DEFAULT_MAX_UPLOAD_SIZE` is 100 MB —
but **nothing enforces a ceiling before the read**, so a client may send a body of any size and
the server buffers all of it before rejecting. The file is then held in memory through magic-number
detection, hashing, and the storage write — several full copies live simultaneously.

**Root cause** Validation ordering: the guard runs after the expensive operation it is meant to
guard. FastAPI's `UploadFile` spools to disk above a threshold, which mitigates but does not
eliminate this — disk is still consumed without limit, and `file.read()` pulls it all back into
RAM regardless.

**Impact** A handful of concurrent large uploads exhausts container memory and triggers OOM kills.
Because uploads are authenticated, a single compromised or malicious `estimator` account is
sufficient. At the stated scale this is also a routine-traffic capacity problem, not only an
attack.

**Recommended solution** Reject on `Content-Length` first, then stream with a hard cap:

```python
# backend/app/modules/ingestion/router.py
MAX_REQUEST_BYTES = 100 * 1024 * 1024

async def _read_capped(file: UploadFile, request: Request, cap: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and int(declared) > cap:
        raise HTTPException(413, "file_too_large")
    buf, total = bytearray(), 0
    while chunk := await file.read(1024 * 1024):        # 1 MiB at a time
        total += len(chunk)
        if total > cap:
            raise HTTPException(413, "file_too_large")   # abort before buffering more
        buf.extend(chunk)
    return bytes(buf)
```

Enforce the same cap at the reverse proxy (`client_max_body_size` in nginx, or the ALB/ingress
equivalent) so the limit holds even if application code regresses. For genuinely large documents,
prefer the existing tus resumable path (which already caps per chunk) over raw multipart.

**Deployment considerations** Set the proxy limit **at or slightly above** `MAX_REQUEST_BYTES` so
clients receive a clean 413 from the application rather than a connection reset from the proxy.

**Regression risks** Low. Legitimate uploads under the cap are unaffected. Verify the tus finalize
path (`tus.py`, `_finalize` → `file_path.read_bytes()`) — it has the same whole-file read, though
bounded by the per-upload `max_size`, so it is capped but still fully buffered.

**Tests to add** `test_upload_rejects_oversized_content_length` (413 without buffering);
`test_upload_rejects_oversized_stream` (lying `Content-Length`);
`test_upload_accepts_at_limit`.

**Similar locations** `boq/router.py` upload (`BOQ_MAX_UPLOAD_SIZE`, 10 MB — same pattern);
`ingestion/tus.py` `_finalize`; `baseline/router.py` award-document upload.

---

### TS-I02 — SSE progress endpoint busy-spins a CPU core per connected client

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Performance / Denial of Service |
| **Release-blocking** | **YES** if async processing is enabled at launch |
| **Affected roles** | Any `viewer` who opens a document-processing view |

**Location** — `backend/app/modules/ingestion/router.py:199-207`

**Evidence**

```python
def _events():
    result = AsyncResult(task_id, app=app)
    prev = {}
    while not result.ready():          # ← no sleep, no timeout, no disconnect check
        meta = result.info or {}
        if meta != prev:
            prev = meta.copy()
            yield _sse_event(meta.get("step", "progress"), meta)
    ...
return StreamingResponse(_events(), media_type="text/event-stream")
```

Three compounding defects:

1. **No sleep.** The loop polls `result.ready()` as fast as the CPU allows. This is a synchronous
   generator, so Starlette runs it in a threadpool worker — one saturated thread and effectively
   one pegged core per client, plus a Redis round-trip per iteration (thousands per second).
2. **No client-disconnect check.** `await request.is_disconnected()` is never consulted, so
   closing the browser tab does not stop the loop.
3. **No timeout.** A Celery task that hangs or dies without updating state loops forever. Combined
   with (2), threads are never reclaimed.

Starlette's threadpool defaults to ~40 workers. **Forty concurrent document uploads exhaust the
pool and the entire application stops serving requests** — including health checks, which would
cause the orchestrator to cycle pods under load.

**Root cause** A polling loop written as if it were async, without the `await asyncio.sleep()`
that would make polling cooperative.

**Recommended solution** Make it a genuine async generator with backoff, a disconnect check, and a
hard timeout:

```python
# backend/app/modules/ingestion/router.py
import asyncio, time

SSE_POLL_SECONDS = 1.0
SSE_MAX_SECONDS = 15 * 60

async def _events():
    app_celery = request.app.state.ctx.registry.get("celery.app")
    if not app_celery:
        yield _sse_event("error", "celery not configured")
        return
    result = AsyncResult(task_id, app=app_celery)
    prev, started = {}, time.monotonic()
    while not result.ready():
        if await request.is_disconnected():
            return                                    # client left — stop immediately
        if time.monotonic() - started > SSE_MAX_SECONDS:
            yield _sse_event("error", "timeout")
            return
        meta = result.info or {}
        if meta != prev:
            prev = dict(meta)
            yield _sse_event(meta.get("step", "progress"), meta)
        else:
            yield ": keep-alive\n\n"                  # keeps proxies from closing the stream
        await asyncio.sleep(SSE_POLL_SECONDS)          # ← yields the event loop
    yield _sse_event("done" if result.successful() else "error",
                     result.result if result.successful() else str(result.result))
```

Note `prev = dict(meta)` rather than `meta.copy()` — `result.info` is not guaranteed to be a dict
and may be an exception instance on failure, where `.copy()` raises.

**Deployment considerations** Long-lived SSE connections need proxy read timeouts raised above
`SSE_MAX_SECONDS` (nginx `proxy_read_timeout`, ALB idle timeout) or the stream is cut mid-flight.
The keep-alive comment above mitigates this. Each open SSE connection also holds a worker
connection slot — size the pool against expected concurrent uploads.

**Regression risks** Low; the event contract is unchanged. The 1 s poll interval adds up to one
second of latency to progress updates, which is imperceptible for multi-second document processing.

**Tests to add** `test_sse_stops_on_client_disconnect`; `test_sse_times_out`;
`test_sse_emits_progress_then_done`. A load test asserting CPU stays flat with 50 concurrent
streams would directly target the defect.

**Similar locations** `grep -rn "while not.*ready()\|while True" backend/app/` — no other
occurrences found, so this is isolated.

---

### TS-B02 — Webhook processing is not atomic; idempotency check is racy

| | |
|---|---|
| **Status** | Probable Risk (by inspection; not reproduced under load) |
| **Severity** | **High** |
| **Category** | Concurrency / Data Integrity / Financial |
| **Release-blocking** | No — but fix before meaningful payment volume |
| **Affected roles** | All paying workspaces |

**Location** — `backend/app/modules/billing/service.py:142-186` (Razorpay) and `:197-248` (Stripe)

**Evidence** The duplicate check and the marker insert are separated by the entire side-effecting
body, and each intermediate step commits independently:

```python
if event_id and self.s.scalar(                      # ← check
    select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)
):
    return {"ok": True, "duplicate": True}
...
self.record_usage(workspace_id, ...)                # commits
self.create_invoice(workspace_id, ...)              # commits
self._workspaces().set_plan(workspace_id, ...)      # commits
...
self.s.add(WebhookEvent(...))                       # ← marker written last
self.s.commit()
```

Two concurrent deliveries of the same `event_id` — which both Razorpay and Stripe do on retry, and
which are common when the first response is slow — both pass the check before either writes the
marker. Result: duplicate `review_paid` usage credits and duplicate invoices.

Compounding: because `record_usage` and `create_invoice` each commit separately, a failure between
them leaves **partially applied financial state** with no rollback. A crash after `create_invoice`
but before the `WebhookEvent` insert means the retry re-applies everything, producing a second
invoice for one payment.

**Root cause** Check-then-act across multiple transactions, with no unique constraint enforcing the
invariant at the database level.

**Impact** Double-credited paid reviews (revenue loss) and duplicate invoices (reconciliation and
tax-filing errors — India GST filings are derived from invoice records). Partial application
produces states no code path expects, e.g. a plan set with no invoice.

**Recommended solution** Insert the idempotency marker **first**, inside the same transaction as
the effects, and let a unique constraint arbitrate the race:

```python
# migration — make the race impossible at the database level
op.create_unique_constraint(
    "uq_webhook_events_provider_event", "webhook_events", ["provider", "provider_event_id"]
)
```

```python
# backend/app/modules/billing/service.py
from sqlalchemy.exc import IntegrityError

def _claim_event(self, provider: str, event_id: str, workspace_id) -> bool:
    """Insert the idempotency marker first. Returns False if already claimed."""
    if not event_id:
        return True
    try:
        with self.s.begin_nested():
            self.s.add(WebhookEvent(
                workspace_id=uuid.UUID(str(workspace_id)) if workspace_id else uuid.UUID(int=0),
                provider=provider,
                provider_event_id=event_id,
            ))
        return True
    except IntegrityError:
        return False        # a concurrent delivery won the race

def process_razorpay_webhook(self, raw_body, signature, secret) -> dict:
    ...
    if not verified:
        return {"ok": False, "reason": "bad_signature"}
    if not self._claim_event("razorpay", event_id, workspace_id):
        return {"ok": True, "duplicate": True}
    try:
        # all effects in ONE transaction — no intermediate commits
        self._apply_razorpay_effect(typ, workspace_id, notes, amount, event_id, evt)
        self.s.commit()
    except Exception:
        self.s.rollback()          # marker rolls back too, so the provider retry can re-apply
        raise
    return {"ok": True, "applied": typ}
```

This requires `record_usage` and `create_invoice` to stop committing internally — pass a
`commit: bool = True` flag, or better, move commit control entirely to the caller.

**Database considerations** Adding the unique constraint requires de-duplicating existing
`webhook_events` rows first. Check for duplicates before the migration:

```sql
SELECT provider, provider_event_id, count(*)
  FROM webhook_events GROUP BY 1, 2 HAVING count(*) > 1;
```

**Regression risks** Medium — this changes transaction boundaries across the billing module.
`create_invoice` currently relies on `flush()` to obtain an id before setting `invoice_number`;
that still works inside a larger transaction, but the tests must be re-run carefully.

**Tests to add** `test_concurrent_identical_webhooks_apply_once` (two threads, real DB);
`test_webhook_failure_rolls_back_completely`;
`test_webhook_retry_after_failure_applies` (the marker must not block a legitimate retry).

**Similar locations** `process_stripe_webhook` — identical structure, same fix.
`auth/service.py accept_invitation` has a comparable check-then-act on `invitation.used_at`,
allowing an invitation to be accepted twice concurrently (lower impact — idempotent in effect).

---

### TS-F01 — Frontend/backend contract mismatch breaks the session provider

| | |
|---|---|
| **Status** | Confirmed Defect (backend response shape verified empirically; frontend by inspection) |
| **Severity** | **High** |
| **Category** | API Contract / Frontend Reliability |
| **Release-blocking** | **YES** — likely a blank screen after sign-in |
| **Affected roles** | All signed-in users |

**Location** — `frontend/lib/api.ts:89`; `frontend/components/session.tsx:58,50,109`;
`backend/app/modules/auth/router.py:365-371`

**Evidence** The client expects an object wrapper with an `id` field:

```ts
// frontend/lib/api.ts:89
listWorkspaces: (token: string) =>
  req<{ workspaces: Workspace[] }>("/auth/workspaces", {}, token),
// Workspace = { id: string; name: string; plan: string; country: string; role: string }
```

The backend returns a **bare array** with `workspace_id`, and no `plan` or `country`. Captured
directly during probe A:

```json
[{"workspace_id": "52b427fd-…", "name": "Attacker Ltd", "role": "owner"}]
```

The failure chain in `session.tsx`:

```ts
const { workspaces: list } = await api.listWorkspaces(token);  // destructuring an ARRAY → undefined
setWorkspaces(list);                                           // state becomes undefined
...
const activeWorkspace = workspaces.find((w) => w.id === session?.workspaceId) ?? null;
//                      ^^^^^^^^^^^^^^^ TypeError: Cannot read properties of undefined
```

Destructuring `workspaces` from an array does **not** throw — it yields `undefined` — so the
`try/catch` in `loadWorkspaces` (which returns `[]` on error) never fires. `setWorkspaces(undefined)`
succeeds, and the next render throws at line 109, unwinding the whole `SessionProvider` subtree.
Even if a guard were added, `w.id` would never match because the field is named `workspace_id`.

This passes `tsc --noEmit` because the response type is *asserted* by the generic parameter of
`req<T>()`, never validated at runtime — the compiler is told what to believe.

**Root cause** No shared, machine-checked API contract. The backend returns unwrapped lists in
some places (`GET /auth/workspaces`) and wrapped objects in others (`GET /billing/invoices` →
`{"invoices": [...]}`), and the TypeScript client encodes one guess per endpoint with nothing
verifying it.

**Impact** The workspace switcher — shipped in TS-085/TS-088 specifically to support multi-workspace
users — cannot work. Most likely the app renders blank after sign-in. Since `SessionProvider`
wraps the application (`app/layout.tsx`), the blast radius is every authenticated page.

> **Not runtime-verified.** No browser was available (§1.6). The backend shape is confirmed
> empirically; the frontend consequence is traced through source. Reproduce in a browser before
> sizing the fix.

**Recommended solution** Fix the backend to match the documented contract (wrapped, with `id`),
since the frontend shape is the more conventional one and `adminWorkspaces` already expects the
same wrapper:

```python
# backend/app/modules/auth/service.py
def list_workspaces(self, user_id) -> dict:
    rows = self.s.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == uuid.UUID(str(user_id)))
        .order_by(Workspace.created_at)
    ).all()
    return {
        "workspaces": [
            {
                "id": str(ws.id),          # ← matches the client's Workspace type
                "name": ws.name,
                "plan": ws.plan,
                "country": ws.country,
                "role": m.role,
            }
            for ws, m in rows
        ]
    }
```

Then defend the client against the class of bug:

```ts
const res = await api.listWorkspaces(token);
const list = Array.isArray(res) ? res : res?.workspaces ?? [];   // tolerate either shape
setWorkspaces(list);
```

**Structural fix (recommended):** serve the FastAPI OpenAPI schema and generate the TypeScript
client from it in CI. That makes this entire finding class impossible rather than fixing one
instance. Alternatively, declare Pydantic `response_model`s on every route and validate client
responses with `zod`.

**Regression risks** Low if the client tolerates both shapes during rollout (deploy the frontend
tolerance first, then change the backend, avoiding a coordinated deploy).

**Tests to add** `test_list_workspaces_response_shape` (backend, asserts the wrapper and `id`);
a frontend unit test rendering `SessionProvider` against a mocked response; an end-to-end
sign-in-and-switch test. **An end-to-end test would have caught this and no existing test could
have** — the backend tests assert on the current shape, and the frontend has no tests at all.

**Similar locations** Audit every `req<T>()` call site in `lib/api.ts` (82 endpoints) against the
actual backend response. `adminWorkspaces` (`api.ts:97`) expects `{workspaces}` from
`GET /auth/admin/workspaces` — verify `list_all_workspaces()` returns the wrapper. Given one
confirmed mismatch and no runtime validation anywhere, **assume others exist until checked.**

---

### TS-O01 — Rate limiting is ineffective across instances and behind a proxy

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Security Control / Availability |
| **Release-blocking** | **YES** — the brute-force control does not function as designed |
| **Affected roles** | All (protective control) |

**Location** — `backend/app/core/ratelimit.py:79-95` (Redis backend) and `:125-138` (`RateLimitDep`)

**Two independent defects.**

**(a) The Redis backend uses `time.monotonic()` as the sorted-set score.**

```python
async def is_allowed(self, key: str, limit: int, window: float) -> bool:
    now = time.monotonic()                       # ← per-process arbitrary epoch
    pipe.zremrangebyscore(key, 0, now - window)
    ...
    pipe.zadd(key, {str(now): now})
```

`time.monotonic()` is documented as having an **undefined reference point**, valid only for
measuring intervals *within a single process*. Two application instances writing to the same Redis
key produce scores on unrelated scales. Depending on which process started first, the trimming
window either evicts every entry immediately (no rate limiting at all) or evicts nothing (users
permanently locked out after the first burst). Redis is only used in multi-instance deployments —
so **the backend is broken precisely in the configuration it exists to serve.** Restarting a
process also shifts its epoch, changing behaviour non-deterministically.

**(b) The bucket key uses the socket peer address with no proxy-header handling.**

```python
client = request.client
host = client.host if client else "unknown"
key = f"{host}:{request.url.path}"
```

Behind a load balancer or ingress (`§2.7` assumption 3), `request.client.host` is the **proxy's**
address for every request. All users worldwide share one bucket per path. With `_LOGIN_LIMIT` at
5 requests/60 s, **the sixth legitimate login attempt across the entire platform fails with 429** —
a self-inflicted denial of service. Conversely a real attacker rotating source IPs is not
constrained at all, since the key ignores their address anyway.

**Root cause** (a) is a misunderstanding of `monotonic()`'s contract — correct for the in-memory
backend it was presumably copied from, invalid the moment state is shared. (b) is missing
`ProxyHeadersMiddleware`; `main.py` adds `HTTPSRedirect`, `TrustedHost`, `CORS`, and
`SecurityHeaders` but never trusts `X-Forwarded-For`.

**Impact** The primary defence against credential stuffing against `/api/auth/login` either does
not apply or locks out all legitimate users. Given TS-A01 and TS-A02 (which both need only one
authenticated account), effective login rate limiting is more than usually load-bearing here.

**Recommended solution**

```python
# backend/app/core/ratelimit.py — wall-clock scores, shareable across processes
class RedisRateLimitStorage:
    async def is_allowed(self, key: str, limit: int, window: float) -> bool:
        now = time.time()                       # ← epoch-based, comparable across processes
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zadd(key, {f"{now}:{secrets.token_hex(4)}": now})   # unique member per attempt
        pipe.pexpire(key, int(window * 1000))
        _, count, _, _ = await pipe.execute()
        return count < limit
```

The unique member suffix also fixes a latent bug: `zadd(key, {str(now): now})` uses the timestamp
as the member name, so two attempts within the same float tick overwrite rather than accumulate,
undercounting the window.

```python
# backend/app/core/ratelimit.py — trust the proxy chain, but only a configured depth
def _client_ip(request: Request, trusted_hops: int) -> str:
    if trusted_hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        chain = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(chain) >= trusted_hops:
            return chain[-trusted_hops]        # count from the right; the left is client-spoofable
    return request.client.host if request.client else "unknown"
```

Add `TS_TRUSTED_PROXY_HOPS: int = 0` to `Settings`. Defaulting to 0 keeps direct-connection
deployments correct, and it must be set to the real hop count in production.

**Deployment considerations** `trusted_hops` must exactly match the infrastructure. Too high and a
client spoofs `X-Forwarded-For` to evade limits; too low and the proxy IP is used, restoring
defect (b). Verify against the actual ALB/ingress configuration, and note that
`_validate_prod_settings` should require `TS_REDIS_URL` in production — currently a multi-instance
production deployment silently falls back to per-instance in-memory limiting, where the effective
limit is `5 × instance_count`.

**Regression risks** Low for (a). For (b), a misconfigured `trusted_hops` degrades limiting rather
than breaking functionality — but the failure is silent, so add a startup log line recording the
resolved client IP strategy.

**Tests to add** `test_redis_ratelimit_shared_across_processes` (two clients, one Redis);
`test_ratelimit_uses_forwarded_for_when_configured`;
`test_ratelimit_ignores_forwarded_for_when_hops_zero` (the anti-spoofing test);
`test_same_tick_attempts_both_counted`.

**Similar locations** `RateLimiter.peek()` shares the `count()` path and inherits (a).
`notifications/module.py:26` uses a Redis lock with a 23-hour timeout — correct there, but review
it alongside this fix.

---

### Medium-severity findings

The following are summarised rather than given the full treatment above; none is release-blocking.

---

**TS-O02 — No observability: no metrics, no tracing, no error tracking, no documented backups**
*Design Concern · Medium · `docs/deployment.md` (65 lines), whole repo*

`grep` for `backup`, `rollback`, `restore`, `monitor`, `alert`, `Sentry`, `observab` across
`docs/deployment.md` returns **zero matches**. There is no metrics endpoint, no structured logging
configuration, no trace propagation, and no error-tracking integration anywhere in the codebase.
`/api/health` returns a static `{"status": "ok", "version": "0.1.0"}` — it does not check database
connectivity, Redis, storage, or the Celery broker, so an orchestrator liveness probe reports
healthy while every dependency is down.

*Recommendation:* add `prometheus-fastapi-instrumentator` for RED metrics; add Sentry (or
equivalent) for exceptions; make `/api/health` a real dependency check with a separate
`/api/health/live` for liveness vs `/api/health/ready` for readiness; document RPO/RTO, PostgreSQL
PITR configuration, S3 versioning, and a tested rollback procedure. Alert at minimum on 5xx rate,
webhook signature failures, Celery queue depth, and failed logins per account.

---

**TS-I03 — tus resumable upload is non-functional and not multi-instance safe**
*Confirmed Defect · Medium · `backend/app/modules/ingestion/tus.py:34,90-115`*

Three issues: (1) `tus_create` returns `{}` with HTTP 200 and **no `Location` header** — the tus
1.0 protocol requires `201 Created` plus `Location`, so a standard tus client cannot discover the
upload id and the flow is unusable; (2) `UPLOAD_DIR = pathlib.Path("/tmp/tender-shield-tus")` is
node-local, so a resumed `PATCH` routed to a different pod returns 404 — resumability, the entire
point of tus, does not survive load balancing; (3) no expiry or cleanup of abandoned `.part`
files, an unbounded disk leak on a `/tmp` filling silently. Also `_load_state`/`_file_path`
interpolate the `upload_id` path parameter into a filesystem path without validating it is a hex
UUID (low exploitability, but free to fix).

*Recommendation:* return `201` with `Location`; move chunk state to Redis or S3 multipart upload;
add a TTL sweeper; validate `upload_id` with `re.fullmatch(r"[0-9a-f]{32}", upload_id)`.

---

**TS-N01 — Deadline alerts re-send daily with no deduplication, via an N+1 scan**
*Confirmed Defect · Medium · `backend/app/modules/notifications/module.py:47-82`*

`_deadline_alert_tick` runs every 24 h and emails **every member** about **every unconfirmed
deadline** falling within the next 7 days. Nothing records that an alert was already sent, so the
same deadline generates an email to every member **every day for seven consecutive days**. A
workspace with 10 members and 5 live tenders averaging 4 deadlines each receives 200 emails/day.
The scan is also a nested N+1 (workspaces × opportunities × deadlines × members) with no
pagination, executed in a single session while holding a 23-hour Redis lock.

*Recommendation:* add a `deadline_alerts_sent(deadline_id, member_id, threshold_days)` table and
send only on threshold crossings (e.g. 7/3/1 days); batch the queries; add per-user notification
preferences (§3.5 item 9). See Q6 in §3.6 — confirm the intended cadence first.

---

**TS-P01 — Untrusted tender text reaches the LLM without delimiting or neutralization**
*Design Concern · Medium · `backend/app/modules/assistant/agent.py:31-46`*

`CLAUDE.md` §4 requires that "tender text is untrusted input — prompt-injection defenses apply
everywhere document text meets an LLM" (Build Doc §11.3). The current defence is a system-prompt
instruction ("Answer ONLY from the TOOL RESULTS provided"), and tool results — which contain
verbatim `source_quote` text extracted from customer-uploaded PDFs — are interpolated into the
user turn as raw JSON with no structural separation:

```python
"content": (f"QUESTION: {message}\n\nTOOL RESULTS (the only facts you may use):\n"
            f"{json.dumps(context, default=str)}")
```

A tender document containing adversarial instructions is presented to the model in the same trust
context as the user's question. Impact is bounded — the agent has no tool-calling ability and can
only return text — so the realistic harm is misleading risk analysis rather than data exfiltration.
That is still material for a product whose entire value is trustworthy risk assessment.

*Recommendation:* wrap document-derived content in explicit delimiters with a standing instruction
that content inside them is data and never instructions; strip or escape delimiter sequences from
the extracted text; keep the deterministic path (which needs no LLM) as the default. Add
adversarial fixtures to `evals/` containing injection attempts and assert the assistant does not
comply.

---

**TS-S01 — Virus scanning is a no-op stub**
*Confirmed Defect · Medium · `backend/app/core/storage.py:200-202`*

```python
def _scan_stub(_data: bytes) -> None:
    """Placeholder virus scan. Production should call a sandboxed scanner or API."""
    return
```

Called on every upload with `scan=True`, and does nothing. Uploaded files are stored and later
served back through `/api/files/{key}` with `Content-Disposition: attachment`, so browser-side
execution risk is limited — but the platform becomes a malware distribution channel between
collaborating contractors. Carried forward from the previous audit; still unaddressed.

*Recommendation:* integrate ClamAV (via `clamd`) or an equivalent scanning API, run it in the async
processing path rather than the request path, and quarantine rather than delete on detection so
false positives are recoverable. Fail closed in production if the scanner is unreachable.

---

**TS-X01 — Cross-module foreign key violates the stated architecture and breaks module-subset boot**
*Confirmed Defect · Medium · `backend/app/modules/findings/models.py`*

`CLAUDE.md` §2 states: "Foreign keys may reference core tables (orgs/users) but not another
module's tables directly; use IDs + events." `findings.opportunity_id` declares a foreign key to
`opportunities`, a table owned by the `ingestion` module.

**Reproduced during this audit:** enabling `findings` without `ingestion` raises
`sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'findings.opportunity_id'
could not find table 'opportunities'`, breaking the "app must boot with any subset of modules"
guarantee (spec core B2). `tests/test_architecture.py` cannot catch this because it inspects Python
imports, not SQLAlchemy metadata.

*Recommendation:* drop the FK constraint and keep `opportunity_id` as a plain indexed `Uuid`, with
referential integrity maintained via events (the pattern the architecture already prescribes). Add
an architecture test asserting that no module's tables declare a `ForeignKey` to a table owned by
another module. Audit all model files for the same pattern — `baselines`, `artifacts`,
`chat_sessions`, `deadlines`, `doc_chunks`, and `clauses` all carry an `opportunity_id`.

---

**TS-B03 — Seat limits are defined but never enforced**
*Confirmed Defect · Medium · `backend/app/modules/billing/plans.py:9-14`*

`PLAN_LIMITS` defines `seats` for every plan (free 2, paygo 3, pro 10, scale 25). `grep -rn "seats"
backend/app/` shows the key is **never read anywhere**. `add_workspace_member` and
`accept_invitation` perform no seat check, so a free workspace can add unlimited members. Since
seats are a priced dimension of every plan, this is direct revenue leakage — and it is the second
instance (with TS-B01) of a documented commercial constraint existing as data but never enforced
in code.

*Recommendation:* enforce in `add_workspace_member` and `accept_invitation`, raising a
`PaywallError` with an upsell payload consistent with the existing paywall pattern. See Q5 in §3.6.

---

**TS-S02 — Production startup guard is incomplete**
*Design Concern · Medium · `backend/app/main.py:56-79`*

`_validate_prod_settings` is a good pattern with gaps. It requires `TS_RAZORPAY_WEBHOOK_SECRET`
but **not** `TS_STRIPE_WEBHOOK_SECRET`, so a Stripe-billed deployment starts with unverifiable
webhooks (it fails closed, returning 400 — no revenue is stolen, but no payment is ever activated
either: a silent total billing outage). It also does not require `TS_REDIS_URL` (see TS-O01), does
not validate that `cookie_samesite="none"` is paired with `Secure`, applies the weak-secret check
only to Razorpay, and does not verify that the JWT keys parse as a valid RSA keypair — a malformed
PEM fails at first login rather than at boot.

*Recommendation:* extend the guard to cover all of the above; parse the keypair at startup and
fail fast; require at least one notification sender in production.

---

**TS-O03 — No branch protection, no CODEOWNERS, no default branch convention**
*Design Concern · Medium · repository configuration*

All 13 branches report `"protected": false`, and there is no `main`/`master` branch (§2.0). There
is no `CODEOWNERS`, no PR template, and no required-review configuration. CI runs on every push and
PR (good) but nothing prevents a direct push of unreviewed code to the de-facto trunk. For a
codebase handling payments and multi-tenant commercial data, unenforced review is a governance gap.

*Recommendation:* designate and protect a default branch; require PR review plus green CI before
merge; add `CODEOWNERS` for `auth/`, `billing/`, and `core/`.

---

### Low-severity findings

**TS-L01 — `/api/health/details` is unauthenticated outside production.**
`health/router.py:48` gates on `settings.is_prod()`, so staging and any non-`prod` environment
expose the full module inventory, failed-module list, and registry capability names to anonymous
callers — a useful reconnaissance map. *Fix:* require super-admin whenever auth is loaded,
regardless of environment.

**TS-L02 — No pagination on any list endpoint.** `GET /ingestion/opportunities`,
`/findings/opportunities/{id}`, `/billing/invoices`, `/auth/workspaces/{id}/members`, and
`/assistant/sessions` all return complete result sets. Only `crossref` accepts a `limit`. Response
sizes and query cost grow unbounded with tenant age. *Fix:* add cursor pagination with a default
and maximum page size.

**TS-L03 — Accessibility not established.** Across `frontend/app/` and `frontend/components/`
there are 12 `<input>` elements and 10 `<label>` elements, with 10 total occurrences of
`aria-*`/`role=`/`alt=` attributes in the entire frontend. No skip link, no focus-trap handling in
modals, no automated a11y check in CI. **This is Not Tested rather than Failed** — no browser or
screen reader was available (§1.6), and the shared `Field` component may associate labels
correctly. *Fix:* add `eslint-plugin-jsx-a11y` and `axe-core` to CI, then re-assess against WCAG
2.1 AA.

**TS-L04 — `pip install -e ".[dev]"` fails on Debian system Python.** Reproduced:
`ERROR: Cannot uninstall PyJWT 2.7.0, RECORD file not found. Hint: The package was installed by
debian.` The audit worked around this with a virtualenv. CI is unaffected (it uses
`actions/setup-python`), but a new contributor following the README hits this immediately.
*Fix:* document the virtualenv requirement in `README.md`, or add `--ignore-installed PyJWT` to the
documented command.

---

## 5. Remediation Plan

### 5.1 Immediate release blockers — Critical (fix first, in this order)

| # | ID | Fix | Est. |
|---|---|---|---|
| 1 | **TS-A01** | Bind workspace-scoped routes to the caller's workspace; add service-level membership checks; audit existing membership rows for prior exploitation | 1 day |
| 2 | **TS-A02** | Use `member.role` in `google_login`; unify the token-issuing tail across all three providers | 2 hours |
| 3 | **TS-B01** | Remove `amount_minor` from the request model; server-owned per-currency price table; validate amount at webhook activation | 1 day |
| 4 | **TS-A03** | `FORCE ROW LEVEL SECURITY` + `WITH CHECK` + `current_setting(…, true)`; cover membership tables; **add PostgreSQL to CI** | 2–3 days |

Order matters: 1 and 2 are the actively exploitable paths and are small, self-contained changes.
4 is the highest-regression-risk change and needs a staging soak, so start it in parallel but ship
it behind the others.

### 5.2 Required pre-release — High

| # | ID | Fix | Est. |
|---|---|---|---|
| 5 | **TS-A04** | Membership checks on member-list endpoints | 2 hours |
| 6 | **TS-A05** | Google account linking on verified email; handle `IntegrityError` as 409 | 3 hours |
| 7 | **TS-I01** | Cap `Content-Length`, stream with a hard limit, enforce at the proxy | 4 hours |
| 8 | **TS-I02** | Async SSE generator with sleep, disconnect check, and timeout | 3 hours |
| 9 | **TS-F01** | Align the `/auth/workspaces` contract; tolerate both shapes client-side; **verify in a browser** | 4 hours |
| 10 | **TS-O01** | Wall-clock Redis scores; `ProxyHeadersMiddleware` with configured hop count | 4 hours |
| 11 | **TS-B02** | Claim the idempotency marker first; single transaction; unique constraint | 1 day |

Also required before a multi-user launch, from §3.5: **team-management UI**, **account/security
settings UI**, and **member removal + invitation revocation**. These are capability gaps rather
than defects, but shipping multi-tenant collaboration without any way to remove a member is not
defensible.

### 5.3 Short-term improvements (first month post-launch)

TS-O02 (observability, real health checks, documented backup/rollback — arguably should be
pre-launch), TS-I03 (tus), TS-N01 (alert dedup), TS-S01 (virus scanning), TS-B03 (seat
enforcement), TS-S02 (startup guard), TS-O03 (branch protection), TS-L01, TS-L02, TS-L04.
Add the cross-opportunity work queue and reviewer inbox (§3.4).

### 5.4 Long-term architectural improvements

1. **Generate the TypeScript client from the OpenAPI schema in CI.** Eliminates the entire TS-F01
   class rather than one instance.
2. **Centralize resource-scoped authorization.** TS-A01, TS-A02, and TS-A04 are three instances of
   one pattern: the role guard is not bound to the resource. A single `require_in_workspace`
   dependency plus a CI assertion that every route with a `{workspace_id}`/`{project_id}` path
   parameter uses it would make the class structurally impossible.
3. **Run the integration suite against PostgreSQL in CI**, not only SQLite. The RLS defects
   survived because no test could observe them.
4. **Add end-to-end tests** (Playwright is already available in this environment). No test
   currently crosses the frontend/backend boundary, which is exactly where TS-F01 lives.
5. **Complete the audit log** to cover authentication, membership, role, billing, and export
   events — needed for both compliance and incident response.
6. **Formalize prompt-injection defenses** (TS-P01) with adversarial fixtures in `evals/`.

---

## 6. Residual Risks and Final Checklist

### 6.1 Readiness assessment by area

Nothing is marked **Pass** without executed evidence.

| Area | Status | Evidence / reason |
|---|---|---|
| Build (backend) | **Pass** | `pip install` + import of all 20 modules succeeds; 145 tests run |
| Build (frontend) | **Pass** | `npm run build` — 12 routes compiled |
| Lint (backend) | **Pass** | `ruff check .` — All checks passed |
| Lint (frontend) | **Pass** | `npm run lint` — no errors |
| Type checking (backend) | **Pass** | `mypy app` — 143 files, no issues |
| Type checking (frontend) | **Pass** | `tsc --noEmit` |
| Unit / integration tests | **Pass** | 145 passed, 1 skipped |
| End-to-end tests | **Fail** | None exist. TS-F01 is exactly what E2E would catch |
| Dependency vulnerabilities (frontend) | **Pass** | `npm audit --audit-level=high` — 0 vulnerabilities |
| Dependency vulnerabilities (backend) | **Not Tested** | `pip-audit` runs in CI and is green; not independently re-run here |
| Secret scanning | **Pass** | All four `.env.*` files read in full — placeholders only, no real secrets |
| Authentication | **Partial** | Primitives strong; **TS-A02** and **TS-A05** are defects in the OIDC path |
| Authorization | **Fail** | **TS-A01**, **TS-A04** — role guards not bound to the target resource |
| Tenant isolation | **Fail** | **TS-A01** reproduced; **TS-A03** — the database backstop is inoperative |
| Payment processing | **Fail** | **TS-B01** — client-set price, no validation at activation |
| Input validation | **Partial** | Pydantic models thorough; **TS-I01** — size checked after buffering |
| File upload security | **Partial** | Extension + magic + size validated; **TS-S01** — scanning is a stub |
| SQL injection | **Pass** | Full review of all service files: SQLAlchemy Core/ORM throughout; the only `text()` is `bind_workspace_context`, correctly parameterized |
| Path traversal | **Pass** | Probes D and F — three traversal variants blocked (404) |
| XSS | **Not Tested** | React auto-escaping applies; no `dangerouslySetInnerHTML` found; not verified in a browser |
| CSRF | **Partial** | Bearer tokens in headers are inherently CSRF-resistant; refresh cookie is `SameSite=lax`, `path=/api/auth`. `POST /api/auth/refresh` reads the cookie and could be triggered cross-site — impact limited to token rotation. Not verified in a browser |
| Security headers | **Pass** | `SecurityHeadersMiddleware` sets CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`; HSTS delegated to the proxy |
| Rate limiting | **Fail** | **TS-O01** — broken across instances and behind a proxy |
| Database migrations | **Partial** | Alembic up/down verified in CI on SQLite; **not verified on PostgreSQL**, where the RLS block lives |
| Database indexes | **Partial** | 22 `index=True` declarations covering `workspace_id` and FK columns; no composite indexes for the common `(workspace_id, opportunity_id)` filter; no query plans measured |
| Transactions | **Fail** | **TS-B02** — financial effects split across multiple commits |
| Concurrency | **Partial** | **TS-B02** identified by inspection; no concurrency testing performed |
| Performance | **Not Tested** | No load testing. **TS-I01** and **TS-I02** identified by inspection |
| Caching | **Not Applicable** | No caching layer implemented; not required at current scale |
| Accessibility | **Not Tested** | No browser or screen reader available. Static scan suggests gaps (**TS-L03**) |
| Responsive design | **Not Tested** | Tailwind responsive classes present; not verified at any viewport |
| Error handling | **Partial** | Consistent `AuthError` → HTTP mapping; **TS-A05** shows an unhandled path |
| Logging | **Partial** | `logging` used consistently; unstructured, no correlation IDs, no PII policy |
| Monitoring / alerting | **Fail** | **TS-O02** — none exists |
| Health checks | **Fail** | `/api/health` is static; checks no dependency |
| Backups / restore | **Fail** | **TS-O02** — not documented, not configured, never tested |
| Rollback procedure | **Fail** | Not documented |
| CI/CD | **Partial** | CI is thorough (lint, types, audit, tests, migrations, both stacks); **TS-O03** — no branch protection, no CD pipeline |
| Documentation | **Pass** | Build doc, 20 module specs, task backlog, changelog — unusually thorough and current |
| Architecture compliance | **Partial** | Module boundaries enforced by test and genuinely respected; **TS-X01** — one cross-module FK |

### 6.2 The most important residual risk

**TS-A03 was not verified by execution.** No PostgreSQL instance was available, and the entire
test suite runs on SQLite where `bind_workspace_context` is a documented no-op. The analysis rests
on three facts that are individually certain — PostgreSQL RLS does not apply to table owners
without `FORCE`; `docker-compose.yml` defines a single role that both migrates and serves; the
generated SQL contains neither `FORCE` nor `WITH CHECK` — but their combined effect on the real
production database has not been observed.

**This must be verified before release**, using the `pg_class` / `pg_policy` queries in TS-A03
against a real staging database, connected as the application's actual production role. If
production already uses a separate non-owner role, TS-A03 drops from Critical to Medium (the
`WITH CHECK` and membership-table gaps remain). This is Q1 in §3.6 and is the single highest-value
open question in this audit.

### 6.3 Other unresolved and unverified risks

1. **Other API contract mismatches (TS-F01 class).** One confirmed mismatch out of 82 client
   endpoints, with no runtime response validation anywhere. **Assume others exist until each is
   checked.**
2. **Accessibility is unknown, not merely imperfect.** The static signal is weak but a static scan
   cannot establish compliance either way.
3. **No performance baseline exists.** TS-I01 and TS-I02 are reasoned from code. The system has
   never been measured under load, so scaling behaviour is entirely unknown.
4. **Rulepack validation status was verified in the second round (§7 TS-P02).** All 32 rulepack
   YAML files in `rulepacks/in-works/` carry `confidence: unvalidated`, and `risk/service.py`
   sets `validated_only=True` for paying workspaces, so paid workspaces currently receive an empty
   risk register. This is a confirmed product blocker.
5. **Three modules reviewed more deeply in the second round.** `auth` (`switch_workspace`,
   `resend_verification`, `mfa_enroll`, invitation token storage), `ingestion` rulepack loader, and
   `docker` packaging were re-examined. The remaining unreviewed modules (`analytics`,
   `comparison`, `crossref`, `qualification`, `standards`, `timeline`, `boq/engine`, `export/render`,
   `ingestion/{ocr,tables,segment,classify,extract}` and frontend pages beyond `login`) should not
   be assumed clean.
6. **Prior exploitation cannot be ruled out.** TS-A01 leaves no distinctive trace beyond a
   `workspace_members` row, and there is no authentication or membership audit log (§3.5 item 6).
   If this code has been deployed with real users, assume the membership table needs review.

### 6.4 Statement of limits

This audit does not certify the application as bug-free or secure. The first pass (§1–§6)
reports what was found within the scope described in §2.3, under the conditions in §1.6, using the
commands in §2.4; the second pass (§7) reports additional findings from a focused re-audit of
`auth`, `rulepacks`, and deployment packaging. Six exploitable defects were reproduced end-to-end
(TS-A01, TS-A02, TS-A04, TS-A05, TS-A06, TS-A07); the remainder are identified by code inspection
and are labelled accordingly. Areas marked **Not Tested** are genuinely unknown, not implicitly
passing.

The recommendation remains **NO-GO** for the audited commit. The blockers are specific,
well-understood, and concentrated in a handful of files — this is a fixable release, not a
failed architecture.

## 7. Second-round re-audit (TS-097)

### 7.1 Scope and evidence

This second pass re-verified the `TS-*` findings in §4 against commit `d651d00` and searched for
new regressions, especially in `auth`, `rulepacks`, and deployment packaging. No source code was
modified. Evidence came from:

- Re-reading `auth/service.py`, `auth/router.py`, `auth/models.py`, `core/storage.py`,
  `ingestion/tus.py`, `core/celery.py`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, and
  `rulepacks/in-works/`.
- `ruff`, `mypy app`, `pytest -q`, `npm run lint`, `npm run typecheck`, `npm run build`,
  `npm audit`, and `pip-audit`.
- Two targeted `TestClient` reproductions for `switch_workspace` and `resend-verification`.
- `grep -R "confidence:" rulepacks/in-works/` and `risk/service.py` analysis.

### 7.2 Re-verification status of previous release blockers

All `TS-*` findings from the first round remain present in `d651d00`; no fixes were observed. The
second round therefore concentrated on new defects and on product gaps that had been explicitly
out of scope earlier.

| ID | Severity | Status in `d651d00` |
|---|---|---|
| TS-A01 | Critical | Still present |
| TS-A02 | Critical | Still present |
| TS-A03 | Critical | Still present |
| TS-B01 | Critical | Still present |
| TS-A04 | High | Still present |
| TS-A05 | High | Still present |
| TS-I01 | High | Still present |
| TS-I02 | High | Still present |
| TS-B02 | High | Still present |
| TS-F01 | High | Still present |
| TS-O01 | High | Still present |
| Other Medium/Low TS-* | Medium/Low | Still present |

### 7.3 New findings

#### TS-A06 — `switch_workspace` does not persist the rotated refresh token

| | |
|---|---|
| **Status** | Confirmed defect — reproduced end-to-end |
| **Severity** | **High** |
| **Category** | Auth / session management |
| **Release-blocking** | Yes |
| **Affected code** | `backend/app/modules/auth/service.py` `switch_workspace` |

The method issues a new refresh-token family and marks the old family row `used_at`, but it never
calls `self.s.commit()`. The new token is therefore never written to the database, while the
browser receives an httpOnly cookie for it. The access token is valid for 15 minutes, but the next
`/auth/refresh` fails with `invalid_refresh`, logging the user out.

**Reproduction:**

```python
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app

app = create_app(Settings(enabled_modules="health,auth,ingestion", database_url="sqlite:///:memory:"))
engine = app.state.ctx.registry.require("db.engine")
Base.metadata.create_all(engine)
client = TestClient(app)

client.post("/api/auth/signup", json={
    "email": "a@example.com",
    "password": "Hunter2!Hunter2",
    "workspace_name": "Acme",
})
login = client.post("/api/auth/login", json={
    "email": "a@example.com",
    "password": "Hunter2!Hunter2",
})
tok = login.json()["access_token"]
ws2 = client.post(
    "/api/auth/workspaces",
    json={"name": "Second"},
    headers={"authorization": f"Bearer {tok}"},
).json()["workspace_id"]

client.post(
    f"/api/auth/workspaces/{ws2}/switch",
    headers={"authorization": f"Bearer {tok}"},
)
refresh = client.post("/api/auth/refresh")
assert refresh.status_code == 401  # {'detail': 'invalid_refresh'}
```

**Recommended solution:** Add `self.s.commit()` immediately after `_issue_tokens(...)` in
`switch_workspace` (mirroring `refresh()`).

---

#### TS-A07 — `POST /api/auth/resend-verification` returns raw verification token

| | |
|---|---|
| **Status** | Confirmed defect — reproduced end-to-end |
| **Severity** | **High** |
| **Category** | Auth / information disclosure |
| **Release-blocking** | Yes |
| **Affected code** | `backend/app/modules/auth/router.py` `resend_verification`; `backend/app/modules/auth/service.py` `create_email_verification` |

`create_email_verification` always returns the raw token, and the `resend-verification` endpoint
returns that value directly in the HTTP response body even when an email sender is configured. If
the response is logged by a proxy or browser extension, an attacker can verify the email address
without mailbox access. This is inconsistent with `signup`, which only returns the token in
non-prod environments when no sender is configured.

**Reproduction:**

```python
client.post("/api/auth/signup", json={
    "email": "a@example.com",
    "password": "Hunter2!Hunter2",
    "workspace_name": "Acme",
})
login = client.post("/api/auth/login", json={
    "email": "a@example.com",
    "password": "Hunter2!Hunter2",
})
tok = login.json()["access_token"]
resend = client.post(
    "/api/auth/resend-verification",
    headers={"authorization": f"Bearer {tok}"},
)
print(resend.json())  # -> raw verification token string
```

**Recommended solution:** `resend_verification` should return only `{"ok": True}` and the token
must be transmitted through the configured email channel. If `create_email_verification` must
return a value for dev/test, the router should strip it in prod.

---

#### TS-O04 — Backend Dockerfile omits required optional extras

| | |
|---|---|
| **Status** | Confirmed defect — by code inspection |
| **Severity** | **High** |
| **Category** | Deployment / packaging |
| **Release-blocking** | Yes |
| **Affected code** | `backend/Dockerfile`; `backend/pyproject.toml` |

The image runs `pip install -e ".[dev,storage,redis]" || pip install -e ".[storage,redis]"`. This
omits `celery`, `billing`, `scheduler`, and `ocr` extras. `app/core/celery.py` imports `celery` at
module scope and `app/main.py` always calls `make_celery_app()`, so the container will fail to boot
unless `celery` is installed. Even after fixing that, payments, deadline-alert scheduling, and
OCR cannot be enabled in the container because their dependencies are missing.

**Evidence:**

```dockerfile
# backend/Dockerfile
RUN pip install -e ".[dev,storage,redis]" || pip install -e ".[storage,redis]"
```

```python
# backend/app/core/celery.py
from celery import Celery
```

**Recommended solution:** Change the Dockerfile to install a production extras set such as
`".[storage,redis,celery,billing,scheduler,ocr]"` and add a smoke test in CI that builds the
image and runs `python -c "from app.main import create_app"`.

---

#### TS-A08 — Invitation tokens stored in plaintext

| | |
|---|---|
| **Status** | Confirmed defect — by code inspection |
| **Severity** | **Medium** |
| **Category** | Auth / data protection |
| **Release-blocking** | No |
| **Affected code** | `backend/app/modules/auth/models.py` `Invitation.token` |

`EmailVerification` and `PasswordReset` store SHA256 hashes of their tokens, but `Invitation`
stores the token as a plaintext `String`. A database dump would disclose every active invitation
token. The token is already emailed once, so the raw value does not need to be retained.

**Recommended solution:** Store `token_hash` on `Invitation`, migrate existing rows, and verify
the hash in the invitation-accept endpoint.

---

#### TS-A09 — TOTP enrollment does not require a verification code

| | |
|---|---|
| **Status** | Confirmed defect — by code inspection |
| **Severity** | **Medium** |
| **Category** | Auth / MFA |
| **Release-blocking** | No |
| **Affected code** | `backend/app/modules/auth/service.py` `mfa_enroll` |

When `method == "totp"`, the service generates a secret, writes it to `user.mfa_totp_secret`, sets
`mfa_method="totp"`, commits, and returns the secret/URI without requiring the user to prove they
can produce a valid TOTP code. A session that is briefly compromised can enable TOTP and lock the
account without the legitimate owner noticing.

**Recommended solution:** Keep `mfa_method` unchanged until the user posts a valid TOTP code
generated from the new secret; only then persist `mfa_totp_secret` and `mfa_method="totp"`.

---

#### TS-P02 — Rulepack patterns are still unvalidated; paying workspaces receive zero risk findings

| | |
|---|---|
| **Status** | Confirmed product blocker — by code and data inspection |
| **Severity** | **Critical** |
| **Category** | Product correctness / business logic |
| **Release-blocking** | Yes |
| **Affected code** | `backend/app/modules/risk/service.py`; `backend/app/modules/rulepacks/loader.py`; `rulepacks/in-works/` |

Every risk pattern and trade checklist in `rulepacks/in-works/` carries `confidence: unvalidated`.
`risk/service.py` sets `validated_only=True` for paying workspaces and
`RulePackLoader.list_patterns` filters to patterns with `confidence == "validated"`. The result is
that paid workspaces currently receive an empty risk register. Free workspaces see unvalidated
patterns.

**Evidence:**

```text
$ grep -R "^confidence:" rulepacks/in-works/
confidence: unvalidated
... (every file)
```

```python
def _is_paying(self, workspace_id) -> bool:
    ...
    return ws is not None and ws.plan.lower() in PAID_PLANS

def run_opportunity(self, workspace_id, opportunity_id) -> list[Finding]:
    validated_only = self._is_paying(workspace_id)
    patterns = self._loader.list_patterns(self._pack_id, validated_only=validated_only)
    ...
```

**Recommended solution:** Complete the Phase-1 QS validation checkpoint and flip at least the
critical patterns to `confidence: validated`, or add an explicit beta/disclaimer flag that lets
paying users see unvalidated patterns with clear "unvalidated" labeling.

### 7.4 Updated remediation plan

The second-round findings do not change the priority of the original release blockers (TS-A01,
TS-A02, TS-A03, TS-B01 remain P0), but add new P0 items:

1. **P0 (release-blocking, new)**
   - TS-A06: add `self.s.commit()` in `switch_workspace`.
   - TS-A07: stop returning raw tokens from `resend-verification`, `forgot-password`, and
     `create-invitation` responses; send through email only.
   - TS-O04: fix `backend/Dockerfile` extras and validate container boot in CI.
2. **P0 (original)**
   - TS-A01, TS-A02, TS-A03, TS-B01 as in §5.1.
   - TS-P02: complete rulepack QS validation or add a beta flag.
3. **P1**
   - TS-A04, TS-A05, TS-I01, TS-I02, TS-B02, TS-F01, TS-O01.
   - TS-A08: hash `Invitation.token`.
   - TS-A09: require TOTP verification before committing enrollment.
4. **P2**
   - Remaining Medium/Low TS-* and product completeness gaps in §3.5.

### 7.5 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The second round confirmed all original `TS-*` release blockers are still present and added three
new release-blocking code defects (TS-A06, TS-A07, TS-O04) plus a product blocker (TS-P02). All
thirteen release-blocking findings must be fixed before a public or multi-tenant launch.
