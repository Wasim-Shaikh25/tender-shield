# TenderShield — End-to-End Production Readiness Audit

**Repository:** `Wasim-Shaikh25/tender-shield`
**Commit audited:** `0866bb7` — `Merge pull request #17 from Wasim-Shaikh25/devin/update-skills-1785346060`
**Branch audited:** `claude/dev-workflow-modules-58dpqw` (the repository's trunk — see §2.0)
**Audit date:** 2026-07-29
**Roles applied:** Principal Software Engineer, Security Engineer, QA Engineer, DevOps/SRE, Database Architect, Product Manager, UX Designer, Accessibility Specialist, Performance Engineer.
**Source changes made:** none. This report, `tasks/backlog.md`, and `CHANGELOG.md` are the only files added or modified.

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

A third-round pass (§8) re-ran the audit from scratch on a fresh branch, re-confirmed every
previous finding, and discovered an additional cross-tenant write path: `POST /api/auth/invitations`
accepts an arbitrary `project_id` and `POST /api/auth/invitations/{token}/accept` adds a
`ProjectMember` row without verifying the project belongs to the invitation's workspace (`TS-A10`).

A fourth-round pass (§9) concentrated on modules and pages explicitly marked "not reviewed in
depth" in prior rounds (analytics, comparison, crossref, qualification, standards, timeline,
baseline, assistant, notifications, risk engine, BOQ engine, export rendering, ingestion tus,
and frontend pages beyond login). It identified twelve additional gaps, the most significant
being synchronous CPU-bound extraction inside async upload routes (`TS-I04`), unbounded CSV
payloads in the BOQ run endpoint (`TS-I05`), a frontend session provider that keeps stale
workspace state after switching (`TS-F02`), and a brittle LLM-response parser in the risk
classifier (`TS-R01`).

A fifth-round pass (§10) re-scanned the same branch for previously overlooked gaps in
notifications, review/drafting, timeline export, risk/assistant LLM adapters, and ingestion
async/direct routes. It identified eight additional gaps, the most significant being an invalid
default Anthropic model name in both the risk classifier and the assistant agent (`TS-R02`,
`TS-A14`), a notifications scheduler tick that calls a method missing from the
`auth.workspace_factory` capability (`TS-N02`), and an async document-processing task that
does not classify documents, segment clauses, update the opportunity submission deadline, or
use the configured OCR provider (`TS-I08`).

A sixth-round pass (§11) re-scanned infrastructure, billing, storage, CORS/allowed-hosts
guards, ingestion/tus I/O, and review opportunity-scoping. It identified six additional gaps:
`LocalStorage` async methods run synchronous filesystem I/O (`TS-S04`), the production startup
guard for CORS and allowed hosts can be bypassed with a comma-separated wildcard (`TS-O05`),
Stripe checkout redirects are hardcoded to `example.com` (`TS-B07`), the Stripe webhook verifier
swallows all exceptions (`TS-B08`), tus routes block the event loop with synchronous file I/O and
return an empty, non-compliant `OPTIONS` response (`TS-I09`), and `POST /api/review/findings/{finding_id}`
does not scope by opportunity (`TS-A16`).

A seventh-round pass (§12) re-scanned the codebase for violations of the product invariants
declared in `CLAUDE.md` §4 and the build doc, concentrating on money representation, source-page
provenance for non-PDF documents, deterministic risk severity, and multi-workspace auth. All
previously documented `TS-*` findings were re-verified and still present. It identified four
additional gaps: the shared `Finding` contract and several downstream modules store/extract
monetary amounts as `float` / `Numeric(16,2)` major units instead of minor units (`TS-C01`),
XLSX/CSV text extraction does not emit page markers so spreadsheet-derived facts lose page
provenance (`TS-I10`), email/password login selects an arbitrary workspace for multi-workspace
users (`TS-A17`), and the severity evaluator silently defaults missing facts to `0` (`TS-R03`).

### 1.2 Finding count by severity

| Severity | Count | Release-blocking | IDs |
|---|---|---|---|
| **Critical** | 5 | 5 | TS-A01, TS-A02, TS-A03, TS-B01, TS-P02 |
| **High** | 15 | 13 | TS-A04, TS-A05, TS-I01, TS-I02, TS-B02, TS-F01, TS-O01, TS-A06, TS-A07, TS-O04, TS-A10, TS-I04, TS-I05, TS-F02, TS-R02 |
| **Medium** | 37 | 0 | TS-O02, TS-I03, TS-N01, TS-P01, TS-S01, TS-X01, TS-B03, TS-S02, TS-O03, TS-A08, TS-A09, TS-R01, TS-D02, TS-Q01, TS-X02, TS-A11, TS-I06, TS-B05, TS-S03, TS-A13, TS-N02, TS-I07, TS-I08, TS-A14, TS-A15, TS-B06, TS-D03, TS-S04, TS-O05, TS-B07, TS-B08, TS-I09, TS-A16, TS-C01, TS-I10, TS-A17, TS-R03 |
| **Low** | 4 | 0 | TS-L01, TS-L02, TS-L03, TS-L04 |
| **Total** | **61** | **18** | |

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
| Arbitrary project_id in invitation adds member to any project | `auth/service.py` `create_invitation`/`accept_invitation` do not verify project ownership (§8 TS-A10) | High |
| Synchronous extraction blocks the async event loop on upload | `ingestion/router.py:164` calls `extract_upload` directly from an `async def` route (§9 TS-I04) | High |
| BOQ run accepts unbounded CSV payloads | `boq/router.py:47` `RunBody.csv` has no max length; parsed entirely in memory (§9 TS-I05) | High |
| Session provider keeps stale workspace list after switch | `frontend/components/session.tsx:52` refuses to overwrite a non-empty workspace list (§9 TS-F02) | High |
| Risk classifier uses an invalid Anthropic model name | `risk/classifier.py:33` default is `claude-sonnet-5`; `risk/module.py:15` instantiates without override (§10 TS-R02) | High |
| Production CORS/allowed-hosts guard bypassed by comma-separated wildcard | `main.py:66-69` checks the exact string `"*"` while `config.py` splits on commas (§11 TS-O05) | Medium |
| LocalStorage async methods block the event loop with synchronous I/O | `core/storage.py:104-119` `read`/`write`/`delete` call sync `pathlib` without `asyncio.to_thread` (§11 TS-S04) | Medium |
| Review finding endpoint does not scope by opportunity | `review/router.py:50-70` and `findings/store.py:49-83` query by `workspace_id` and `finding_id` only (§11 TS-A16) | Medium |
| Monetary amounts are represented as `float` / `Numeric(16,2)` major units | `core/contracts/findings.py:64`, `findings/models.py:60`, `drafting/validators.py:25`, `boq/engine.py:96-99`, `standards/service.py:25-29` (§12 TS-C01) | Medium |
| Spreadsheet ingestion loses page provenance because `[sheet:...]` markers are not recognised | `ingestion/extract.py:56-77`, `ingestion/doc_text.py:27-45`, `ingestion/segment.py:41-68`, `ingestion/deadlines.py:83-105` (§12 TS-I10) | Medium |
| Email/password login picks the first workspace for a user with no ordering | `auth/service.py:160-162` (§12 TS-A17) | Medium |
| Severity rules silently treat missing facts as `0` | `risk/severity.py:41-45` (§12 TS-R03) | Medium |


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
  no-uncited-clauses, no-invented-numbers. Money is intended to be in minor units, but the
  shared `Finding` contract and several downstream modules still use major-unit `float` /
  `Numeric(16,2)` representations (§12 TS-C01).
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

Ship only when **all eighteen** release-blocking findings in §5.1, §5.2, §7.3, §9.4, §10.3, §11.3, and §12.3 are fixed,
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

---

## 8. Third-round re-audit (TS-128)

### 8.1 Scope and evidence

This re-audit was requested as a "rerun from scratch" using the same prompt. It ran from a fresh
branch (`claude/production-readiness-audit-rerun-1785347883`) cut from the current trunk
(`claude/dev-workflow-modules-58dpqw`, commit `0866bb7`).

Baseline checks re-executed:

| # | Command | Result |
|---|---|---|
| 1 | `ruff check .` | **PASS** — All checks passed |
| 2 | `mypy app` | **PASS** — 143 files, no issues |
| 3 | `pytest -q` | **PASS** — 145 passed, 1 skipped, 1 warning |
| 4 | `npm run lint` | **PASS** — no ESLint errors |
| 5 | `npm run typecheck` | **PASS** — `tsc --noEmit` |
| 6 | `npm run build` | **PASS** — 12 routes compiled |
| 7 | `npm audit` | **PASS** — 0 vulnerabilities |
| 8 | `pip-audit` | **PASS** — No known vulnerabilities |
| 9 | Custom security probes (`/home/ubuntu/audit_rerun_probes.py`) | **6 of 6 reproduced expected issues, plus 1 new exploit** |

The probe script is an audit artifact and was **not committed** to the repository.

### 8.2 Re-verification status of previous findings

All previously reported `TS-*` findings were re-confirmed by code inspection and, where possible,
by the probes:

- **TS-A01, TS-A04** — Reproduced end-to-end in the probe script.
- **TS-A06, TS-A07, TS-A09** — Reproduced end-to-end in the probe script.
- **TS-A02, TS-A03, TS-A05, TS-B01, TS-B02, TS-I01, TS-I02, TS-F01, TS-O01, TS-O04, TS-P02,**
  **TS-S01, TS-X01, and product gaps** — Confirmed by re-reading the same files and configuration.

No previously reported finding was retired in this round.

### 8.3 New finding

#### TS-A10 — `create_invitation` accepts arbitrary `project_id`; `accept_invitation` does not verify project ownership

| | |
|---|---|
| **Status** | Confirmed Defect — **reproduced end-to-end** |
| **Severity** | **High** |
| **Category** | Broken Access Control / Tenant Isolation |
| **Release-blocking** | **YES** |
| **Affected roles** | Any workspace `admin`/`owner` |

**Location**

- `backend/app/modules/auth/router.py:472-485` — `create_invitation`
- `backend/app/modules/auth/service.py:514-550` — `create_invitation`
- `backend/app/modules/auth/service.py:552-599` — `accept_invitation`

**Evidence**

`POST /api/auth/invitations` takes an optional `project_id` in the body and trusts it verbatim:

```python
def create_invitation(
    self, workspace_id, email: str, role: str, project_id: str | None = None
) -> dict:
    ...
    project_uuid = uuid.UUID(str(project_id)) if project_id else None
    ...
    invitation = Invitation(
        workspace_id=workspace_id,
        project_id=project_uuid,          # ← no check that this project belongs to workspace_id
        ...
    )
```

`accept_invitation` then adds a `ProjectMember` row using the invitation's `workspace_id` and
`project_id`, again without verifying the project belongs to that workspace:

```python
if invitation.project_id:
    existing_project = self.s.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == invitation.project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not existing_project:
        self.s.add(
            ProjectMember(
                workspace_id=invitation.workspace_id,
                project_id=invitation.project_id,
                ...
            )
        )
```

**Reproduction** (new probe, verified):

```text
1. Victim B signs up → workspace B, creates project secret-proj
2. Attacker A signs up → workspace A (owner)
3. POST /api/auth/invitations
   Authorization: Bearer <A token>
   {"email": "attacker@example.com", "role": "viewer", "project_id": "<secret-proj UUID>"}

   → HTTP 200 {"token": "..."}

4. POST /api/auth/invitations/{token}/accept
   Authorization: Bearer <A token>

   → HTTP 200 {"workspace_id": "A", "role": "viewer"}

5. GET /api/auth/projects/{secret-proj}/members
   Authorization: Bearer <A token>

   → HTTP 200 with victim B's project member list
```

The attacker is now a member of another tenant's project and can enumerate its membership.

**Root cause**

The same "role check without resource binding" pattern as TS-A01/A04: the service validates the
caller's role in their own workspace but never checks that the `project_id` belongs to that
workspace. `Project.workspace_id` exists and is already checked in `add_project_member`, so the
correct pattern is available.

**Impact**

*Technical:* Cross-tenant project membership injection. An attacker who knows or guesses any
project UUID can join that project and read its member list (which already has no workspace check
— see TS-A04).

*Business:* Compromises the confidentiality of project-team composition, which may reveal
competitors, subcontractors, or bid-partner relationships. Corrupts the `project_members` table
with rows whose `workspace_id` does not match the project they reference, creating a data-integrity
and incident-response problem.

**Recommended solution**

In `create_invitation`, verify `project_id` belongs to the caller's workspace before creating the
invitation. In `accept_invitation`, either re-verify or rely on a FK constraint that ties
`project_id` to the same `workspace_id`. Minimal patch:

```python
def create_invitation(self, workspace_id, email, role, project_id=None):
    ...
    if project_id:
        project = self.s.scalar(
            select(Project).where(
                Project.id == uuid.UUID(str(project_id)),
                Project.workspace_id == workspace_id,
            )
        )
        if not project:
            raise AuthError("no_such_project")
    ...
```

Add a regression test that attempts to invite to a foreign-project UUID and asserts 403/404.

**Regression risks** Low — the invitation flow is self-contained.

**Tests to add** `test_create_invitation_rejects_foreign_project`, `test_accept_invitation_preserves_workspace_project_binding`.

---

### 8.4 Updated remediation plan

Add to the P0/P1 list from §5 and §7.4:

- **P0 (release-blocking, new)**
  - **TS-A10**: validate `project_id` in `create_invitation` and `accept_invitation` against the
    caller's workspace.
- **P1**
  - Add `TS-A10` regression tests and extend the centralized resource-authorization check to
    project-scoped invitation flows.

### 8.5 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The third round re-confirmed every prior release blocker and discovered one additional
release-blocking cross-tenant write path (TS-A10). There are now **31 findings** (5 Critical,
11 High, 11 Medium, 4 Low) with **14 release-blocking** items. The defects remain concentrated
in the auth module and are fixable, but the product should not ship until all fourteen blockers
are resolved and verified.
## 9. Fourth-round re-audit

### 9.1 Scope and evidence

This re-audit was requested to analyse the repository end-to-end, skip findings already
documented in prior sections, and add any newly discovered gaps. It concentrated on the areas
explicitly listed in §2.3 as "not reviewed in depth" and on additional frontend pages and
infrastructure. Baseline checks were re-run on the current commit (`4bca123`) and remain green:
`ruff check .`, `mypy app`, `pytest -q` (146 passed), `npm run lint`, `npm run typecheck`, and
`npm run build` all pass. Source code is unchanged from the commit audited in the previous
report (git diff is limited to documentation/changelog/backlog), so all previously reported
`TS-*` findings remain present.

### 9.2 Re-verification status of previous findings

All previously reported `TS-*` findings were re-confirmed by code inspection. No previously
reported finding was retired in this round.

### 9.3 New findings

#### TS-I04 — Synchronous extraction blocks the async event loop in `upload_document`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Concurrency / Performance |
| **Release-blocking** | **YES** |
| **Affected roles** | Any authenticated user with `estimator` role |

**Location** — `backend/app/modules/ingestion/router.py:112-181`

**Evidence** The `upload_document` route is declared `async def`, but after storing the file it
calls the synchronous, CPU-bound `extract_upload` directly:

```python
# backend/app/modules/ingestion/router.py:164
ocr = request.app.state.ctx.registry.get("ingestion.ocr")
text, ocr_status = extract_upload(file.filename, data, ocr)
```

`extract_upload` performs PDF parsing, table extraction, and optional OCR. Running it on the
main event loop blocks all other requests for the duration of the parse.

**Root cause** Missing `await asyncio.to_thread(...)` (or a Celery enqueue) around a synchronous,
CPU-intensive operation inside an async route.

**Impact** A single large uploaded tender pack can freeze the entire server for all users.
Combined with TS-I01 (fully-buffered upload), this is a practical DoS vector.

**Recommended solution** Move `extract_upload` to a thread pool:

```python
text, ocr_status = await asyncio.to_thread(extract_upload, file.filename, data, ocr)
```

For production, consider making the non-async path queue to Celery (as the `?async=1` path does)
by default, and stream progress via the existing SSE endpoint.

**Regression risks** Low — the function is already side-effect-free given stored bytes.

**Tests to add** `test_upload_document_yields_event_loop` (assert no other request is blocked
while a large PDF is parsed); `test_async_query_runs_in_thread`.

**Similar locations** `baseline/router.py:92` `upload_award_document` stores but does not extract
text; the extraction is deferred to `BaselineService.store_award_document`, which is called from a
sync route so the concern is smaller. `boq/router.py:95-100` `upload_boq` calls `to_csv` on
parsed data inside an `async def` route and has the same pattern (see TS-X02).

---

#### TS-I05 — BOQ run endpoint accepts unbounded CSV payloads

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Denial of Service / Input Validation |
| **Release-blocking** | **YES** |
| **Affected roles** | Any authenticated user with `estimator` role |

**Location** — `backend/app/modules/boq/router.py:40-54`; `backend/app/modules/boq/service.py:79-89`

**Evidence** The request body has no maximum length and is parsed directly into a pandas
DataFrame:

```python
# backend/app/modules/boq/service.py:80
def run_csv(self, workspace_id, opportunity_id, csv_text: str) -> list[Finding]:
    df = pd.read_csv(io.StringIO(csv_text))
```

```python
# backend/app/modules/boq/router.py:47-51
def run_boq(...):
    findings = _runner(...).run_csv(principal.workspace_id, opportunity_id, body.csv)
```

`RunBody` only declares `csv: str`; Pydantic will accept an arbitrarily long string.

**Root cause** No payload size cap on `RunBody.csv` and no streaming/ chunked CSV parser.

**Impact** A multi-megabyte or multi-gigabyte `csv` string will be loaded into memory as a single
object, causing OOM or extremely long CPU consumption on every request. The `estimator` role is
required, but a compromised account or a single malicious user can crash the worker.

**Recommended solution** Add a `max_length` validator to `RunBody.csv` (e.g. 5 MB, matching the
largest permitted CSV upload) and reject before `pd.read_csv`:

```python
class RunBody(BaseModel):
    csv: str = Field(..., max_length=5 * 1024 * 1024)
```

**Regression risks** Low — legitimate BOQ CSVs are well below this size.

**Tests to add** `test_run_boq_rejects_oversized_csv`; `test_run_boq_accepts_max_size_csv`.

**Similar locations** `ingestion/router.py:127` `file.read()` is bounded by `MAX_UPLOAD_SIZES`,
so the raw upload path is safer; the BOQ text path bypasses those checks.

---

#### TS-F02 — Session provider keeps a stale workspace list after switch/refresh

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | Frontend State / Session |
| **Release-blocking** | **YES** |
| **Affected roles** | Any user with more than one workspace |

**Location** — `frontend/components/session.tsx:42-53`

**Evidence** `applyTokens` only replaces the workspace list when the current list is empty:

```tsx
const applyTokens = (t: Tokens, all?: Workspace[]) => {
  ...
  const match = (all ?? workspaces).find((w) => w.id === t.workspace_id);
  if (match) {
    setWorkspaces((prev) => (prev.length ? prev : all ?? prev));
  }
};
```

After the first successful load `prev` is non-empty, so subsequent `switchWorkspace` or
`refreshSession` calls pass a fresh `all` list but the state is not updated. The active
workspace is then computed from the stale list:

```tsx
const activeWorkspace = workspaces.find((w) => w.id === session?.workspaceId) ?? null;
```

Because `session.workspaceId` is new but `workspaces` is old, `activeWorkspace` becomes `null`
after every switch or refresh.

**Root cause** A guard intended to avoid overwriting a loaded list also prevents updating it when
the user's context changes.

**Impact** The workspace switcher and any UI that depends on `activeWorkspace` break after the
first switch/refresh. This undermines the multi-workspace support the session provider is meant
to provide.

**Recommended solution** Replace the conditional update with unconditional state replacement:

```tsx
if (match) {
  setWorkspaces(all ?? workspaces);
}
```

**Regression risks** Low — the intent is to keep the workspace list in sync with the token.

**Tests to add** A React component test rendering `SessionProvider` through a mock
`switchWorkspace` response and asserting `activeWorkspace` matches the new workspace.

**Similar locations** `refreshSession` and `signIn` both call `applyTokens` with a freshly loaded
list and are also affected.

---

#### TS-R01 — Risk classifier uses brittle string slicing and no schema validation

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | LLM Reliability / Data Integrity |
| **Release-blocking** | No |
| **Affected roles** | All users running risk review with an LLM key |

**Location** — `backend/app/modules/risk/classifier.py:50-59`

**Evidence**

```python
raw = msg.content[0].text
return json.loads(raw[raw.index("[") : raw.rindex("]") + 1])
```

The parser finds the first `[` and the last `]` in the response. If the model emits any other
square brackets — in an explanation, a clause reference, or a formatting artifact — the slice will
be wrong and `json.loads` will fail or return malformed data. There is no Pydantic validation of
the required fields (`found`, `facts`, `source_quote`, `source_page`).

**Root cause** Ad-hoc JSON extraction instead of a constrained tool/schema call or strict
response parsing.

**Impact** Risk review can crash silently (returns `[]`) or return fabricated `facts` that feed
into deterministic severity scoring, producing incorrect findings without the user noticing.

**Recommended solution** Switch to Anthropic's `tool_use` / JSON mode with a defined schema, or
wrap `json.loads` in a Pydantic validator and reject any response that does not match:

```python
from pydantic import BaseModel, Field, ValidationError

class ClauseMatch(BaseModel):
    found: bool
    finding: str
    facts: dict = Field(default_factory=dict)
    source_quote: str = ""
    source_page: int | None = None
```

**Regression risks** Low — the contract with the rest of the engine is a list of dicts with the
same keys.

**Tests to add** `test_classifier_rejects_bracket_noise`; `test_classifier_validates_missing_fields`.

**Similar locations** `assistant/agent.py:46` returns raw text and does not validate that the
answer is grounded-only or that it cites only provided facts (see TS-A13).

---

#### TS-D02 — `days_to_submission` mixes UTC and local time for naive deadlines

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Date Arithmetic / Data Quality |
| **Release-blocking** | No |
| **Affected roles** | All users viewing the opportunity board / analytics |

**Location** — `backend/app/modules/comparison/service.py:64-70`

**Evidence**

```python
if submission_due:
    ref = datetime.now(UTC) if submission_due.tzinfo else datetime.now()
    delta = submission_due - ref
    days_to_submission = max(0, delta.days)
```

When `submission_due` is naive (the common case on SQLite and for extracted deadlines without an
explicit timezone), the reference is `datetime.now()` in the server's local timezone, while the
deadline is interpreted as UTC by the storage layer. This produces an off-by-hours error in the
countdown and can flip the red/amber deadline badges incorrectly.

**Root cause** Inconsistent timezone handling: naive datetimes are assumed UTC in the model but
compared against local wall-clock time.

**Impact** The board and analytics show wrong urgency, misleading bid teams about how much time
remains.

**Recommended solution** Store and compare all deadline datetimes in UTC. When a naive value is
encountered, assume UTC rather than local time:

```python
ref = datetime.now(UTC)
if submission_due.tzinfo is None:
    submission_due = submission_due.replace(tzinfo=UTC)
delta = submission_due - ref
```

**Regression risks** Low — the change only affects comparison semantics.

**Tests to add** `test_days_to_submission_for_naive_utc_deadline` with mocked wall-clock time.

**Similar locations** `notifications/module.py:57-58` also normalises naive `due_at` to UTC but
only after comparison with `datetime.now(UTC)`, so it has the same local-time bug.

---

#### TS-Q01 — Qualification matrix marks missing criteria as `not_met` with HIGH severity

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Product Correctness / False Positives |
| **Release-blocking** | No |
| **Affected roles** | All users running qualification review |

**Location** — `backend/app/modules/qualification/service.py:144-199`

**Evidence** When no keyword for a criterion is found in the tender clauses, the code creates a
`QualificationCriterion` with `status="not_met"`:

```python
if found is None:
    records.append(
        QualificationCriterion(
            key=cfg["key"],
            label=cfg["label"],
            status="not_met",
            ...
        )
    )
```

`_to_finding` then assigns `Severity.HIGH` to any `not_met` row:

```python
severity = Severity.HIGH if c.status == "not_met" else Severity.MEDIUM
```

A missing mention of "equipment requirements" does not mean the bidder does not meet it; it
means the tender is silent on that criterion.

**Root cause** Confusing "criterion not mentioned in tender" with "criterion not met by bidder".

**Impact** Every qualification run generates HIGH-severity false positives, reducing trust in the
register and hiding real problems in a wall of noise.

**Recommended solution** Introduce a `not_mentioned` status and set severity to `LOW` or
`INFO`:

```python
if found is None:
    status = "not_mentioned"
    severity = Severity.LOW
else:
    status = "unknown"   # present but not verified
    severity = Severity.MEDIUM
```

**Regression risks** Low — the `status` values are not exposed outside this module.

**Tests to add** `test_qualification_missing_criterion_is_not_high_severity`.

---

#### TS-X02 — BOQ engine relies on DuckDB reading `df` from caller scope

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Architecture / Deterministic Engine |
| **Release-blocking** | No |
| **Affected roles** | All users running BOQ checks |

**Location** — `backend/app/modules/boq/engine.py:79-80,126-127`

**Evidence** `run_checks` interpolates numeric parameters into a SQL string and then asks DuckDB
to read `df` from the Python scope:

```python
sql = CHECKS_SQL.format(tol=tolerance, q=outlier_quantile, mult=outlier_multiplier)
rows = duckdb.query(sql).to_df().to_dict("records")  # duckdb reads `df` from scope
```

```python
totals = duckdb.query("SELECT sum(amount) a, sum(amount_calc) c FROM df").fetchone()
```

DuckDB's `query` resolves `df` from the current Python frame. If `run_checks` is refactored,
renamed, or called from a context where the variable is not named `df`, the query fails. The
`str.format` on `CHECKS_SQL` is also fragile and harder to audit than parameterized queries.

**Root cause** Tight coupling between SQL text and the local variable name; use of string
formatting for numeric placeholders.

**Impact** The deterministic engine can fail in unexpected execution contexts (async threads,
Celery workers, refactored callers) and is harder to maintain or reason about.

**Recommended solution** Pass `df` explicitly to DuckDB via `duckdb.from_df` or a relation
alias, and avoid `str.format` for SQL even with trusted numeric values:

```python
conn = duckdb.connect()
conn.register("df", df)
rows = conn.execute(CHECKS_SQL, [tolerance, outlier_quantile, outlier_multiplier]).fetchall()
```

**Regression risks** Low — the query shape and returned columns can stay identical.

**Tests to add** `test_run_checks_with_renamed_dataframe`; `test_check_sql_uses_bound_parameters`.

**Similar locations** `boq/router.py:95` `to_csv` for scanned PDFs is also CPU-heavy but does not
use DuckDB scope injection.

---

#### TS-A11 — Cross-reference search loads all clauses regardless of `limit`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Performance / Denial of Service |
| **Release-blocking** | No |
| **Affected roles** | Any authenticated `viewer` |

**Location** — `backend/app/modules/crossref/router.py:17-33`; `backend/app/modules/crossref/service.py:23-61`

**Evidence** The router accepts `limit: int = 20` and `q: str = ""` with no validation:

```python
def search(..., q: str = "", limit: int = 20, ...):
    ...
    return {
        "query": q,
        "results": _service(...).search(principal.workspace_id, opportunity_id, q, limit=limit),
    }
```

The service loads every clause for the opportunity from the database and then slices in Python:

```python
docs = {str(d.id): d for d in svc.list_documents(workspace_id, opportunity_id)}
clauses = svc.list_clauses(workspace_id, opportunity_id)
...
scored.sort(key=lambda x: x["score"], reverse=True)
return scored[:limit]
```

`limit` only trims the returned list; the full clause set is always fetched.

**Root cause** No pagination or database-level `LIMIT`, and no upper bound on `limit` or length
of `q`.

**Impact** A workspace with many clauses (large tender packs) can be trivially OOM'd or CPU
exhausted by a single search request. A very long `q` string also increases processing time.

**Recommended solution** Cap `limit` with `Query(..., ge=1, le=100)`, validate `q` length, and
move scoring to the database or at least apply a `LIMIT` after tokenisation. Short-term fix:

```python
limit: int = Query(20, ge=1, le=100)
```

**Regression risks** Low — search results are currently unranked beyond Jaccard score.

**Tests to add** `test_crossref_search_respects_limit`; `test_crossref_search_rejects_huge_limit`.

---

#### TS-I06 — `confirm_deadline` does not verify the deadline belongs to the opportunity

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Authorization / Data Integrity |
| **Release-blocking** | No |
| **Affected roles** | Any authenticated `estimator` |

**Location** — `backend/app/modules/ingestion/router.py:271-282`; `backend/app/modules/ingestion/service.py:152-162`

**Evidence** The route is `/opportunities/{opportunity_id}/deadlines/{deadline_id}/confirm`, but
the service only filters by `deadline_id` and `workspace_id`:

```python
def confirm_deadline(self, workspace_id, deadline_id) -> Deadline | None:
    dl = self.s.scalar(
        select(Deadline).where(
            Deadline.id == uuid.UUID(str(deadline_id)),
            Deadline.workspace_id == uuid.UUID(str(workspace_id)),
        )
    )
```

The `opportunity_id` path parameter is never used.

**Root cause** Missing `opportunity_id` filter in the service query.

**Impact** A user can confirm a deadline belonging to a different opportunity in the same
workspace, mutating the wrong tender's timeline.

**Recommended solution** Add `Deadline.opportunity_id == uuid.UUID(str(opportunity_id))` to the
`where` clause and return 404 when the deadline does not belong to the requested opportunity.

**Regression risks** None — all legitimate calls already include a valid opportunity ID.

**Tests to add** `test_confirm_deadline_rejects_foreign_opportunity`.

---

#### TS-B05 — Baseline `freeze` has a race condition on `version` numbering

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Data Integrity / Concurrency |
| **Release-blocking** | No |
| **Affected roles** | Users with `reviewer` role |

**Location** — `backend/app/modules/baseline/service.py:331-358`; `backend/app/modules/baseline/models.py:17-33`

**Evidence** `freeze` reads the current maximum version, increments it, and then inserts:

```python
next_version = (
    self.s.scalar(
        select(func.coalesce(func.max(Baseline.version), 0)).where(
            Baseline.opportunity_id == opp
        )
    )
    + 1
)
```

There is no unique constraint on `(opportunity_id, version)` in `Baseline` model.

**Root cause** Non-atomic read-modify-write and missing unique constraint.

**Impact** Two concurrent `freeze` calls for the same opportunity can both receive the same
`next_version`, producing two baselines with the same version number and ambiguous ordering.

**Recommended solution** Add a unique constraint/index on `(opportunity_id, version)` and use an
advisory lock or atomic `INSERT ... ON CONFLICT DO NOTHING` retry:

```python
class Baseline(Base, WorkspaceScopedMixin):
    __table_args__ = (UniqueConstraint("opportunity_id", "version"),)
```

**Regression risks** Low — existing data may need migration if duplicates already exist.

**Tests to add** `test_freeze_version_is_unique_per_opportunity` under concurrent requests.

---

#### TS-S03 — Uploaded filename can inject `Content-Disposition` header in file download

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Header Injection / File Download |
| **Release-blocking** | No |
| **Affected roles** | Any authenticated user downloading uploaded files |

**Location** — `backend/app/main.py:159-181`

**Evidence** The `/api/files/{key:path}` endpoint constructs `Content-Disposition` directly from
the filename portion of the storage key:

```python
filename = _pathlib.Path(key).name
...
headers={"Content-Disposition": f"attachment; filename={filename}"},
```

`validate_and_store` stores the key as `workspace/{id}/{digest[:16]}-{safe_name}` where `safe_name`
is the original filename with path traversal stripped but special characters (including `"` and
`;`) left intact. An uploaded file named `report"; filename="evil` becomes part of the key and then
part of the response header.

**Root cause** No escaping/sanitising of filename before use in an HTTP header.

**Impact** Response-header splitting and possible content-sniffing attacks if a browser misparses
the header. Although the route returns `application/octet-stream`, `Content-Disposition` injection
is a security hardening gap.

**Recommended solution** Sanitise the filename to a safe basename and escape it for RFC 5987:

```python
import re
safe = re.sub(r'[^\w.\-]', '_', filename)
headers={"Content-Disposition": f'attachment; filename="{safe}"'},
```

**Regression risks** Low — legitimate filenames contain only safe characters.

**Tests to add** `test_download_file_sanitises_filename_header`.

**Similar locations** `export/router.py:48` and `baseline/router.py:215` generate filenames from a
fixed `opportunity_id` UUID template, so they are safe; `main.py` is the only user-controlled
path.

---

#### TS-A13 — Assistant agent has no output guard and includes user prompt verbatim

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | LLM Safety / Prompt Injection |
| **Release-blocking** | No |
| **Affected roles** | All users using the assistant chat |

**Location** — `backend/app/modules/assistant/agent.py:21-49`; `backend/app/modules/assistant/service.py:159-166`

**Evidence** The `AnthropicAgent` sends the user question and tool context to the LLM without any
output guard:

```python
messages=[{
    "role": "user",
    "content": (
        f"QUESTION: {message}\n\nTOOL RESULTS (the only facts you may use):\n"
        f"{json.dumps(context, default=str)}"
    ),
}]
```

The system prompt instructs the model to answer only from tool results and refuse unrelated
questions, but there is no enforcement: a user message that says "ignore previous instructions"
can override the system prompt, and the model's free-text output is returned directly.

**Root cause** No constrained output (tool/schema call), no prompt-injection classifier, and no
post-hoc validation that the response only cites the provided tool results.

**Impact** The assistant could leak context, give non-grounded legal/commercial advice, or be
manipulated by crafted tender text uploaded by a malicious user.

**Recommended solution** Use Anthropic's tool-calling / JSON mode to force a structured
response, validate citations against the provided context, and run a lightweight prompt-injection
classifier on the user message. At minimum, add a post-processor that rejects answers whose
citations are not in the tool context.

**Regression risks** Low — the assistant is already a thin adapter.

**Tests to add** `test_assistant_refuses_prompt_injection`; `test_assistant_rejects_ungrounded_citation`.

### 9.4 Updated remediation plan

Add to the P0/P1 remediation lists from §5, §7.4, and §8.4:

- **P0 (release-blocking, new)**
  - **TS-I04**: move `extract_upload` out of the async event loop (`asyncio.to_thread` or Celery).
  - **TS-I05**: cap the `csv` payload size in `boq/router.py`.
  - **TS-F02**: fix `applyTokens` to always overwrite the workspace list with the freshly loaded
    list.
- **P1 (pre-release)**
  - **TS-R01**: replace ad-hoc JSON slicing in `risk/classifier.py` with a schema-validated or
    tool-call response.
  - **TS-D02**: normalise all deadline comparisons to UTC and remove the local-time fallback.
  - **TS-Q01**: distinguish "not_mentioned" from "not_met" in the qualification matrix.
  - **TS-X02**: make the BOQ engine explicitly bind its DataFrame and use parameterized SQL.
  - **TS-A11**: cap `crossref` `limit`/`q` and apply database-level pagination.
  - **TS-I06**: add `opportunity_id` filter to `confirm_deadline`.
  - **TS-B05**: add a unique constraint on `(opportunity_id, version)` and serialise `freeze`
    calls.
  - **TS-S03**: sanitise and escape filenames in `Content-Disposition` headers.
  - **TS-A13**: add output validation/guarding to the assistant agent.

### 9.5 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The fourth round re-confirmed every prior release blocker and identified twelve additional gaps,
three of which are release-blocking (TS-I04, TS-I05, TS-F02). There are now **43 findings** (5
Critical, 14 High, 20 Medium, 4 Low) with **17 release-blocking** items. The new blockers are
concentrated in ingestion, BOQ, and frontend session state and are fixable in the same short
timeframe as the auth blockers, but the product should not ship until all seventeen are resolved
and verified.


## 10. Fifth-round re-audit

### 10.1 Summary

The fifth round focused on paths that were not covered by prior rounds or were only lightly
touched: the notifications scheduler, the review audit trail, drafting version generation,
timeline ICS export, the risk and assistant Anthropic adapters, and the ingestion async task
and direct `register_document` route. All previously documented `TS-*` findings were
re-verified and still present. This round adds **eight new findings** (`TS-N02`, `TS-I08`,
`TS-I07`, `TS-R02`, `TS-A14`, `TS-A15`, `TS-B06`, `TS-D03`).

### 10.2 New findings

#### TS-N02 — Notifications deadline-alert scheduler calls a missing `WorkspaceAdmin` method

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection — requires APScheduler to be enabled) |
| **Severity** | **Medium** |
| **Category** | Cross-Module Contract / Operational Defect |
| **Release-blocking** | No |
| **Affected roles** | All workspace members who should receive deadline alerts |

**Location** — `backend/app/modules/notifications/module.py:47-48`; `backend/app/modules/auth/module.py:36`; `backend/app/modules/auth/workspaces.py:18-41`

**Evidence**

The notification scheduler tick uses the `auth.workspace_factory` capability to enumerate workspaces:

```python
# backend/app/modules/notifications/module.py
admin = workspace_factory(session)
for workspace in admin.list_all_workspaces():
```

But the `auth` module publishes `auth.workspace_factory` as `WorkspaceAdmin(session)`:

```python
# backend/app/modules/auth/module.py:36
ctx.registry.provide("auth.workspace_factory", lambda session: WorkspaceAdmin(session))
```

`WorkspaceAdmin` does not implement `list_all_workspaces()`:

```python
class WorkspaceAdmin:
    ...
    def get(self, workspace_id) -> Workspace | None: ...
    def is_paying(self, workspace_id) -> bool: ...
    def get_user(self, user_id) -> dict | None: ...
    def list_members(self, workspace_id) -> list[dict]: ...
    def mark_free_review_used(self, workspace_id) -> None: ...
    def set_plan(self, workspace_id, plan: str) -> None: ...
```

The method exists on `AuthService` (`backend/app/modules/auth/service.py`), not on `WorkspaceAdmin`.

**Root cause**

The `auth.workspace_factory` capability contract is overloaded. Billing and export consume `WorkspaceAdmin` operations (`is_paying`, `get_user`, `set_plan`, `mark_free_review_used`), but notifications expects an admin list-workspaces operation. The wrong class is bound to the slot for this consumer.

**Impact**

When APScheduler is enabled, every `deadline_alert_tick` raises `AttributeError: 'WorkspaceAdmin' object has no attribute 'list_all_workspaces'`. The exception is caught by APScheduler and the job continues, but no alert emails are sent. In the default Docker build APScheduler is not installed (`TS-O04`), so this is a latent failure that will surface as soon as the `scheduler` extra is installed.

**Recommended solution**

Add `list_all_workspaces()` to `WorkspaceAdmin` so the existing registry binding works:

```python
class WorkspaceAdmin:
    ...
    def list_all_workspaces(self) -> list[dict]:
        rows = self.s.execute(select(Workspace.id, Workspace.name, Workspace.plan))
        return [{"workspace_id": str(r[0]), "name": r[1], "plan": r[2]} for r in rows]
```

Or, if `WorkspaceAdmin` is intended to be a narrow billing/admin interface, publish `AuthService` under a separate `auth.admin_factory` capability and have notifications consume that.

**Regression risks**

Low. Billing/export use existing `WorkspaceAdmin` methods that are unchanged.

**Tests to add**

1. `test_deadline_alert_tick_sends_email` — with APScheduler mocked, schedule the tick for a workspace with an upcoming deadline and verify at least one `Message` is queued.
2. `test_workspace_admin_list_all_workspaces` — assert `WorkspaceAdmin` exposes the method notifications expects.

**Similar locations** — `billing/service.py` and `export/service.py` consume `auth.workspace_factory` but only call methods that exist on `WorkspaceAdmin`.

---

#### TS-I08 — Async `process_document` Celery task does not classify, segment clauses, update the submission deadline, or run OCR

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Ingestion / Async Pipeline |
| **Release-blocking** | No |
| **Affected roles** | All users uploading documents with `?async=1` |

**Location** — `backend/app/modules/ingestion/tasks.py:52-99`; `backend/app/modules/ingestion/service.py:90-109`

**Evidence**

The synchronous `upload_document` path calls `register_document` with extracted text:

```python
# backend/app/modules/ingestion/service.py:90-109
def register_document(
    self, workspace_id, opportunity_id, filename: str, sample_text: str = "", **fields
) -> Document:
    kind = classify_text(sample_text, self._anchors()) or "other"
    doc = Document(...)
    ...
    if sample_text.strip():
        self._segment(doc, sample_text)
        self._extract_deadlines(doc, sample_text)
        persist_chunks(...)
```

`classify_text` sets `doc.kind`, `_segment` creates `Clause` rows, and `_extract_deadlines` both creates `Deadline` rows and updates `Opportunity.submission_due` from the earliest submission deadline.

The async Celery task only loads the file, extracts text, persists chunks, and extracts deadlines:

```python
# backend/app/modules/ingestion/tasks.py:52-99 (condensed)
@app.task(bind=True, name="ingestion.process_document")
def process_document(self, document_id: str, workspace_id: str, opportunity_id: str):
    ...
    text, ocr_status = extract_upload(doc.filename, data, ocr=None)
    ...
    doc.ocr_status = ocr_status
    session.commit()
    persist_chunks(session, workspace_id, opportunity_id, document_id, text)
    for ex in extract_deadlines(text):
        session.add(Deadline(...))
    session.commit()
    return {"status": "done", ...}
```

It does not:
- call `classify_text` or set `doc.kind`,
- segment clauses into `Clause` rows,
- update `Opportunity.submission_due`,
- use the configured OCR provider (`ocr=None` is hardcoded, so scanned PDFs are permanently marked `needs_ocr`).

The route docstring says `?async=1` enqueues Celery processing, but the task does not complete the pipeline.

**Root cause**

The async task was written as a minimal text-and-deadline extractor and not kept in sync with the synchronous `register_document` pipeline. It also does not receive the registry, so it cannot resolve the configured OCR provider.

**Impact**

Any document uploaded with `?async=1` is left with `kind="other"` and no `Clause` rows. The deadline wall may miss the `submission_due` update. Scanned PDFs uploaded asynchronously never get OCR applied. Downstream modules (risk, crossref, drafting, assistant) see an empty or incomplete corpus.

**Recommended solution**

Refactor the async task to reuse the same pipeline as `register_document`:

```python
# backend/app/modules/ingestion/tasks.py
def process_document(self, document_id, workspace_id, opportunity_id):
    with session_scope() as session:
        doc = get_document(session, workspace_id, document_id)
        ...
        svc = IngestionService(session, loader_provider=..., publish=_noop)
        svc._classify_and_segment(doc, text)   # new helper shared with register_document
        svc._extract_deadlines(doc, text)
        persist_chunks(...)
```

Pass the OCR provider to `extract_upload` (or import it from `ingestion.ocr` using the `TS_OCR_ENABLED` setting). Ensure `doc.kind`, `doc.pages`, and `opp.submission_due` are updated.

**Regression risks**

Medium. The async task is currently only exercised by `?async=1` uploads; the sync path is the default. The refactor should share the same helpers so behavior converges.

**Tests to add**

1. `test_process_document_sets_kind_and_clauses` — enqueue the task and assert the resulting document has `kind != "other"` and `Clause` rows.
2. `test_process_document_updates_submission_due` — assert `Opportunity.submission_due` is set from a submission deadline in the text.
3. `test_process_document_uses_ocr_provider` — with a fake OCR provider, verify scanned PDFs are OCR'd instead of `needs_ocr`.

**Similar locations** — `upload_document` sync path handles this correctly; the divergence is in `process_document`.

---

#### TS-I07 — `register_document` accepts unbounded `sample_text` and processes it synchronously

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Denial of Service / Input Validation |
| **Release-blocking** | No |
| **Affected roles** | Any authenticated `estimator` |

**Location** — `backend/app/modules/ingestion/router.py:35-37`; `backend/app/modules/ingestion/service.py:90-109`

**Evidence**

The `register_document` body has no maximum length on `sample_text`:

```python
class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1)
    sample_text: str = ""
    supersedes: str | None = None
```

The service then runs the text through several CPU/memory-intensive operations in the request cycle:

```python
def register_document(
    self, workspace_id, opportunity_id, filename: str, sample_text: str = "", **fields
) -> Document:
    kind = classify_text(sample_text, self._anchors()) or "other"
    ...
    if sample_text.strip():
        self._segment(doc, sample_text)
        self._extract_deadlines(doc, sample_text)
        persist_chunks(...)
```

`classify_text` runs a regex search over the full string for each doc-type anchor. `_segment` splits on lines and applies header/xref regexes. `_extract_deadlines` scans every line for date patterns. `persist_chunks` inserts one `DocChunk` row per page. There is no truncation or chunking before this work.

The synchronous `upload_document` path extracts text from a file and passes it to `register_document`; while the file size is capped, the resulting text can still be tens of megabytes.

**Root cause**

The `sample_text` field has no `max_length`, and the ingestion service assumes the input is reasonably sized. The synchronous route does not degrade large inputs to an async worker or stream.

**Impact**

A single `POST /api/ingestion/opportunities/{id}/documents` with a multi-megabyte `sample_text` will hold a worker thread for a long time, perform many regex searches, and insert many rows. This is a straightforward CPU/memory DoS against the backend.

**Recommended solution**

1. Cap `sample_text` in the request body:

```python
class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    sample_text: str = Field("", max_length=1_000_000)
    supersedes: str | None = Field(None, max_length=36)
```

2. For the sync `upload_document` path, pass extracted text through a `DocChunk` generator and only classify/segment the first N characters (e.g. 200 KB) in the request; schedule the rest for the Celery worker (which must be fixed per `TS-I08`).

**Regression risks**

Low. Legitimate tender documents rarely exceed a few hundred kilobytes of extracted text.

**Tests to add**

1. `test_register_document_rejects_oversized_sample_text` — `422` when `sample_text` exceeds the cap.
2. `test_upload_document_large_text_does_not_block` — assert a 50 MB extracted text is either rejected or offloaded to the worker.

**Similar locations** — `boq/router.py:RunBody.csv` has the same unbounded-text problem (`TS-I05`); fix both with a single input-size policy.

---

#### TS-R02 — Risk classifier uses an invalid default Anthropic model name

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **High** |
| **Category** | ML/LLM Integration / Product Functionality |
| **Release-blocking** | **YES** |
| **Affected roles** | Paying users running risk review |

**Location** — `backend/app/modules/risk/classifier.py:33-34`; `backend/app/modules/risk/module.py:15`

**Evidence**

`AnthropicClassifier` defaults to a non-existent model:

```python
class AnthropicClassifier:
    def __init__(self, model: str = "claude-sonnet-5", max_tokens: int = 900):
        self.model = model
        self.max_tokens = max_tokens
```

The `risk` module instantiates it without override when `ANTHROPIC_API_KEY` is set:

```python
if os.environ.get("ANTHROPIC_API_KEY"):
    ctx.registry.provide("risk.classifier", AnthropicClassifier())
```

`claude-sonnet-5` is not a valid Anthropic model identifier. The Anthropic SDK will raise a model-not-found error, which is caught here:

```python
try:
    msg = client.messages.create(
        model=self.model,
        ...
    )
except Exception:
    logger.exception("AnthropicClassifier failed for pattern %s", pattern.id)
    return []
```

So every pattern classification silently returns `[]`. The risk engine (`risk/engine.py:run_pattern`) then produces no presence findings for patterns that have candidate clauses, only absence findings for patterns with no candidates. The core risk-review feature is effectively disabled whenever an Anthropic key is configured.

**Root cause**

A placeholder model name was hardcoded and never replaced with a real default or a configurable setting.

**Impact**

Paying workspaces with an Anthropic key configured get empty risk findings. This breaks the product's primary value proposition and, combined with `TS-P02` (paid workspaces see only `validated` patterns), can leave users with zero risk output.

**Recommended solution**

Add a `TS_ANTHROPIC_MODEL` setting and pass it through the module:

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    ...
    anthropic_model: str = "claude-3-5-sonnet-20241022"

# backend/app/modules/risk/module.py
ctx.registry.provide(
    "risk.classifier",
    AnthropicClassifier(model=s.anthropic_model, max_tokens=s.anthropic_max_tokens),
)
```

Validate the model name against a known-good allow-list and fail fast on startup if it is not recognized, rather than silently returning empty lists at runtime.

**Regression risks**

Low. The change only affects deployments with `ANTHROPIC_API_KEY` set, which are currently broken.

**Tests to add**

1. `test_risk_classifier_with_invalid_model_fails_fast` — startup fails or the call raises a clear `ConfigurationError`.
2. `test_risk_classifier_valid_model_returns_findings` — with a mocked Anthropic client, `run_patterns` returns the expected findings.

**Similar locations** — `assistant/agent.py` has the same invalid default (`TS-A14`); fix both together and share the model setting.

---

#### TS-A14 — Assistant agent uses an invalid default Anthropic model name

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | ML/LLM Integration / Product Functionality |
| **Release-blocking** | No |
| **Affected roles** | All users of the assistant chat |

**Location** — `backend/app/modules/assistant/agent.py:22-23`; `backend/app/modules/assistant/module.py:16`

**Evidence**

`AnthropicAgent` also defaults to `claude-sonnet-5`:

```python
class AnthropicAgent:
    def __init__(self, model: str = "claude-sonnet-5", max_tokens: int = 700):
        self.model = model
        self.max_tokens = max_tokens
```

The assistant module instantiates it without override:

```python
if os.environ.get("ANTHROPIC_API_KEY"):
    from app.modules.assistant.agent import AnthropicAgent
    ctx.registry.provide("assistant.agent", AnthropicAgent())
```

When the model name fails, the exception is caught and the agent returns a fallback string:

```python
except Exception:
    logger.exception("AnthropicAgent failed")
    return "I couldn't complete that request just now — please try a specific query."
```

**Root cause**

Same as `TS-R02`: a placeholder model name hardcoded in the LLM adapter and never wired to a setting.

**Impact**

The assistant silently degrades to a generic error message for every free-form query when an Anthropic key is configured. Users may not realize the assistant is broken because there is no HTTP error.

**Recommended solution**

Share the `TS_ANTHROPIC_MODEL` setting introduced for `TS-R02`:

```python
ctx.registry.provide(
    "assistant.agent",
    AnthropicAgent(model=s.anthropic_model, max_tokens=s.anthropic_max_tokens),
)
```

Fail fast on startup for unrecognized model names.

**Regression risks**

Low. No currently working assistant path is affected.

**Tests to add**

1. `test_assistant_with_invalid_model_returns_error` — the agent returns a clear error rather than silently swallowing.
2. `test_assistant_valid_model_uses_shared_setting` — the module passes the configured model to `AnthropicAgent`.

**Similar locations** — `risk/classifier.py` (`TS-R02`).

---

#### TS-A15 — Review audit trail endpoint ignores `opportunity_id`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Data Isolation / Audit |
| **Release-blocking** | No |
| **Affected roles** | `reviewer`, `admin`, `owner` |

**Location** — `backend/app/modules/review/router.py:83-90`; `backend/app/modules/review/service.py:98-100`; `backend/app/modules/review/models.py:19-29`

**Evidence**

The route is scoped to an opportunity:

```python
@router.get("/opportunities/{opportunity_id}/audit")
def audit_trail(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    rows = _service(request, session).audit_trail(principal.workspace_id, opportunity_id)
```

But the service ignores the `opportunity_id`:

```python
def audit_trail(self, workspace_id, opportunity_id=None) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.workspace_id == uuid.UUID(str(workspace_id)))
    return list(self.s.scalars(stmt.order_by(AuditLog.id.desc())))
```

And the `AuditLog` model has no `opportunity_id` column:

```python
class AuditLog(Base, WorkspaceScopedMixin):
    _tablename_ = "audit_log"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

So `/opportunities/{opportunity_id}/audit` returns every `AuditLog` row in the workspace, not just the ones for that opportunity.

**Root cause**

The audit log schema was built workspace-scoped but not opportunity-scoped, and the service signature accepts an `opportunity_id` parameter that it never uses.

**Impact**

A reviewer for one opportunity can see audit entries for every other opportunity in the workspace (e.g., findings accepted/rejected, notes added). This is a workspace-internal data-leakage and compliance issue. It also makes the per-opportunity audit UI useless.

**Recommended solution**

1. Add `opportunity_id` to `AuditLog` (nullable for workspace-level events) and backfill from `object_id` where `object_type="finding"` by joining to `FindingRow`.
2. Update `ReviewService.audit` to accept and store `opportunity_id`.
3. Filter `audit_trail` by `opportunity_id` when provided:

```python
def audit_trail(self, workspace_id, opportunity_id=None) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.workspace_id == uuid.UUID(str(workspace_id)))
    if opportunity_id:
        stmt = stmt.where(AuditLog.opportunity_id == uuid.UUID(str(opportunity_id)))
    return list(self.s.scalars(stmt.order_by(AuditLog.id.desc())))
```

**Regression risks**

Low. Requires a migration, but opportunity-level audit is the intended behavior.

**Tests to add**

1. `test_audit_trail_filters_by_opportunity` — create audit entries for two opportunities and assert the endpoint returns only the requested one.
2. `test_audit_log_stores_opportunity_id` — after `review_finding`, the `AuditLog` row has the finding's `opportunity_id`.

**Similar locations** — `ReviewService.last_reviewer` already filters `AuditLog` by the opportunity's finding IDs, which is a workaround for the same missing column.

---

#### TS-B06 — `Artifact.version` uses a non-atomic read-modify-write increment

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Concurrency / Data Integrity |
| **Release-blocking** | No |
| **Affected roles** | Users generating artifacts concurrently |

**Location** — `backend/app/modules/drafting/service.py:136-154`; `backend/app/modules/drafting/models.py:16`

**Evidence**

`DraftingService.generate` computes the next artifact version like this:

```python
opp = uuid.UUID(str(opportunity_id))
next_version = (
    self.s.scalar(
        select(func.coalesce(func.max(Artifact.version), 0)).where(
            Artifact.opportunity_id == opp, Artifact.kind == kind
        )
    )
    + 1
)
artifact = Artifact(
    workspace_id=uuid.UUID(str(workspace_id)),
    opportunity_id=opp,
    kind=kind,
    version=next_version,
    body=body,
    model_meta={"generator": "deterministic", "findings": len(findings)},
)
self.s.add(artifact)
self.s.commit()
```

This is a classic read-modify-write race: two concurrent requests can read the same `max(version)`, both compute the same `next_version`, and both try to insert. The `Artifact` model has a unique constraint:

```python
__table_args__ = (UniqueConstraint("opportunity_id", "kind", "version"),)
```

So one request succeeds and the other raises an `IntegrityError` (HTTP 500). The data is not corrupted, but the API is not concurrency-safe.

**Root cause**

The version increment is not serialized. SQLAlchemy's `func.max` read and the subsequent insert are not an atomic single statement.

**Impact**

Concurrent artifact generation (e.g., two reviewers clicking "Generate" at the same time, or the UI retrying a slow request) can fail with 500 errors.

**Recommended solution**

Use an advisory lock or a single atomic insert with `INSERT ... ON CONFLICT DO NOTHING` and retry:

```python
from sqlalchemy import text
def _next_version_atomic(self, opp, kind) -> int:
    # PostgreSQL example
    self.s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": f"artifact:{opp}:{kind}"})
    return self.s.scalar(select(func.coalesce(func.max(Artifact.version), 0)).where(...)) + 1
```

For SQLite, use an application-level `threading.Lock` or move the operation to the worker. Long-term, add a unique constraint and a retry loop around the insert.

**Regression risks**

Low. The fix only changes the version-assignment path; artifact content and ordering are unchanged.

**Tests to add**

1. `test_generate_artifact_concurrent` — two concurrent `generate` calls for the same opportunity/kind produce versions `1` and `2` without 500s.
2. `test_generate_artifact_no_duplicate_versions` — assert the unique constraint is never violated under load.

**Similar locations** — `baseline/service.py` has the same pattern with `Baseline.version` (`TS-B05`); fix both with the same locking strategy.

---

#### TS-D03 — Timeline ICS export appends `Z` to naive or local datetimes; synthetic `tender_published` uses `created_at`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Date/Time / Calendar Export |
| **Release-blocking** | No |
| **Affected roles** | Users exporting deadlines to a calendar |

**Location** — `backend/app/modules/timeline/router.py:65-68`; `backend/app/modules/timeline/service.py:103-115`; `backend/app/modules/ingestion/deadlines.py:65-72`

**Evidence**

The ICS export always appends a literal `Z` to `due_at`:

```python
@router.get("/opportunities/{opportunity_id}/timeline.ics", response_class=PlainTextResponse)
def export_ics(...):
    for e in events:
        if e.due_at is None:
            continue
        dt = e.due_at.strftime("%Y%m%dT%H%M%SZ")
```

`due_at` can be:
1. A **naive** `datetime` produced by `extract_deadlines.parse_date` (`strptime` with no timezone):

```python
def parse_date(text: str) -> datetime | None:
    for fmt in _FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None
```

2. `opp.created_at`, which is created with `DateTime(timezone=True)` but may be stored as naive depending on the backend.

Appending `Z` claims the time is UTC. A naive `datetime` formatted as `20260729T153000Z` is ambiguous or wrong. A local timezone-aware `datetime` would be emitted in local wall-clock time with a `Z` suffix, which is also wrong.

Additionally, the synthetic `tender_published` event falls back to `opp.created_at` when no published deadline is extracted:

```python
if not has_published and opp.created_at is not None:
    events.append(
        TimelineEvent(
            kind="tender_published",
            ...
            due_at=opp.created_at,
            ...
            source="synthetic",
        )
    )
```

This is the date the opportunity was recorded, not the tender's actual publication date, and it may be wrong by hours due to the `Z` suffix.

**Root cause**

The ICS exporter does not normalize timestamps to UTC before formatting, and the fallback publisher date is not a real extracted fact.

**Impact**

Calendar entries are offset from the real deadline, which can mislead users into missing a submission or showing up at the wrong time. The synthetic publication date is misleading.

**Recommended solution**

1. Convert all `due_at` values to UTC before ICS formatting:

```python
from datetime import UTC

def _ics_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
```

2. Store extracted deadlines with an explicit timezone (UTC) in the database, or at least document that the application treats them as UTC.
3. For `tender_published`, either require an extracted publication date or clearly label the event as "Tender recorded" rather than "Tender published".

**Regression risks**

Low. Consumers of the ICS feed will get correct UTC timestamps.

**Tests to add**

1. `test_export_ics_uses_utc` — a naive `due_at` of `2026-07-29 15:30:00` is emitted as `20260729T153000Z`, and a local timezone `due_at` is converted to the correct UTC time.
2. `test_export_ics_rejects_unzoned_created_at` — the synthetic `tender_published` event carries a UTC timestamp if `created_at` is naive.

**Similar locations** — `_event_json` in `timeline/router.py` emits `due_at.isoformat()` which is at least honest about timezone awareness, but it too should normalize to UTC for API consistency.

---

### 10.3 Updated remediation plan

Add to the P0/P1 remediation lists from §5, §7.4, §8.4, and §9.4:

- **P0 (release-blocking, new)**
  - **TS-R02**: replace the invalid Anthropic model default with a real, configurable model and fail fast on startup.
- **P1 (pre-release)**
  - **TS-N02**: fix the `auth.workspace_factory` capability contract used by the notifications scheduler.
  - **TS-I08**: complete the async `process_document` task (classification, segmentation, `submission_due`, OCR).
  - **TS-I07**: cap `sample_text` and large extracted-text sizes before synchronous processing.
  - **TS-A14**: wire the assistant agent to the same configurable Anthropic model setting.
  - **TS-A15**: add `opportunity_id` to `AuditLog` and filter `audit_trail` by it.
  - **TS-B06**: serialize `Artifact.version` increments with advisory locks or a single atomic insert.
  - **TS-D03**: normalize `due_at` to UTC for ICS export and fix the `tender_published` fallback.

### 10.4 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The fifth round re-confirmed every prior release blocker and identified eight additional gaps,
one of which is release-blocking (`TS-R02`). There are now **51 findings** (5 Critical, 15 High,
27 Medium, 4 Low) with **18 release-blocking** items. The new release blocker is a broken
core feature (risk review silently fails when an Anthropic key is configured) and must be
resolved before any paying user can rely on the product.

## 11. Sixth-round re-audit

### 11.1 Summary

The sixth round focused on paths that had not been deeply reviewed in prior rounds or were
flagged for a second look: `core/storage.py`, `main.py` CORS/allowed-hosts guard, the
`billing/providers.py` and `webhook.py` Stripe integration, `ingestion/tus.py`, and the
`review`/`findings` authz boundary. All previously documented `TS-*` findings were re-verified
and still present. This round adds **six new findings** (`TS-S04`, `TS-O05`, `TS-B07`, `TS-B08`,
`TS-I09`, `TS-A16`).

### 11.2 New findings

#### TS-S04 — `LocalStorage` async methods perform synchronous file I/O

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Storage / Async I/O |
| **Release-blocking** | No |
| **Affected roles** | All users uploading/downloading files when `TS_STORAGE_TYPE=local` |

**Location** — `backend/app/core/storage.py:99-123`

**Evidence** `LocalStorage` declares async methods but calls synchronous `pathlib` operations:

```python
class LocalStorage:
    async def write(self, key: str, data: bytes, content_type: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.root))

    async def read(self, key: str) -> bytes:
        path = self.root / key
        if not path.exists():
            raise StorageError("file_not_found")
        return path.read_bytes()
```

`delete` is identical (`path.exists()`, `path.unlink()`). `S3Storage` correctly uses
`asyncio.to_thread`.

**Root cause** The local backend was written with async signatures but not async
implementations.

**Impact** Uploads and downloads block the event-loop thread while reading/writing files. Under
load this stalls other requests and can make the app unresponsive. The issue is invisible on
small files or light traffic.

**Recommended solution** Wrap all blocking calls in `asyncio.to_thread` (or use `aiofiles`):

```python
async def write(self, key, data, content_type):
    path = self.root / key
    await asyncio.to_thread(lambda: path.parent.mkdir(parents=True, exist_ok=True))
    await asyncio.to_thread(path.write_bytes, data)
    return str(path.relative_to(self.root))
```

Do the same for `read` and `delete`.

**Regression risks** Low — only the local backend implementation changes.

**Tests to add** `test_local_storage_write_does_not_block_event_loop` — run concurrent writes
and assert they overlap rather than execute sequentially.

**Similar locations** `ingestion/tus.py` (`tus_create`, `tus_patch`, `_load_state`, `_save_state`)
also performs synchronous file I/O in async routes (`TS-I09`).

---

#### TS-O05 — Production guard for CORS and allowed hosts can be bypassed with a comma-separated wildcard

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Configuration / Production Hardening |
| **Release-blocking** | No |
| **Affected roles** | All users (if an admin misconfigures CORS/hosts) |

**Location** — `backend/app/core/config.py:36-39,98-107`; `backend/app/main.py:66-69`

**Evidence** `cors_origins` and `allowed_hosts` are comma-separated strings, split into lists:

```python
cors_origins: str = "*"
allowed_hosts: str = "*"

def cors_origin_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

def allowed_host_list(self) -> list[str]:
    return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()] or ["*"]
```

The production guard only checks the exact string `"*"`:

```python
if settings.cors_origins == "*":
    errors.append("TS_CORS_ORIGINS must be explicit in production (no wildcard)")
if settings.allowed_hosts == "*":
    errors.append("TS_ALLOWED_HOSTS must be explicit in production (no wildcard)")
```

So `TS_CORS_ORIGINS="https://app.example.com,*"` or `TS_ALLOWED_HOSTS="app.example.com, *"`
bypass the guard and produce a list containing a wildcard.

**Root cause** The guard checks the raw string, not the parsed list, and does not reject wildcard
elements.

**Impact** `TrustedHostMiddleware` receives a list containing `"*"`, which disables host
validation. `CORSMiddleware` receives a list containing `"*"` and `allow_credentials` is forced
to `False`, so any origin can make cross-origin requests (without cookies). An admin can
unknowingly deploy with an open CORS/hosts policy.

**Recommended solution** In `_validate_prod_settings`, call `settings.cors_origin_list()` and
`settings.allowed_host_list()` and raise if either contains `"*"` or is empty after stripping:

```python
if "*" in settings.cors_origin_list():
    errors.append("TS_CORS_ORIGINS must be explicit in production (no wildcard)")
if "*" in settings.allowed_host_list():
    errors.append("TS_ALLOWED_HOSTS must be explicit in production (no wildcard)")
```

**Regression risks** Low — only production startup validation changes.

**Tests to add** `test_prod_settings_reject_wildcard_in_cors_list`;
`test_prod_settings_reject_wildcard_in_allowed_hosts_list`.

**Similar locations** `cors_supports_credentials()` already checks `"*" in cors_origin_list()`
but only to disable credentials; the startup guard should reject the wildcard outright.

---

#### TS-B07 — Stripe checkout uses hardcoded `example.com` redirect URLs

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Billing / Stripe Integration |
| **Release-blocking** | No |
| **Affected roles** | Users paying via Stripe |

**Location** — `backend/app/modules/billing/providers.py:115-117`

**Evidence**

```python
session = self._client.checkout.Session.create(
    payment_method_types=["card"],
    line_items=[...],
    mode="payment",
    success_url="https://example.com/success",
    cancel_url="https://example.com/cancel",
    metadata=metadata,
)
```

`success_url` and `cancel_url` are hardcoded to `example.com` in the live Stripe provider.

**Root cause** Placeholder URLs were left in the live provider and not replaced with settings or
request-derived URLs.

**Impact** After a successful Stripe payment the customer is redirected to `example.com`
instead of the application. The UI never receives the session completion signal, so the user
sees a broken payment flow even though the webhook may activate the workspace server-side.

**Recommended solution** Add `TS_STRIPE_SUCCESS_URL` and `TS_STRIPE_CANCEL_URL` settings (or a
single `TS_PUBLIC_APP_URL` and derive `/billing/stripe/success` and `/billing/stripe/cancel`),
and pass them to `checkout.Session.create`. Validate they are HTTPS in production.

**Regression risks** Low — only affects Stripe checkout when live keys are configured.

**Tests to add** `test_stripe_checkout_uses_configured_redirect_urls`.

**Similar locations** `RazorpayProvider` does not require redirect URLs; only Stripe is affected.

---

#### TS-B08 — Stripe webhook verifier swallows all exceptions and returns `None`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Billing / Webhook Validation |
| **Release-blocking** | No |
| **Affected roles** | Stripe-using workspaces, operators |

**Location** — `backend/app/modules/billing/webhook.py:31-48`

**Evidence**

```python
def verify_stripe_signature(
    raw_body: bytes, signature: str, secret: str | SecretStr | None
) -> dict | None:
    secret_value = _secret_to_bytes(secret).decode() if secret else ""
    if not signature or not secret_value:
        return None
    try:
        import stripe
        return stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=signature,
            secret=secret_value,
        )
    except Exception as exc:
        logger.exception("stripe webhook verification failed: %s", exc)
        return None
```

Every exception — `SignatureVerificationError`, `ValueError` from a malformed payload,
`ImportError` if `stripe` is missing, or any runtime SDK error — is caught and logged at
exception level. The function returns `None`, so the caller treats it as a bad signature and
returns HTTP 400.

**Root cause** An overly broad `except Exception` was used to avoid surfacing any Stripe SDK
failures.

**Impact** Real SDK/configuration problems are hidden in logs and appear as signature failures,
so operators cannot distinguish "wrong secret" from "Stripe SDK broken". The service returns
400, so Stripe may stop retrying or retry pointlessly, and payment activation may never happen.

**Recommended solution** Catch only `stripe.error.SignatureVerificationError` (and `ValueError`
for malformed payload) and return `None` for those. Let unexpected SDK/import errors propagate
as 500 so they are visible in error tracking and not retried.

```python
try:
    import stripe
    return stripe.Webhook.construct_event(...)
except stripe.error.SignatureVerificationError:
    return None
except ValueError:
    return None
```

**Regression risks** Low — only changes error-handling paths.

**Tests to add** `test_verify_stripe_signature_distinguishes_signature_failure_from_sdk_error`.

**Similar locations** `process_stripe_webhook` in `billing/service.py` and `billing/router.py`
consume this verifier.

---

#### TS-I09 — tus endpoints perform synchronous file I/O and `OPTIONS` returns a non-compliant empty body

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Ingestion / tus Protocol |
| **Release-blocking** | No |
| **Affected roles** | Users uploading large documents via tus |

**Location** — `backend/app/modules/ingestion/tus.py:87-90,118-119,123-140,143-164`

**Evidence** The `OPTIONS` handler returns an empty body with no tus protocol headers:

```python
@router.options("/")
def tus_options():
    return {}  # CORS handled globally; tus clients may probe OPTIONS.
```

A tus client expects `Tus-Resumable`, `Tus-Version`, `Tus-Max-Size`, etc. Without these the
client cannot discover server capabilities.

`tus_create` and `tus_patch` are async but read and write local chunk files synchronously:

```python
@router.post("/")
async def tus_create(...):
    ...
    _file_path(upload_id).write_bytes(b"")  # sync
    _save_state(upload_id, state)             # _state_path(upload_id).write_text(...)
    return {}

@router.patch("/{upload_id}")
async def tus_patch(...):
    state = _load_state(upload_id)            # json.loads(path.read_text())
    ...
    with file_path.open("ab") as f:
        f.write(data)
    state["offset"] = file_path.stat().st_size
    _save_state(upload_id, state)
```

`_finalize` also reads the merged file synchronously before `await validate_and_store`.

**Root cause** tus routes were written as async handlers but perform blocking filesystem calls
inline; the `OPTIONS` probe was not implemented to spec.

**Impact** In addition to `TS-I03` (missing `Location` header, node-local storage, no cleanup),
tus uploads also block the event loop during every chunk read/write. Some tus clients may
refuse to start uploads when `OPTIONS` is non-compliant.

**Recommended solution** 1. Implement `tus_options` to return protocol headers:

```python
@router.options("/")
def tus_options():
    return Response(
        headers={
            "Tus-Resumable": "1.0.0",
            "Tus-Version": "1.0.0",
            "Tus-Max-Size": str(DEFAULT_MAX_UPLOAD_SIZE),
            "Tus-Extension": "creation,creation-defer-length",
        }
    )
```

2. Wrap `_file_path(...).write_bytes`, `_save_state`, `_load_state`, and chunk writes in
`asyncio.to_thread`. 3. Return the `Location` header from `tus_create` (already tracked by
`TS-I03`).

**Regression risks** Low; the tus endpoint is currently non-functional in standard clients.

**Tests to add** `test_tus_options_returns_protocol_headers`;
`test_tus_create_does_not_block_event_loop`.

**Similar locations** `LocalStorage` (`TS-S04`) and `_finalize` share the same sync-I/O
anti-pattern.

---

#### TS-A16 — `POST /api/review/findings/{finding_id}` does not scope by opportunity

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Authorization / Data Isolation |
| **Release-blocking** | No |
| **Affected roles** | `reviewer`, `admin`, `owner` |

**Location** — `backend/app/modules/review/router.py:50-70`;
`backend/app/modules/review/service.py:52-66`; `backend/app/modules/findings/store.py:49-55,63-83`

**Evidence** The route accepts only a `finding_id`:

```python
@router.post("/findings/{finding_id}")
def review_finding(
    finding_id: str,
    body: ReviewBody,
    ...
):
    row = _service(request, session).review_finding(
        principal.workspace_id,
        finding_id,
        decision=body.decision,
        ...
    )
```

The service delegates to `FindingStore.set_review`, which calls `FindingStore.get`:

```python
def get(self, workspace_id, finding_id) -> FindingRow | None:
    return self.s.scalar(
        select(FindingRow).where(
            FindingRow.id == uuid.UUID(str(finding_id)),
            FindingRow.workspace_id == uuid.UUID(str(workspace_id)),
        )
    )
```

No `opportunity_id` appears in the query. `FindingRow` has an `opportunity_id` column, but it
is not used to scope the update.

**Root cause** `review_finding` was built around finding IDs only, without tying the call to
the opportunity being reviewed. The store's `get`/`set_review` methods are workspace-scoped but
not opportunity-scoped.

**Impact** A reviewer who knows the UUID of a finding from another opportunity in the same
workspace can accept, reject, or edit it. This cross-opportunity write corrupts the wrong
tender's review state and audit trail.

**Recommended solution** Add an `opportunity_id` path parameter to the route (or derive it from
the session) and update `FindingStore.get`/`set_review` to include `opportunity_id` in the
`where` clause:

```python
def set_review(self, workspace_id, opportunity_id, finding_id, *, status, ...):
    row = self.get(workspace_id, opportunity_id, finding_id)
    if row is None:
        return None
    ...

def get(self, workspace_id, opportunity_id, finding_id) -> FindingRow | None:
    return self.s.scalar(
        select(FindingRow).where(
            FindingRow.id == uuid.UUID(str(finding_id)),
            FindingRow.workspace_id == uuid.UUID(str(workspace_id)),
            FindingRow.opportunity_id == uuid.UUID(str(opportunity_id)),
        )
    )
```

Update the review router and service signatures accordingly.

**Regression risks** Low — all current callers already operate within a known opportunity
context; the frontend calls are per-opportunity.

**Tests to add** `test_review_finding_rejects_foreign_opportunity`;
`test_finding_store_get_scopes_by_opportunity`.

**Similar locations** `findings/store.py` `replace_for_producer` and `list` already scope by
`opportunity_id`; only `get`/`set_review` are missing it. `confirm_deadline` has a related
`opportunity_id` scoping gap (`TS-I06`).

### 11.3 Updated remediation plan

Add to the P0/P1 remediation lists from §5, §7.4, §8.4, §9.4, and §10.3:

- **P0 (release-blocking, new)**
  - None.
- **P1 (pre-release)**
  - **TS-S04**: wrap `LocalStorage` `read`/`write`/`delete` in `asyncio.to_thread`.
  - **TS-O05**: reject wildcard entries in `cors_origin_list()` and `allowed_host_list()` in
    the production startup guard.
  - **TS-B07**: configure Stripe `success_url`/`cancel_url` from settings, not `example.com`.
  - **TS-B08**: narrow Stripe webhook verifier exception handling to
    `SignatureVerificationError`/`ValueError`; let SDK/runtime errors propagate.
  - **TS-I09**: wrap tus file I/O in `asyncio.to_thread` and implement a compliant
    `tus_options` response (also return `Location` from `tus_create` per `TS-I03`).
  - **TS-A16**: scope `ReviewService.review_finding` and `FindingStore.set_review` by
    `opportunity_id`.

### 11.4 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The sixth round re-confirmed every prior release blocker and identified six additional gaps.
There are now **57 findings** (5 Critical, 15 High, 33 Medium, 4 Low) with **18 release-blocking**
items. The new gaps are infrastructure, configuration, payment-flow, and authz hardening issues;
they do not add new release blockers, but they should be fixed and verified before launch.

## 12. Seventh-round re-audit

### 12.1 Summary

The seventh round concentrated on the product invariants in `CLAUDE.md` §4 and the build doc that
had not been explicitly audited in prior passes: money in minor units, every extracted fact
carrying page/quote provenance, deterministic severity evaluation, and correct workspace selection on
login. All previously documented `TS-*` findings were re-verified and remain present. This round
adds **four new findings** (`TS-C01`, `TS-I10`, `TS-A17`, `TS-R03`).

### 12.2 New findings

#### TS-C01 — `Finding.amount_exposure` and monetary thresholds are stored/extracted as `float` major units, violating the minor-units invariant

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Data Integrity / Product Invariant / Money |
| **Release-blocking** | No |
| **Affected roles** | All users viewing risk, BOQ, baseline, drafting, or standards findings |

**Location** — `backend/app/core/contracts/findings.py:64`; `backend/app/modules/findings/models.py:60`;
`backend/app/modules/drafting/validators.py:18-44`; `backend/app/modules/drafting/service.py` and
`backend/app/modules/baseline/service.py` (amount casts); `backend/app/modules/boq/engine.py:96-99`;
`backend/app/modules/standards/service.py:25-29` and `models.py`; `backend/app/modules/standards/service.py:_extract_number`

**Evidence** The shared `Finding` contract exposes money as an optional `float`:

```python
class Finding(BaseModel):
    ...
    amount_exposure: float | None = None
```

The DB model maps it as `Numeric(16, 2)`:

```python
class FindingRow(Base, WorkspaceScopedMixin):
    ...
    amount_exposure: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
```

The drafting `FactTable` stores extracted amounts as `float` with a major-unit regex and a 0.5 tolerance:

```python
@dataclass
class FactTable:
    amounts: list[float] = field(default_factory=list)

    def has_amount(self, value: float, tol: float = 0.5) -> bool:
        return any(abs(value - a) <= tol for a in self.amounts)

_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
...
for m in _AMOUNT_RE.finditer(grounded):
    value = float(m.group(1).replace(",", ""))
    if value not in amounts:
        amounts.append(value)
```

The BOQ engine uses `float` arithmetic and `round(..., 2)`:

```python
df["amount_calc"] = (
    pd.to_numeric(df["qty"], errors="coerce") * pd.to_numeric(df["rate"], errors="coerce")
).round(2)
```

Standards thresholds are `float` and the amount extractor returns `float`:

```python
class PolicyBody(BaseModel):
    threshold: float = Field(ge=0)
...
def _extract_number(finding: dict, unit: str) -> float | None:
    ...
    return float(raw)
```

**Root cause** The product invariant "Money in minor units (paise), never float" is documented but not
enforced in the shared contract, the database schema, or the consumers. Major-unit `float` values
propagate through risk, drafting, baseline, BOQ, and standards, carrying rounding errors and breaking
cross-currency consistency.

**Impact** Small rounding discrepancies in BOQ totals and amount comparisons; risk/standards/baseline
findings can expose or compare amounts at the wrong scale; monetary fields cannot safely represent
non-INR currencies or sub-rupee figures in minor units.

**Recommended solution** 1) Change `Finding.amount_exposure` to `int | None` (paise/minor units).
2) Change `FindingRow.amount_exposure` to `BigInteger` and migrate existing data. 3) Update
`FactTable` to parse amounts into integer paise and compare integer values with no tolerance. 4)
Reimplement BOQ engine with `Decimal`/minor-unit arithmetic. 5) Update standards `PolicyBody.threshold`
to `int` and `_extract_number` to return minor units. 6) Update `_rupees()` formatting to divide by 100.

**Regression risks** Moderate — the `amount_exposure` JSON field and DB column change type; any client
rendering the value must format it as currency. Existing tests that expect float comparisons will need
updates.

**Tests to add** `test_finding_amount_exposure_is_minor_units`;
`test_fact_table_rejects_major_unit_float`; `test_boq_amount_calc_no_float_rounding`;
`test_standards_threshold_minor_units`.

**Similar locations** `backend/app/modules/drafting/service.py` and
`backend/app/modules/baseline/service.py` cast `amount_exposure` to `float`;
`backend/app/modules/standards/models.py` maps `threshold` to `Numeric(12, 4)`;
`backend/app/modules/boq/engine.py` computes `amount`/`amount_calc` with `float` and `round`.

---

#### TS-I10 — XLSX/CSV text extraction does not emit page markers, so spreadsheet-derived deadlines and clauses lose page provenance

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Ingestion / Provenance / Product Invariant |
| **Release-blocking** | No |
| **Affected roles** | All users uploading spreadsheet tender documents |

**Location** — `backend/app/modules/ingestion/extract.py:56-77`;
`backend/app/modules/ingestion/doc_text.py:27-45`; `backend/app/modules/ingestion/segment.py:41-68`;
`backend/app/modules/ingestion/deadlines.py:83-105`

**Evidence** XLSX extraction emits `[sheet:<name>]` separators:

```python
def _xlsx_to_text(data: bytes) -> str:
    ...
    lines.append(f"[sheet:{ws.title}]\n" + "\n".join(out))
    return "\n".join(lines)
```

CSV extraction does the same:

```python
def _csv_to_text(data: bytes) -> str:
    ...
    return "\n".join(f"[sheet:{filename}]\n" + text for ...)
```

PDF extraction emits `[pN]` markers via `_join_pages`. The page splitter, clause segmenter, and
deadline extractor all key off `[pN]`:

```python
_PAGE_MARKER = re.compile(r"^\s*\[p(\d+)\]\s*$", re.MULTILINE)


def segment_clauses(text: str) -> list[ClauseSeg]:
    page = 1
    for line in text.splitlines():
        pm = _PAGE.match(line)
        if pm:
            page = int(pm.group(1))
            continue
        ...
```

**Root cause** Spreadsheet text is normalised to "sheet" markers instead of page markers, and the
downstream page-aware pipeline only understands `[pN]`. No component maps sheets to synthetic page
numbers.

**Impact** Every deadline or clause extracted from an XLSX/CSV document gets `source_page=1` and is
stored as a single "Preamble" segment with `clause_ref=None`, violating the "every extracted fact has
`source_page`" invariant and making it impossible to cite the source sheet/page for
spreadsheet-derived facts.

**Recommended solution** Emit `[pN]` markers in `_xlsx_to_text`/`_csv_to_text` (e.g., `[p1]` for each
sheet or `[pN]` per logical page), or update `_PAGE_MARKER`, `segment_clauses`, and `extract_deadlines`
to treat `[sheet:<name>]` as a page boundary and derive a `source_page` from the sheet index. Also
update `DocChunk` and `Clause` `page`/`page_from` accordingly.

**Regression risks** Low — changes only the text normalisation for spreadsheets. PDF extraction
remains unchanged.

**Tests to add** `test_xlsx_extraction_emits_page_markers`;
`test_csv_deadline_carries_correct_source_page`;
`test_xlsx_clause_segmentation_not_single_preamble`.

**Similar locations** `backend/app/modules/ingestion/doc_text.py:extract_pages` is the other consumer
of `[pN]` markers; `backend/app/modules/ingestion/tasks.py` calls `extract_upload` and should be
included in regression tests.

---

#### TS-A17 — Email/password login selects an arbitrary workspace for multi-workspace users

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Auth / Tenant Isolation |
| **Release-blocking** | No |
| **Affected roles** | Users who are members of more than one workspace |

**Location** — `backend/app/modules/auth/service.py:160-162`

**Evidence** `login()` resolves the user's workspace with an unqualified `scalar()`:

```python
member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
workspace_id = member.workspace_id if member else None
role = member.role if member else "owner"
```

There is no `ORDER BY`, `LIMIT 1`, or primary-workspace flag, so the returned row is whichever row
the database happens to return first.

**Root cause** The query assumes a user has at most one workspace, or that the first row is
deterministic. The codebase has no concept of a primary/default workspace, and the login flow has no
workspace-selection step.

**Impact** A multi-workspace user may be logged into the wrong workspace on every login, with the
access token pointing at a different tenant's data. The `switch_workspace` endpoint exists, but the
initial session is non-deterministic.

**Recommended solution** Add `ORDER BY WorkspaceMember.created_at` (or `is_primary DESC`) and
`LIMIT 1` to the query; better, return a list of workspaces and require explicit selection when there
are multiple. Persist the choice in the token or session.

**Regression risks** Low — single-workspace users are unaffected. Multi-workspace users get a stable
workspace.

**Tests to add** `test_login_multi_workspace_selects_oldest_or_primary`;
`test_login_multi_workspace_reproducible`.

**Similar locations** `backend/app/modules/auth/service.py:switch_workspace` already supports
explicit workspace selection; the login path should reuse the same membership check.

---

#### TS-R03 — Severity evaluator silently defaults missing facts to `0`

| | |
|---|---|
| **Status** | Confirmed Defect (by inspection) |
| **Severity** | **Medium** |
| **Category** | Risk / Deterministic Logic / Product Invariant |
| **Release-blocking** | No |
| **Affected roles** | All users reviewing risk findings |

**Location** — `backend/app/modules/risk/severity.py:41-45`

**Evidence** The evaluator looks up referenced facts in the context and returns `0` when absent:

```python
if isinstance(node, ast.Name):
    if node.id in _VALID_SEVERITIES:
        return node.id
    return ctx.get(node.id, 0)  # missing facts default to 0/falsy
```

This means a missing fact (e.g., `rate_percent_per_week` not returned by the classifier) becomes
`0` in comparisons. A rule like `"critical if rate_percent_per_week > 0.5 else medium"` would
incorrectly evaluate to `medium` when the fact is missing, instead of failing closed or defaulting.

**Root cause** The evaluator treats absent facts as falsy/`0` rather than as an error.
`evaluate_severity` catches malformed rules but not missing variables.

**Impact** Severity can be systematically under- or over-rated when the classifier omits a fact or
`OppFacts` does not include a value the rule expects. This undermines the "numbers never come from
the LLM" guarantee because the downstream severity computation silently invents a numeric default.

**Recommended solution** Change `_ev` to raise `KeyError` for missing names, and have
`evaluate_severity` catch it and return the `default` severity while logging a warning. Alternatively,
return a sentinel `None` and propagate it so comparisons short-circuit to the `default`. Document
required facts per pattern and validate the classifier output against them.

**Regression risks** Low — the change only affects the severity of findings produced by rules
referencing missing facts. Existing tests with complete fact sets continue to pass.

**Tests to add** `test_evaluate_severity_missing_fact_returns_default`;
`test_evaluate_severity_missing_fact_logs_warning`.

**Similar locations** `backend/app/modules/risk/classifier.py` builds the `facts` dict;
`backend/app/modules/risk/service.py:_opp_facts` controls which opportunity-level facts are
available.

### 12.3 Updated remediation plan

Add to the P0/P1 remediation lists from §5, §7.4, §8.4, §9.4, §10.3, and §11.3:

- **P0 (release-blocking, new)**
  - None.
- **P1 (pre-release)**
  - **TS-C01**: move all monetary amounts to integer minor units (paise); update
    `Finding.amount_exposure`, `FindingRow.amount_exposure`, `FactTable`, the BOQ engine, and
    standards threshold/extraction.
  - **TS-I10**: emit `[pN]` markers for XLSX/CSV sheets or teach `doc_text.py`,
    `segment_clauses`, and `extract_deadlines` to treat `[sheet:<name>]` as a page boundary.
  - **TS-A17**: order `WorkspaceMember` by `created_at` (or add `is_primary`) in `login()` and
    surface workspace selection for multi-workspace users.
  - **TS-R03**: fail closed in `evaluate_severity` when a referenced fact is missing instead of
    defaulting to `0`.

### 12.4 Updated final recommendation

**NO-GO** for public launch and for any deployment holding more than one customer's data.

The seventh round re-confirmed every prior release blocker and identified four additional gaps.
There are now **61 findings** (5 Critical, 15 High, 37 Medium, 4 Low) with **18 release-blocking**
items. The new gaps are product-invariant violations (money representation, provenance,
deterministic severity) and an auth workspace-selection issue; they do not add new release blockers,
but they should be fixed and verified before launch.
