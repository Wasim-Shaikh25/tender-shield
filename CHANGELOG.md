# Changelog

All notable changes to TenderShield. Updated **every session** with what was
done and what comes next (see `CLAUDE.md` §1.5). Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); task IDs reference `tasks/backlog.md`.

## [Unreleased]

### Done — 2026-07-29 (PR consolidation)

- Merged the two older audit-only branches (`devin/fourth-round-audit` and
  `claude/production-readiness-audit-ts130-1753815240`) into the consolidated
  branch using `merge -s ours` so their history is preserved but the current
  report/fixes remain authoritative.
- Closed PR #20 and PR #19 as superseded by PR #21.
- Renamed PR #21 to reflect it is the consolidated production-readiness audit + fixes PR.

### Done — 2026-07-29 (TS-097 follow-up: PostgreSQL RLS regressions + migration drift)

- `bind_workspace_context` now inlines the validated UUID string because `SET LOCAL`
  does not accept SQLAlchemy bind parameters.
- `rls_statements` uses `nullif(current_setting('app.workspace_id', true), '')::uuid`
  so an unset GUC evaluates to NULL (fail-closed) instead of raising an empty-string
  UUID cast error.
- Rewrote `tests/test_rls_postgres.py` as a self-contained PostgreSQL-only suite that
  creates/drops its own RLS sample table, backfills rows, and asserts cross-tenant
  read/write blocking and owner-level `FORCE` enforcement.
- Added `migrations/versions/3e8f87662b2f_*.py` to backfill `Invitation.token -> token_hash`
  and add `users.mfa_totp_pending_secret`, fixing the `alembic upgrade head` drift
  reported by the testing agent.
- Added `psycopg[binary]` to `dev` extras and updated the `rls-postgres` CI job to
  create a non-superuser `app`/`app_db` so `FORCE ROW LEVEL SECURITY` is actually tested.

### Done — 2026-07-29 (TS-163: account-centric auth re-architecture backend)

- `User` model now stores `org_name`, `city`, `dob`, `phone`, `mobile_verified`;
  `phone` and `password_hash` are non-nullable; OIDC columns (`google_sub`, `apple_id`)
  removed.
- Added `MobileVerification` table and Alembic migration `6cffa6139050`.
- `POST /api/auth/signup` now creates an account only (no default workspace) with
  org/firm name, email, mobile, city, DOB, password, and confirm-password fields;
  enforces password complexity; returns email and mobile verification tokens.
- `POST /api/auth/verify-email` and `POST /api/auth/verify-mobile` activate the account.
- `POST /api/auth/login` always issues an OTP challenge; tokens are only returned after
  the `/api/auth/mfa/challenge` step.
- Removed Google and Apple OIDC routes and service methods.
- Added `/api/auth/settings`, `/api/auth/settings/password`, and updated `/api/auth/me`.
- JWT claims and `Principal` now include `mobile_verified`; gated endpoints require both
  email and mobile verified (or superadmin).
- Added `tests/helpers.py` and updated all test suites for the new OTP-on-login flow.
- Backend: 146 tests passed, ruff clean.

### Done — 2026-07-30 (TS-163 follow-up: migration fixes)

- `e26e85245237` RLS policy loop now skips tables that do not yet exist, so a later
  migration can create and then secure `award_documents`.
- `5a5548916ff0` now applies workspace-isolation RLS immediately after creating the
  `award_documents` table.
- `6cffa6139050` uses `batch_alter_table` and backfills existing rows, making the
  `phone`/`password_hash` NOT NULL change and OIDC column drop safe on both PostgreSQL
  and SQLite.
- Verified `alembic upgrade head` and `alembic downgrade base` on SQLite.

### Done — 2026-07-30 (TS-163 re-analysis: account-first auth flow hardening)

- Re-analyzed open TODOs against the new account-centric auth flow; the auth-related
  open items (TS-103, TS-106, TS-107, TS-135, TS-161, TS-163 frontend) are now driven
  by account → workspace selection after login.
- `AuthService.login` now always issues an account-level `mfa_token` with no workspace
  selected; `mfa_challenge` returns an account-level access token.
- `AuthService.refresh` preserves the workspace bound to the refresh-token row instead
  of picking an arbitrary workspace; `refresh_tokens.workspace_id` column added.
- `bind_workspace_context` now also sets `app.user_id`; membership-table RLS policies
  (`workspace_members`, `project_members`) allow a user to read/write their own rows
  even in an account-level session, so `/api/auth/workspaces` create/list and switch work.
- `rls_statements` supports an optional `user_id_column` for membership tables.
- Updated `specs/modules/auth.md` (B2, B3, A25).
- Frontend updated for the new flow: `login/page.tsx` has account-only signup with
  org/firm name, email, mobile, city, DOB, password + confirm, email/mobile
  verification, OTP login, and workspace creation; `session.tsx` drives workspace
  selection; `api.ts` and `admin/page.tsx` align with backend response shapes.

### Next

- TS-103 — regenerate the TypeScript API client from the updated OpenAPI schema and
  remove hand-rolled API response mismatches.
- TS-106 — Team-management UI (invite/list/role/remove) and invitation revocation API.
- TS-107 — Account & security settings UI.
- TS-108 — Observability (metrics, health probes, backup/rollback docs).
- TS-109 — Enforce plan seat limits in `add_workspace_member` / `accept_invitation`.
- TS-133..TS-162 — remaining medium/low audit follow-ups.

### Done — 2026-07-29 (TS-132: 61-finding implementation tracker)

- Generated `tasks/audit_fix_tracker.md` mapping every `TS-*` finding to its requirement,
  recommended solution, and task ID.
- Added 30 implementation task rows (TS-133..TS-162) to `tasks/backlog.md` for findings
  that did not already have a fix task.
- Added `scripts/build_audit_tracker.py` to regenerate the tracker from
  `PRODUCTION_READINESS_AUDIT.md`.

### Done — 2026-07-29 (TS-096: Google OIDC role fix)

- `AuthService.google_login` now issues tokens with the user's actual workspace role
  (queried from `WorkspaceMember`) instead of the hardcoded `"owner"` literal.
- Added `specs/modules/auth.md` acceptance criterion A13 covering OIDC role binding.

### Done — 2026-07-29 (TS-095: workspace-scoped member addition)

- `POST /api/auth/workspaces/{workspace_id}/members` now verifies the caller's
  `principal.workspace_id` matches `{workspace_id}` (super-admins bypass), preventing
  any admin of one workspace from joining or adding members to another workspace.
- Added `specs/modules/auth.md` acceptance criterion A14 covering workspace binding.

### Done — 2026-07-29 (TS-123: resend-verification no longer leaks token)

- `POST /api/auth/resend-verification` now returns `{"status": "ok"}` and no longer
  echoes the raw verification token.
- Updated `tests/test_auth_module.py` `_login` helper to mark test users verified
  directly in the DB since the route no longer exposes the token.
- Added `specs/modules/auth.md` acceptance criterion A15.

### Done — 2026-07-29 (TS-122: switch_workspace persists rotated refresh token)

- `AuthService.switch_workspace` now commits after issuing the rotated refresh
  token, so the new `RefreshToken` row and the `used_at` mark on the old row are
  persisted.
- Added `specs/modules/auth.md` acceptance criterion A16.

### Done — 2026-07-29 (TS-100: Google account linking on existing email)

- `AuthService.google_login` now looks up an existing user by verified email and
  links the `google_sub` instead of crashing with an `IntegrityError`/500.
- Added `email_not_verified` error mapping and `specs/modules/auth.md` A17.

### Done — 2026-07-29 (TS-099: cross-tenant member list isolation)

- `list_workspace_members` and `list_project_members` now require the caller to
  be a member of the target workspace (or super-admin) before returning emails/roles.
- Added `specs/modules/auth.md` acceptance criterion A18.

### Done — 2026-07-29 (TS-124: Dockerfile runtime extras)

- `backend/Dockerfile` now installs all runtime extras (`storage`, `redis`,
  `celery`, `billing`, `scheduler`, `ocr`, `auth`) plus `uvicorn`, instead of
  only `dev`/`storage`/`redis`.
- Created `specs/deployment.md` covering production image requirements.

### Done — 2026-07-29 (TS-129: invitation project_id verification)

- `create_invitation` now rejects a `project_id` that does not belong to the
  invitation's workspace.
- `accept_invitation` also verifies project/workspace consistency before adding
  a `ProjectMember`.
- Added `specs/modules/auth.md` acceptance criterion A19.

### Done — 2026-07-29 (TS-098: server-owned billing prices + webhook validation)

- `POST /api/billing/checkout` no longer trusts the client `amount_minor`; it
  uses the server price table in `plans.py` and rejects mismatches.
- `process_razorpay_webhook` and `process_stripe_webhook` validate the paid
  amount against the server price table before activating a plan or crediting
  a paygo review.
- Added `SUBSCRIPTION_PRICES` currency/plan table and `PAYGO_PRICE_INR_PAISE`.
- Added `specs/modules/billing.md` B11 and A5.

### Done — 2026-07-29 (TS-136 / TS-149: valid Anthropic model identifiers)

- Replaced the invalid `claude-sonnet-5` default with `claude-3-5-sonnet-20241022`
  in both `AnthropicClassifier` and `AnthropicAgent`.
- Added `specs/modules/risk.md` A6 and `specs/modules/assistant.md` A3.

### Done — 2026-07-29 (TS-162: severity evaluator missing-fact safety)

- `severity.evaluate_severity` now raises on missing facts instead of silently
  defaulting to `0`/`False`; the top-level `try/except` falls back to the safe
  `default` severity.
- Updated `tests/test_risk.py` to expect fallback behavior.
- Added `specs/modules/risk.md` A7.

### Done — 2026-07-29 (TS-104: rate limiting hardening)

- `RedisRateLimitStorage` now uses wall-clock `time.time()` scores (comparable
  across workers), atomic add-only-under-limit Lua scripts, and unique members
  per attempt.
- `RateLimitDep` prefers the rightmost `X-Forwarded-For` entry and falls back to
  the transport peer.
- Added `specs/modules/core.md` B7/A10.

### Done — 2026-07-29 (TS-105: webhook atomicity)

- `process_razorpay_webhook` and `process_stripe_webhook` now claim the
  `WebhookEvent` idempotency marker via a savepoint, apply the billing effect
  with `commit=False`, and commit everything in one transaction.
- `WorkspaceAdmin.set_plan` and `BillingService` helpers accept `commit=False` for
  callers that manage the transaction boundary.
- Added `specs/modules/billing.md` B12/A6.

### Done — 2026-07-29 (TS-126: hash invitation tokens at rest)

- `Invitation.token` renamed to `token_hash`; raw tokens are generated with
  `secrets.token_urlsafe` and stored as SHA-256.
- `accept_invitation` hashes the supplied token before lookup.
- Added `specs/modules/auth.md` B17/A20.

### Done — 2026-07-29 (TS-127: verify TOTP before completing enrollment)

- Added `User.mfa_totp_pending_secret` and changed `mfa_method` default to empty.
- `mfa_enroll` for TOTP stores the secret pending and returns the provisioning URI.
- `mfa_verify` confirms the first TOTP code, then commits `mfa_method="totp"` and
  moves the secret to `mfa_totp_secret`.
- Added `specs/modules/auth.md` B8/A21.

### Done — 2026-07-29 (TS-101 / TS-102: upload size cap + SSE hardening)

- `POST /api/ingestion/opportunities/{id}/upload` now reads at most
  `MAX_UPLOAD_SIZES[suffix] + 1` bytes and returns 413 before buffering the full
  oversized file.
- SSE document-processing stream now uses an async generator with `await`
  disconnect checks, `asyncio.sleep(0.5)` polling, and a 600-second hard timeout.
- Updated `specs/modules/ingestion.md` B7, B11, A4, A7.

### Done — 2026-07-29 (TS-094: end-to-end production readiness audit)

- **TS-094** — Full end-to-end production readiness audit of trunk
  (`claude/dev-workflow-modules-58dpqw`, commit `d651d00`). **Audit only — no source
  files were changed.** `PRODUCTION_READINESS_AUDIT.md` was rewritten and now supersedes
  the previous report, whose `F26`–`F41` findings are retired (four no longer reproduce:
  `.env.*` templates exist, tus `PATCH` and the SSE endpoint are authenticated, and S3
  calls no longer block the event loop).
  - **Recommendation: NO-GO** — 24 findings (4 Critical, 7 High, 9 Medium, 4 Low),
    9 release-blocking.
  - **Four exploits reproduced end-to-end** against the running app via `TestClient`:
    - Any verified user can add themselves as `owner` to **any** workspace by UUID —
      `add_workspace_member` applies the caller's own token role to a path-supplied
      workspace with no membership check (full cross-tenant takeover).
    - `POST /api/auth/google` mints `role="owner"` for every user because the role is a
      hardcoded string literal; a `viewer` was escalated to `owner`.
    - `GET /auth/workspaces/{id}/members` and `GET /auth/projects/{id}/members` return
      foreign tenants' member emails and roles.
    - Google sign-in with an email that already has a password account raises an
      unhandled `IntegrityError` (HTTP 500) — no account linking.
  - **Row-level security is structurally inoperative**: `ENABLE` without `FORCE` (the app
    role owns the tables, so policies are bypassed), `USING` without `WITH CHECK`,
    `current_setting()` without the missing-OK argument, and `workspace_members` /
    `project_members` carry no policy at all. Not verified against PostgreSQL — none was
    available — and no test in the suite exercises RLS, since all 145 tests run on SQLite.
  - **Billing accepts a client-supplied price**: `checkout.amount_minor` flows to the
    provider unchecked, and the webhook activates a plan without ever comparing the amount
    paid to the plan price — a ₹1 payment activates the ₹14,999/month plan with a
    genuinely valid signature. Plan seat limits are defined but never read anywhere.
  - Also confirmed: unbounded in-memory upload buffering before the size check; an SSE
    progress loop that busy-spins a threadpool worker with no sleep, disconnect check, or
    timeout; a Redis rate limiter keyed on `time.monotonic()` (meaningless across
    processes) with no proxy-header handling; non-atomic, racy webhook idempotency; and a
    `/auth/workspaces` response shape the frontend client cannot consume.
  - **Verified as working** (reported as defenses, not assumptions): path traversal in
    `/api/files` blocked across three variants; workspace switching correctly enforces
    membership; no real secrets in any committed `.env.*` file; SQL injection surface clean;
    the three artifact validators genuinely enforce the no-invented-quotes/clauses/numbers
    invariants; domain services filter on `workspace_id` consistently.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities.
  - Product gaps identified: no team-management UI, no account/security settings UI, no
    member removal or invitation revocation, no data export/deletion, and an audit log
    covering only finding decisions.

### Done — 2026-07-29 (TS-121: second-round production readiness audit)

- **TS-121** — Second-round end-to-end re-audit of trunk (`d651d00`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - Re-verification that all first-round `TS-*` findings still reproduce.
  - Six new findings: `TS-A06` (workspace switch refresh token not committed),
    `TS-A07` (`resend-verification` leaks raw token), `TS-O04` (Dockerfile missing
    runtime extras), `TS-A08` (invitation token stored plaintext), `TS-A09` (TOTP
    enrollment lacks verification), and `TS-P02` (rulepacks still unvalidated; paying
    workspaces receive zero findings).
  - Updated counts: **30 findings (5 Critical, 10 High, 11 Medium, 4 Low), 13 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-130: fifth-round production readiness audit rerun)

- **TS-130** — Fifth-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Eight new findings: `TS-N02` (notifications scheduler calls missing `WorkspaceAdmin` method),
    `TS-I08` (async `process_document` does not classify/segment or use OCR),
    `TS-I07` (`register_document` accepts unbounded `sample_text` with synchronous processing),
    `TS-R02` (risk classifier default Anthropic model name is invalid),
    `TS-A14` (assistant agent default Anthropic model name is invalid),
    `TS-A15` (`review` audit trail ignores `opportunity_id` and `AuditLog` lacks the column),
    `TS-B06` (`Artifact.version` read-modify-write race), and
    `TS-D03` (timeline ICS export appends `Z` to naive/local datetimes).
  - Updated counts: **51 findings (5 Critical, 15 High, 27 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-131: sixth-round production readiness audit rerun)

- **TS-131** — Sixth-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Six new findings: `TS-S04` (`LocalStorage` async methods run synchronous file I/O),
    `TS-O05` (production guard allows a comma-separated wildcard in `CORS`/`allowed_hosts`),
    `TS-B07` (Stripe checkout hardcodes `example.com` redirect URLs),
    `TS-B08` (Stripe webhook verifier swallows all exceptions),
    `TS-I09` (tus endpoints perform synchronous file I/O and `OPTIONS` is non-compliant),
    and `TS-A16` (`review_finding` does not scope by `opportunity_id`).
  - Updated counts: **57 findings (5 Critical, 15 High, 33 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Done — 2026-07-29 (TS-132: seventh-round production readiness audit rerun)

- **TS-132** — Seventh-round end-to-end re-audit of trunk (`claude/dev-workflow-modules-58dpqw`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`. **Audit only — no source files were changed.**
  `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - Four new findings: `TS-C01` (monetary amounts represented as `float` / `Numeric(16,2)` major units),
    `TS-I10` (XLSX/CSV ingestion loses page provenance), `TS-A17` (email/password login selects an
    arbitrary workspace for multi-workspace users), and `TS-R03` (severity evaluator silently defaults
    missing facts to `0`).
  - Updated counts: **61 findings (5 Critical, 15 High, 37 Medium, 4 Low), 18 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Next

Fix in order — the four blockers first (`TS-095` cross-workspace member add, `TS-096`
Google role escalation, `TS-098` billing price validation, then `TS-097` RLS, which
carries the highest regression risk and needs PostgreSQL in CI plus a staging soak).
Then the High findings `TS-099`–`TS-105`, and the launch-required product gaps `TS-106`
(team management) and `TS-107` (account settings). The second-round audit adds the
following to the launch-critical list: `TS-122` (workspace switch refresh persistence),
`TS-123` (resend-verification token leak), `TS-124` (Dockerfile runtime extras), `TS-125`
(rulepack validation / beta flag), `TS-126` (hash invitation tokens), and `TS-127` (TOTP
verification before enrollment). Every fix needs a regression test; `TS-097` cannot be
marked done until RLS is verified against a real PostgreSQL instance using a non-owner
application role. Six product questions (§3.6 of the report) need answers before `TS-097`,
`TS-100`, `TS-098`, `TS-109`, and `TS-111` can be finalised.

### Done — 2026-07-29 (older requirements completed: TS-033..TS-037, TS-043..TS-045, TS-079)

- **TS-033** — Minimal tus 1.0 resumable upload server at `/api/ingestion/tus`:
  creation (`POST /`), chunked upload (`PATCH /{id}`), and offset query (`HEAD /{id}`).
  Completed uploads are validated, stored, and processed (sync or async via Celery).
- **TS-034** — Celery + Redis async page-streamed processing:
  - Added `app.core.celery` with `make_celery_app`; falls back to eager execution when
    `TS_REDIS_URL` is unset.
  - Added `ingestion.tasks.process_document` which loads the stored file, extracts text,
    persists `doc_chunks`, and extracts deadlines while publishing `PROGRESS` state.
  - Added SSE stream endpoint `/api/ingestion/opportunities/{id}/documents/{id}/stream?task_id=...`.
  - `POST /api/ingestion/opportunities/{id}/upload?async=1` stores the file, creates a
    pending document, and enqueues processing.
- **TS-035 / TS-079** — Real email/SMS sender adapters for MFA and OTP:
  - `Msg91Sender` and `SesSender` are already in `notifications.adapters` and degrade to
    console logging without credentials.
  - `AuthService` now sends `email`/`sms` one-time codes during login/MFA enrolment using
    the configured `notifications.sender`.
- **TS-036** — Google OIDC login and phone OTP:
  - Added `POST /api/auth/google` with `google.auth` verification against Google's JWKS.
  - New `GoogleClient` in `app.modules.auth.google` and `google_*` settings in `app.core.config`.
  - Phone OTP is supported through `mfa_enroll` with `method=sms` and the MSG91 sender.
- **TS-037** — Live Razorpay + Stripe provider integration:
  - `RazorpayProvider` and `StripeProvider` create real orders/sessions when keys are set;
  otherwise deterministic mock handles are returned.
  - Added `POST /api/billing/webhooks/stripe` with signature verification and idempotent
    `checkout.session.completed` processing (records usage, creates invoices, sets plan).
  - Added `stripe_webhook_secret` to `Settings`.
- **TS-043** — Deadline-countdown alerts driven by the notice register:
  - `notifications.module` registers a daily scheduler job that scans every workspace for
    unconfirmed deadlines within the next 7 days and emails workspace members.
  - `WorkspaceAdmin.list_members` added to support recipient lookup.
- **TS-044** — Award-document ingestion for award baseline:
  - Added `AwardDocument` model + migration and `POST /api/baseline/opportunities/{id}/award-document`.
  - `BaselineService.freeze(source="award")` now pulls from the latest award letter text and
    includes an `award_text_preview` in the snapshot.
- **TS-045** — Handover-pack file export (DOCX/PDF/XLSX):
  - Added `render_handover_pack` to `export/render.py`.
  - Added `ExportService.export_handover` and `GET /api/baseline/opportunities/{id}/handover/export?format=...`.
  - Exports include the sealed hash, key obligations, notice register, gaps, and deadlines.

### Done — 2026-07-29 (TS-128: third-round production readiness audit rerun)

- **TS-128** — Third-round end-to-end re-audit of trunk (`d651d00`) per
  `END_TO_END_PRODUCTION_AUDIT_PROMPT.md`, run from scratch on a fresh branch.
  **Audit only — no source files were changed.** `PRODUCTION_READINESS_AUDIT.md` updated with:
  - All prior `TS-*` findings re-verified and still present.
  - One new finding: `TS-A10` (`create_invitation` / `accept_invitation` accepts an
    arbitrary `project_id` and adds the invitee as a member of a project in a foreign
    workspace, granting cross-tenant project read access).
  - Updated counts: **31 findings (5 Critical, 11 High, 11 Medium, 4 Low), 14 release-blocking**.
  - Updated remediation plan and final recommendation remains **NO-GO**.
  - Baseline recorded: `ruff` clean, `mypy` clean (143 files), 145 backend tests passing,
    frontend lint/typecheck/build clean, `npm audit` 0 vulnerabilities, `pip-audit` 0.

### Next

- Add `TS-129` to the launch-critical fix list: `create_invitation` and
  `accept_invitation` must verify that `project_id` belongs to the invitation's
  workspace before persisting the `ProjectMember` row.
- Fix in order — the four blockers first (`TS-095` cross-workspace member add, `TS-096`
  Google role escalation, `TS-098` billing price validation, then `TS-097` RLS), followed
  by High findings `TS-099`–`TS-105` and `TS-A10` (TS-129), and the launch-required
  product gaps `TS-106` (team management) and `TS-107` (account settings).

### Done — 2026-07-29 (production readiness audit fixes: TS-083..TS-084)

- **TS-083** — Production security hardening:
  - `Settings` now uses `SecretStr` for all secrets and adds `TS_ENV`, `TS_ALLOWED_HOSTS`,
    `TS_CORS_ORIGINS` enforcement, `TS_STORAGE_TYPE`/`s3_*`, and `TS_REDIS_URL`.
  - `create_app` validates production settings: no default Razorpay webhook secret,
    explicit CORS/allowed-hosts, and configured JWT keys.
  - Added security headers middleware (CSP, HSTS in prod, X-Frame-Options, etc.).
  - Added `HTTPSRedirectMiddleware` and `TrustedHostMiddleware` in production.
  - Split health endpoint: `GET /api/health` is public and minimal; `GET /api/health/details`
    exposes module/capability metadata and is gated by auth (super-admin in production,
    authenticated in non-production, public when auth is disabled).
  - Updated affected tests to use `/api/health/details`.
- **TS-084** — Auth session/MFA hardening:
  - Refresh tokens are now returned as `httpOnly`, `Secure` (prod), `SameSite=Lax`
    cookies named `refresh_token`; `/api/auth/refresh` and `/logout` read them from
    cookies. The JSON response no longer contains `refresh_token`.
  - Added `/api/auth/mfa/challenge`; when `User.mfa_totp_secret` is set, `/login` returns
    `mfa_required` and a short-lived `mfa_token` instead of final tokens.
  - Added `/api/auth/workspaces/{id}/switch` to rotate refresh and reissue access for the
    selected workspace.
  - Added password policy: ≥8 chars, uppercase, lowercase, digit, symbol, and a blocklist
    of trivial passwords.
  - Added account lockout: 5 failed login attempts within 15 minutes lock the account for
    15 minutes, stored in new `users.failed_login_attempts` and `users.locked_until` columns.
  - Migration `64f9e4b70eda` adds the lockout columns.
  - Updated test suite to use strong passwords and cookie-based refresh flow.

### Done — 2026-07-29 (production readiness audit fixes: TS-086..TS-087)

- **TS-086** — File upload/storage hardening:
  - Added `app.core.storage` with MIME/magic/size validation, extension blocklist,
    and per-file-type limits. BOQ uploads are capped at 10 MB.
  - Added `LocalStorage` (default dev) and `S3Storage` (credential-gated) adapters;
    `TS_STORAGE_TYPE=s3` activates S3 with fallback to local on failure.
  - Added stub virus-scan hook (`_scan_stub`) so a real scanner/ClamAV integration can
    be swapped in later.
  - Wired `validate_and_store` into `ingestion` and `boq` upload routes.
- **TS-087** — Risk/export quality:
  - `RiskService.run_opportunity` now passes `validated_only=True` to rule-packs when
    the workspace is on a paid plan (`pro`, `enterprise`, `paygo`, `team`).
  - `ExportService.export` pulls the last reviewer from the audit log and includes
    `reviewed_by_email` and `reviewed_at` in the pack stamp.
  - Added tamper-evident SHA-256 integrity hash to the export stamp.
  - Replaced `datetime.utcnow()` in `comparison/service.py` with timezone-safe logic.

### Done — 2026-07-29 (production readiness audit fixes: TS-089..TS-090)

- **TS-089** — Deployment/DevEx:
  - Added `.env.local`, `.env.dev`, and `.env.prod` templates covering all `TS_*`
    settings (database, CORS, allowed hosts, auth keys, storage/S3, billing, Redis, OCR/LLM).
  - Updated `.env.example` to match the new settings.
  - `docker-compose.yml` now uses `.env.local`, mounts `backend_storage`, and sets
    `TS_STORAGE_DIR` to `/app/storage`.
  - `backend/Dockerfile` installs `storage` + `redis` extras.
- **TS-090** — CI/tooling:
  - Backend CI now runs `ruff`, `mypy`, `pip-audit`, `pytest`, and Alembic up/down checks.
  - Frontend CI now runs `npm run lint`, `npm run typecheck`, `npm audit`, and `npm run build`.
  - Added `mypy` config to `pyproject.toml` (permissive baseline to avoid existing noise).
  - Added ESLint config and `lint` / `typecheck` scripts to `frontend/package.json`.
  - Resolved `postcss`/`sharp`/`brace-expansion` npm audit warnings via `overrides`.

### Done — 2026-07-29 (production readiness audit fixes: TS-091)

- **TS-091** — Notification/payment adapter skeletons:
  - Added `app.modules.notifications.adapters` with `SesSender` and `Msg91Sender`
    that fall back to console logging when credentials are absent.
  - Added `app.modules.billing.providers` with `RazorpayProvider` and `StripeProvider`
    that return mock handles without live keys.
  - Added `app.core.scheduler` (APScheduler optional) and wired it into `create_app`
    lifespan; `notifications` registers a daily digest stub job.
  - Added provider/notification settings to `app.core.config`.
  - Added `billing` and `scheduler` optional extras to `pyproject.toml`.

### Done — 2026-07-29 (production readiness audit fixes: TS-085, TS-088, TS-092)

- **TS-085** — Workspace switcher:
  - `SessionProvider` now fetches `/auth/workspaces` and exposes `switchWorkspace`.
  - Header includes a workspace dropdown when the user belongs to multiple workspaces.
- **TS-088** — Frontend cleanup:
  - Removed hardcoded `SAMPLE` tender and `SAMPLE_BOQ` from the opportunity workbench.
  - Replaced the sample tender button with a real file upload (`<input type="file">`) wired to
    `/ingestion/opportunities/{id}/upload`.
  - Replaced the sample BOQ button with a CSV textarea.
  - Removed the unverified "Hosted in India" claim from the landing page.
  - Added `/billing` page (plan/usage, invoices, checkout) and `/admin` link.
  - `api.ts` now sends `credentials: "include"` so httpOnly cookies travel with every request.
- **TS-092** — Admin console and analytics UI:
  - Added `/admin` superadmin page listing users and workspaces, with a superadmin toggle.
  - Added per-opportunity **Audit** tab on the workbench using `/review/opportunities/{id}/audit`.
  - Added `/analytics` dashboard showing opportunity risk counts, BOQ defects, and export readiness.

### Done — 2026-07-29 (production readiness audit quick wins: TS-093)

- **TS-093** — Implemented quick-win fixes from `PRODUCTION_READINESS_AUDIT.md` F26–F42:
  - Added `.env.local`, `.env.dev`, and `.env.prod` templates with no secrets and updated `.gitignore`.
  - Aligned frontend upload `accept` list with backend MIME/extension allow-list.
  - Made billing checkout currency-aware by `Workspace.country` (`IN` → `inr`, `AE`/`SA`/`QA`/`GB` → local currencies) and defaulted to `IN`.
  - Protected `GET /api/rulepacks` and `/api/rulepacks/{id}/patterns` with `require("viewer")`.
  - Authenticated the Celery SSE stream endpoint (`/api/ingestion/opportunities/{id}/documents/{id}/stream`) and scoped the document lookup.
  - Added `GET /api/files/{key:path}` download route enforcing workspace prefix isolation.
  - Made S3 initialization raise `StorageError` in production instead of silently falling back to local storage.
  - Added a Redis distributed lock around the deadline-alert scheduler tick (`notifications.module`).
  - Added email verification flow: `EmailVerification` model + migration, `POST /api/auth/verify-email`, `POST /api/auth/resend-verification`, `email_verified` claim in access/MFA tokens, and gated billing checkout + member invitations on `email_verified` (or super-admin).
  - Hardened tus `PATCH`/`HEAD` with auth, workspace scoping, and per-extension upload-size caps; enabled virus-scan stub path for BOQ uploads.
  - Moved S3 `put_object`/`get_object`/`delete_object`/`generate_presigned_url` calls to `asyncio.to_thread` to avoid blocking the event loop.
  - Added migration `df4721874c4d_add_email_verifications`.

### Next

- TS-094 — Replace `StorageError` in production with a real ClamAV/cloud virus-scan hook.
- TS-095 — End-to-end browser validation of signup, email verification, file upload, and payment flows.
- TS-096 — Rulepack validation by a QS/contracts expert against real tender sets (F27 remains open).

### Done — 2026-07-26 (real web validation + invitation fix: TS-080..TS-081)

- **TS-080** — Ran end-to-end browser validation against the local frontend + backend:
  - UI signup (`http://localhost:3000/login`) created a user, default workspace, and
    navigated to `/opportunities`.
  - Real `fetch` calls from the browser verified workspace CRUD, project CRUD,
    project-member listing, and super-admin 403 rejection.
- **TS-081** — Fixed `POST /api/auth/invitations/{token}/accept` raising
  `TypeError: can't compare offset-naive and offset-aware datetimes` on SQLite.
  `accept_invitation` now normalizes a naive `expires_at` to UTC before comparing.
  Added `test_invitation_flow` to `tests/test_auth_module.py`.

### Done — 2026-07-26 (password reset: TS-082)

- **TS-082** — Added forgot-password and reset-password flow:
  - New `password_resets` table with 15-minute single-use tokens stored as SHA-256 hashes.
  - `POST /api/auth/forgot-password` returns `ok` even for unknown emails to prevent
    enumeration; returns the raw token in dev/test until real email delivery is wired.
  - `POST /api/auth/reset-password` validates the token, enforces an 8-character minimum,
    hashes the new password with argon2id, and marks the token used.
  - Frontend: `/forgot-password` and `/reset-password?token=...` pages, plus a link
    from `/login`.
  - Added regression tests for reset, reuse, and expired-token rejection.

### Done — 2026-07-26 (workspace/project tenant refactor + super admin: TS-074..TS-078)

- **TS-074** — Spec for the workspace/project tenant refactor + super admin:
  `specs/workspace-and-admin-refactor.md`.
- **TS-075** — New auth data model: removed `org`/`org_members`, added `User`,
  `Workspace`/`WorkspaceMember`, `Project`/`ProjectMember`, `Invitation`, global
  `is_superadmin` flag, and `mfa_method`/`mfa_phone` on `User`.
- **TS-076** — Renamed `org_id` → `workspace_id` across all modules, RLS helpers,
  and `core.db`; regenerated the migration chain as
  `migrations/versions/e26e85245237_workspace_tenant.py` with workspace-scoped
  RLS policies for PostgreSQL.
- **TS-077** — Workspace/project CRUD, sharing/invites, MFA method selection, and
  super-admin endpoints:
  - `POST/GET /api/auth/workspaces`
  - `POST/GET /api/auth/workspaces/{id}/members`
  - `POST/GET /api/auth/workspaces/{id}/projects`
  - `POST/GET /api/auth/projects/{id}/members`
  - `POST /api/auth/invitations` + `POST /api/auth/invitations/{token}/accept`
  - `POST /api/auth/mfa/enroll` + `POST /api/auth/mfa/verify`
  - `GET/POST /api/auth/admin/*` super-admin routes.
- **TS-078** — Updated `tests/test_auth_module.py` and frontend `api.ts` / `session.tsx`
  / `app/login/page.tsx` for `workspace_id`; verified `ruff`, `pytest`, `npm run build`,
  and `alembic upgrade head && downgrade base` all pass.
- Updated `README.md`, `docs/deployment.md`, `specs/modules/auth.md`, and
  `tasks/backlog.md` to reflect the new workspace/super-admin model.

### Done — 2026-07-26 (spec audit follow-up: Sprints 0–2)

- **TS-058..TS-070** — Spec-audit follow-up task IDs and `tasks/spec_audit_tracker.md` created.
- **TS-062** — `analytics` and `comparison` now publish `*.service_factory` capabilities
  via `module.py`, and their routers consume the factory when available.
- **TS-063** — Fixed route wording in `specs/modules/timeline.md` and `specs/modules/crossref.md`
  to match the implemented router paths.
- **TS-058..TS-061** — Added missing module specs:
  - `specs/modules/findings.md` (shared findings store and contract).
  - `specs/modules/export.md` (Bid Review Pack export with review gate).
  - `specs/modules/health.md` (health/capabilities endpoint).
  - `specs/modules/notifications.md` (deadline-digest sender abstraction).
- **TS-059 (code)** — `export` now publishes `export.service_factory` and the router
  consumes it, matching the pluggable pattern.
- **TS-064..TS-066** — Aligned `ingestion`, `risk`, and `drafting` public-interface
  specs with the capabilities and routes actually implemented.
- **TS-067** — Added tests for `export`, `health`, and `notifications`:
  - `test_export.py` covers review-gated XLSX export and bad-format handling.
  - `test_health.py` covers the `/api/health` module/capability report.
  - `test_notifications.py` covers deadline alert thresholds and `ConsoleSender`.

### Done — 2026-07-26 (Sprint 4 complete + TS-071)

- **TS-068** — Implemented `ingestion.doc_chunks` table + migration and the
  `ingestion.doc_text` capability (`DocTextService`), plus `GET /api/ingestion/documents/{id}/text`.
- **TS-070** — Added `invoices` table + migration, `GET /api/billing/invoices`, and the
  `billing.record_usage` capability; Razorpay `order.paid`/`subscription.charged` now generate a paid invoice.
- **TS-069** — Implemented assistant chat sessions (`chat_sessions` + `chat_messages`),
  history endpoints, and SSE `/api/assistant/sessions/{id}/stream`.
- **TS-071** — Implemented Sign in with Apple backend skeleton: `users.apple_id`,
  `GET /api/auth/apple/authorize`, `POST /api/auth/apple/callback`, client-secret
  generation, and id_token verification. Disabled until Apple Developer credentials
  are configured (`TS_APPLE_*`).
- Added integration tests for billing, ingestion doc chunks, assistant sessions, and
  Apple sign-in.

### Done — 2026-07-26 (Devin rules: TS-073)

- **TS-073** — Created `.devin/rules/*.mdc` and `DEVIN.md` so Devin follows the same
  mandatory workflow, architecture, and spec conventions as Cursor/Claude. Updated
  `CLAUDE.md` and `.cursor/rules/00-workflow.mdc` to reference the Devin rules.

### Done — 2026-07-26 (deployment helpers: TS-072)

- **TS-072** — Added `.env.local`, `.env.dev`, `.env.prod`, `scripts/run.sh`, and
  `docs/deployment.md` with local / Docker / prod setup instructions.

### Next

- TS-079 — Wire real email/SMS delivery for `email`/`sms` MFA methods, OTP codes, and
  password-reset links (replace dev-only token return).
- TS-036 — Complete Google OIDC login (`/api/auth/google/callback`) and live
  messaging-provider credentials.
- Configure Apple Developer credentials and test end-to-end Sign in with Apple.

### Done — 2026-07-26 (session 23 continued: TS-057)

- **TS-057** — Internal Accuracy Dashboard:
  - New `analytics` module with `GET /api/analytics/accuracy` (admin/owner only).
  - Aggregates review outcomes from the shared findings table and produces
    per-pattern and per-source precision proxies, false-positive counts, and
    a most-rejected patterns list.
  - Recall and true false negatives are reported as `null` because they require
    an external golden-label set; the shape is ready for that feed.
  - Added `FindingStore.list_for_org` to support org-wide analytics without
    direct table imports.
  - `specs/modules/analytics.md` and `tests/test_analytics.py` added.

### Next

- Phase 1 accuracy gate: validate the Bid Readiness score and weights against a
  real tender set and QS sign-off; no Phase-2 expansion until ≥70% QS acceptance.
- Golden-label import for true precision/recall in `analytics` (TS-057 follow-up).

### Done — 2026-07-26 (session 23 continued: TS-050)

- **TS-050** — Tender Comparison:
  - New `comparison` module with `GET /api/comparison/opportunities` returning a
    portfolio ranking table.
  - Aggregates per-opportunity counts (risk by severity, qualification gaps,
    BOQ defects, standard violations), earliest submission deadline, and the
    latest `bid_decision` score/recommendation from `drafting`.
  - Deterministic priority ranking: `proceed` > `proceed_with_conditions` >
    `do_not_proceed` > none, then bid score desc, critical risk asc,
    days-to-submission asc.
  - `specs/modules/comparison.md` and `tests/test_comparison.py` added.

### Done — 2026-07-26 (session 23 continued: TS-053 + TS-051)

- **TS-053** — Clause Cross-Reference:
  - New `crossref` module with `CrossRefService` and routes
    `GET /api/crossref/opportunities/{id}?q=...&limit=...`.
  - Token-level search across every clause in an opportunity, ranked by overlap,
    with provenance (document kind/filename, clause ref, heading, page, 300-char preview).
  - `specs/modules/crossref.md` and `tests/test_crossref.py` added.

- **TS-051** — Clause Change Detection:
  - `POST /api/crossref/opportunities/{id}/diff?document_id=...` compares two
    versions of a document and returns `added`, `removed`, and `changed` clauses.
  - Uses explicit `supersedes` chains when provided; falls back to the two most
    recent uploads of the same document kind.
  - Clause matching is deterministic: keyed by `clause_ref`, with text similarity
    on normalised clauses.
  - Wired into the ingestion clause store; no hard cross-module imports.

### Done — 2026-07-26 (session 23 continued: TS-048 + TS-049 + TS-052 + TS-054 + TS-055 + TS-056)

- **TS-052** — Tender Timeline:
  - New `timeline` module with `TimelineService` and routes
    `/api/timeline/opportunities/{id}/timeline` and `.ics` export.
  - Expanded `ingestion.deadlines` keywords to extract tender publication,
    technical/financial opening, EMD validity, BG submission, contract signing.
  - Timeline normalizes raw kinds to a canonical milestone vocabulary, includes a
    `tender_published` synthetic fallback, and sorts dated events.
  - `specs/modules/timeline.md` and `tests/test_timeline.py` added.

- **TS-049** — Qualification Compliance Matrix:
  - New `qualification` module with `QualificationService` and routes
    `GET/POST /api/qualification/opportunities/{id}`.
  - Deterministic extraction of 8 eligibility criteria (minimum turnover,
    similar project experience, equipment, engineer, certifications, EMD,
    bid security, experience years) with source quote + page.
  - Writes `qualification_gap` findings to the shared findings store; missing
    criteria are `not_met` (severity `high`), found criteria are `unknown`
    (severity `medium`) pending org evidence.
  - `specs/modules/qualification.md` and `tests/test_qualification.py` added.

- **TS-048** — Bid / No-Bid Recommendation:
  - Extended `drafting` to generate a `bid_decision` artifact from accepted
    findings only.
  - Deterministic score (0–100) with transparent weights over `risk_clause`,
    `qualification_gap`, `boq_defect`, and `standard_violation` findings.
  - Weights default to a documented table and can be overridden through the
    rule-pack playbook (`default_contractor.bid_decision_weights`).
  - Output: score, strengths, concerns, recommendation
    (`proceed` / `proceed_with_conditions` / `do_not_proceed`), and conditions.
  - Gated by review: no `proposed` or `needs_clarification` findings allowed.
  - Updated `specs/modules/drafting.md` and `tests/test_drafting.py`.

- **TS-056** — Organization Standards Enforcement:
  - Extended `standards` with `OrgCommercialStandard` (org-scoped, RLS) for
    per-org policy thresholds.
  - New routes:
    `GET/PUT/DELETE /api/standards/commercial/{key}` and
    `POST /api/standards/opportunities/{id}/check`.
  - `check_violations` extracts numbers from accepted findings (percent, days,
    amount) and returns violations; the endpoint persists `standard_violation`
    findings through the shared findings store.
  - `drafting` `bid_decision` consumes `standards.commercial_service_factory`
    and includes standard violations in score/concerns.
  - Updated `specs/modules/standards.md` and added `tests/test_standards.py`.

- **TS-054** — Risk Explainability:
  - `Finding` contract and `findings` table now carry an `explanation` JSON field.
  - `RiskPattern` schema accepts `industry_reason`; all five `in-works` India
    patterns updated with real, domain-appropriate reasons.
  - `risk.engine.run_pattern` builds an explanation object for every finding
    (`matched_pattern`, `evidence_quote`, `industry_reason`, `suggested_review`,
    `absence` flag).
  - `risk` and `review` API responses now include `explanation`.
  - Tests updated: `test_risk.py` asserts explanation shape.

- **TS-055** — Structured Review Outcomes:
  - `ReviewStatus` expanded: `accepted`, `edited`, `rejected`, `false_positive`,
    `needs_clarification`.
  - `findings` table and contract gain `review_reason`.
  - Review endpoint accepts `decision` + `review_reason`; audit logs both.
  - Export gate now blocks on `proposed` **and** `needs_clarification`.
  - Tests added for `false_positive`/`needs_clarification` and gate behavior.

- Migration `0012_review_explain.py` adds `review_reason` and `explanation`
  columns to `findings`; Alembic up/down verified.
- `specs/modules/risk.md` and `specs/modules/review.md` updated in the same change.
- `tasks/backlog.md` / `tasks/phase15_tracker.md`: TS-052, TS-054, TS-055 marked `done`.

### Done — 2026-07-26 (session 23: Phase 1.5 bid-decision extensions planning)

- Product requirements and roadmap for **Phase 1.5 — Bid-Decision Extensions**
  (`docs/TenderShield_Phase15_Extensions.md`). Maps the 10 requested
  capabilities to the existing modular architecture, defines domain/market
  rationale, priority, sprint sequencing, acceptance criteria, and module mapping.
- Task backlog updated with sequential IDs **TS-048…TS-057** for Bid / No-Bid
  Recommendation, Qualification Matrix, Tender Comparison, Clause Change
  Detection, Tender Timeline, Clause Cross-Reference, Risk Explainability,
  Structured Review Outcomes, Organization Standards Enforcement, and Internal
  Accuracy Dashboard (`tasks/backlog.md`).
- Progress tracker created (`tasks/phase15_tracker.md`) with sprint themes,
  acceptance gates, and blockers; Bid Decision Intelligence is the capstone
  feature with Sprint 0–2 inputs (explainability, review outcomes,
  qualification, timeline, org standards) sequenced first.

### Done — 2026-07-24 (session 22: org-custom standards + researched notice figures)

- **TS-047** — the third standards layer: a firm can publish **its own** notice
  regimes that either **prevail** over or run **side by side** with the
  universal + regional rule-pack standards (Doc §10 custom playbooks).
  - New pluggable `standards` module (backend): `org_notice_standards` table
    (org-scoped + RLS, one row/org), `GET/PUT/DELETE /api/standards/notice`
    (read = viewer, write = admin), boundary validation (bad mode → 400,
    duplicate keys → 409). Publishes `standards.org_notice_provider`.
  - `baseline` now merges three layers — universal → regional → org — when
    building the notice register + gaps. `prevail` overrides matching regimes
    (keeping base fields the org omits); `side_by_side` appends. Org regimes are
    tagged `origin="org"`; an expected org regime absent from a contract becomes
    a gap. Migration `0011`.
  - Frontend: `/standards` editor (mode toggle + editable regime rows), nav link,
    and a "your standard" badge on org-origin gaps in the Handover tab.
- **Researched, cited notice figures** (you asked me to do the QS research):
  the universal/India packs now carry real, sourced windows — **FIDIC 2017
  cl.20.2** (28-day notice / 84-day detailed claim), **NEC4 cl.61.3** (8-week /
  56-day compensation-event bar), **MSMED Act 2006 s.15** (45-day statutory
  payment cap), plus **CPWD cl.10CC** escalation and the hindrance-register EOT
  practice — with a `references.md`. All remain `confidence: unvalidated` pending
  a QS sign-off (Doc §14).
- Verified live (UI): the register shows the MSMED 45-day and CPWD 10CC figures
  from the India overlay, and a firm's own "Site handover" regime flowing through
  as an org-badged gap.
- 113 backend tests passing (7 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 21: layered contract-standards — universal-first, flexible)

- **TS-046** — the flexibility spine the geographic roadmap rides on: **layered
  notice standards** as versioned data (`rulepacks/in-works/notice_standards/`).
  - `base.yaml` (scope `universal`) defines the contract-form-agnostic notice
    regimes (claim, variation, EOT, payment, defect, termination, dispute) with
    typical windows, `expected` flags and keywords; `india.yaml` (scope `IN`) is
    an **overlay** that tightens the claim window (28→15d), retimes EOT to the
    hindrance-register practice, and adds the India-only escalation/star-rate
    regime.
  - `RulePackLoader.notice_standard(pack_id, region)` merges universal + regional:
    a regional category overrides the base **only in the fields it explicitly
    sets** (`exclude_unset`, so an omitted `expected` keeps the base value —
    this was a real bug, fixed), region-only categories append. **Adding a new
    market or an unexpected clause type is now a YAML file, not a code change** —
    the exact seam the future GCC (FIDIC) / UK (NEC/JCT) packs plug into.
  - The `baseline` notice register is now **standards-aware**: each extracted
    window is classified into a semantic category, and every *expected* regime
    with no window in the contract is flagged as a **gap** (the notice analogue
    of risk absence detection) — deterministic, no LLM. Region + gaps are frozen
    into the sealed snapshot and shown in the handover pack. Degrades to
    extraction-only when `rulepacks` is disabled.
  - Frontend Handover tab: "standard: universal + IN" badge, semantic categories,
    and an amber "expected notice regimes not found" panel.
  - Verified live (UI): a claims-only contract correctly flags Variation, EOT
    (hindrance-register, 15d), Payment, Termination and Price-escalation (30d) as
    gaps — the India overlay visibly in effect.
- 108 backend tests passing (3 new), ruff clean, frontend builds clean.

### Done — 2026-07-24 (session 20: Phase-2 baseline lock — end to end)

- **TS-041** — new pluggable `baseline` module (backend), the first Phase-2
  feature. At award it freezes the reviewed commercial state into an immutable,
  hash-sealed snapshot so tender knowledge survives handover (Doc §0.1 P2):
  - **Hash-sealed freeze** — SHA-256 over the canonical snapshot (accepted/edited
    findings with verbatim provenance + confirmed deadlines + opportunity meta).
    Append-only versions; `verify` recomputes the hash and reports tamper
    (the doc's "baseline freeze (hashes)" requirement).
  - **Freeze gate** — sealing is blocked until the `review` gate is satisfied
    (Doc §11.4), reusing the professional-liability spine; refused when `review`
    is disabled.
  - **Deterministic notice-rule register** — regex over the accepted findings
    **and the segmented contract clauses** extracts contractual notice windows
    ("within 14 days", "28 days' notice"), normalised to days, with page
    citations. No LLM (Doc §4) — populates from real contract text even with no
    API key. These seed the Phase-3 time-bar countdowns.
  - **Award-vs-tender delta** — diffs the latest tender seal against the latest
    award seal (added / dropped / changed findings). Deterministic.
  - **Commercial handover pack** — sealed hash, critical/high obligations, notice
    register and confirmed-deadline calendar from the latest baseline.
  - Cross-module only via capabilities (`findings`/`review`/`ingestion`); the app
    boots and Phase-1 flows pass with `baseline` disabled. Migration `0010`,
    org-scoped + RLS on PostgreSQL. 8 new tests (freeze gate, seal, verify,
    compare, handover, live-clause notice extraction).
- **TS-042** — frontend **Handover** tab on the opportunity workbench: freeze
  tender/award baselines (gated on review), sealed-baseline list with hashes,
  notice-rule register with citations, award-vs-tender delta, and the handover
  pack. Typed `baseline` client methods added.
- Verified end to end against a live server + browser: freeze refused before
  review (403), sealed v1 (64-char hash), `verify` intact, notice register
  extracting the 14-day and 28-day windows from clause text with p3 provenance,
  and the rendered Handover tab.
- 106 backend tests passing; ruff clean; frontend builds clean.
- **Phasing note:** the doc gates P2 behind the Phase-1 accuracy gate (§10);
  this ships as a config-flagged, fully decoupled module so it does not disturb
  Phase-1. The accuracy gate (5 real tenders + QS review) remains the real gate
  before P2 is *promoted*.

### Done — 2026-07-24 (session 19: in-app Help page + honest QS-lifecycle scope)

- **TS-040** — new static Help page at `/help` (`frontend/app/help/page.tsx`),
  linked from the header nav:
  - an 8-step **how-to-use** walkthrough (create workspace → open opportunity →
    upload full pack → confirm deadline wall → run risk review → run BOQ
    assurance → review/accept findings → generate & export);
  - the **rules it never breaks** (numbers from code not AI, every finding cited
    & quote-verified, human approves before export, data isolated per workspace);
  - an honest **QS-lifecycle coverage table** — states plainly that TenderShield
    owns the **pre-bid slice** (risk review, deadline extraction, BOQ arithmetic
    assurance, scope-gap detection, bid-decision artifacts) and deliberately does
    **not** do estimating, drawing take-off, BOQ authoring, interim valuations, or
    variations/claims/final account;
  - a not-legal / not-QS-certification **disclaimer** (Doc §11.4) reinforcing that
    findings are prompts for a qualified human, which is why the accept/reject
    step exists.
- **Scope framing corrected (same session):** the coverage table no longer
  flattens roadmap items into "not covered." It now uses three buckets —
  **Covered now** (Phase-1 pre-bid slice), **On the roadmap** (baseline lock,
  change/variation inbox + notice drafts, contractual time-bar engine incl.
  FIDIC 20.1 / NEC CE, cross-tender outcome graph — all from Doc §0.1/§1.2), and
  **Not ours** (takeoff, BIM/clash, live pricing, CPM, legal opinions — Doc §0.2).
  Added a "where it goes beyond typical QS tools" section (reads the contract,
  tracks the clock, playbook deviation, cross-tender learning, inspectable
  provenance, deterministic numbers). The AI assistant is not advertised since
  it is hidden from users.
- Spec `specs/frontend.md` updated (structure, B8, A2) to record the Help page,
  the hidden assistant, and human-label/typography decisions from session 18.
- Frontend builds clean; `/help` prerenders as static content.

### Done — 2026-07-24 (session 18: UI polish — hide assistant, human labels, fonts)

- **AI assistant hidden from users:** the Assistant tab, chat state, and handler
  removed from the opportunity workbench — user-facing tabs are now Overview /
  Risks / BOQ / Artifacts. (The backend module still exists; disable it fully by
  omitting `assistant` from `TS_ENABLED_MODULES`.)
- **No raw identifiers on screen:** new `lib/labels.ts` maps every internal code
  to a proper label — categories (`grand_total` → "Grand-total mismatch",
  `blank_rate` → "Blank rate", `ld` → "Liquidated damages", …), review status,
  deadline kinds, artifact kinds, opportunity status, doc kinds. Board + detail
  render through it; the BOQ tab label shows "BOQ" (not "Boq").
- **Proper typography:** app-wide Inter → system-UI font stack in Tailwind +
  legibility/feature settings in globals (drop in `next/font` Inter for an exact
  self-hosted face when building with network).

Frontend builds clean; backend unaffected (98 tests still passing).

### Done — 2026-07-23 (session 17: no-AWS scanned-table path)

- **TS-039** — the hard scanned-table BOQ case, **without AWS**: `RapidTableProvider`
  (rapid-table SLANet ONNX + RapidOCR, offline) reconstructs a table from a
  scanned/image BOQ page; a dependency-free HTML→rows parser + `scanned_boq_csv`
  maps it to canonical CSV; wired as the BOQ-upload fallback (`ingestion.scanned_boq_csv`,
  only when `TS_OCR_ENABLED`). The HTML→CSV conversion is unit-tested; the model
  downloads once on first use (blocked in this sandbox, so the recognition step is
  not sandbox-verified — works on a normal machine).
- **AWS is no longer required anywhere.** Textract removed as a dependency;
  TS-033 is now just tus resumable upload. Docs corrected. 99 tests passing.

### Done — 2026-07-23 (session 16: OCR + PDF table reading — no cloud)

- **TS-038** — real OCR + table extraction without AWS:
  - **pdfplumber** reads BOQ tables straight out of digital PDFs; new
    `POST /api/boq/opportunities/{id}/upload` accepts PDF/XLSX/CSV, detects the
    BOQ table, maps headers to canonical columns, and runs the deterministic
    checks. Tested end-to-end (duplicate + arithmetic caught from a PDF table).
  - pluggable **`OcrProvider`**: `RapidOcrProvider` (RapidOCR — ONNX, bundled
    models, **fully offline**; PyMuPDF rasterizes pages) reads scanned/image
    PDFs; `NullOcrProvider` default. Verified live: a text-free image PDF OCR'd
    back to its exact text.
  - **honest degradation** (Doc §12.4): a scanned PDF with no text layer is
    flagged `ocr_status="needs_ocr"` when OCR is off, instead of silently
    ingesting blank/garbage text. Enable with `TS_OCR_ENABLED=true` +
    `pip install -e ".[ocr]"`.
  - `file_to_boq_csv` + `ingestion.ocr` published as capabilities so BOQ reads
    tables without importing ingestion. OCR test skips where the `ocr` extra
    isn't installed (CI stays light).

Test suite: 98 passing, ruff clean; architecture test green.

### Done — 2026-07-23 (session 15: production hardening — implementable-now slice)

Built the parts of the hardening list that need no live credentials:

- **TS-026** — real multipart upload + text extraction: `extract.py` (PDF via
  pypdf, XLSX via openpyxl, CSV/text), `LocalStorage` (per-org, sha256), and
  `POST …/upload` that feeds the existing classify/segment/deadline pipeline.
  Tested end-to-end with a generated PDF (classified NIT, deadline extracted).
- **TS-030** — PDF export (reportlab): completes DOCX/PDF/XLSX; gated + stamped;
  `?format=pdf` returns a real `%PDF-`.
- **TS-029** — GST invoice computation (`gst.py`): CGST/SGST intra-state vs IGST
  inter-state (SAC 998313), sequential gap-free numbering. Pure + tested.
- **TS-028** — TOTP MFA (`mfa.py`, pyotp): enroll (secret + otpauth URI) +
  verify; `users.mfa_totp_secret` column (migration `0009`); `/auth/mfa/enroll`
  + `/verify`. Enforcement-at-login is a follow-up.
- **TS-027** — `notifications` module: pluggable `Sender` (ConsoleSender dev
  backend) + pure deadline-digest logic (alert windows 7/3/1/0 days). SES/MSG91
  adapters plug in behind the same interface (TS-035).
- **TS-031** — deploy scaffolding: `docker-compose.yml` (Postgres + backend +
  frontend), backend/frontend `Dockerfile`s, `.env.example`.
- **TS-032** — frontend CI job (npm ci + build) added to GitHub Actions.

Still needs live accounts (interfaces are built; see backlog TS-033…TS-037):
Textract OCR, tus resumable, Celery/Redis, SES/MSG91 send, Google OIDC/phone
OTP, Stripe. Migrations 0001→0009. **95 tests passing, ruff clean.**

### Handoff snapshot (for local takeover)

**All Phase-1 backlog tasks (TS-001…TS-025) are `done`.** 11 feature modules;
migrations 0001–0008; **88 backend tests passing, ruff clean; frontend builds
clean.** Full local run steps, env vars, and the end-to-end click-path are in
`README.md`. What remains is production infra (OCR/uploads/Postgres/payments/
alerts) and the non-code domain-accuracy gate (real tenders + QS + an
`ANTHROPIC_API_KEY`) — see "What's left" in `README.md` and below.

### Done — 2026-07-23 (session 14: assistant — the last module)

- **TS-024** — `assistant` module (Doc §8), grounded + tool-first:
  - pure `tools.py` (list_deadlines, filter_findings, missing_docs,
    rulepack_lookup) reading only the org's own data via capabilities.
  - `AssistantService` routes recognized intents (deadlines / findings by
    severity / missing docs) to **deterministic, cited answers that work with
    no API key**; off-topic questions are **refused** (grounded-only).
  - free-form questions use an injected `AnthropicAgent` only when
    `ANTHROPIC_API_KEY` is set, answering strictly from tool results.
  - `POST /api/assistant/chat`; frontend **Assistant tab** (ask box + grounded
    replies). Tests cover the deadline/findings/missing-doc intents + refusal.
- README rewritten as a local-takeover guide (run steps, env vars, click-path).

Test suite: 88 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 13: BOQ write-through + BOQ workbench)

- **BOQ write-through** — `BoqRunner` parses an uploaded workbook (CSV), runs
  the deterministic engine + scope-gap checklists (spec text pulled from the
  opportunity's clauses via ingestion), and **persists defects to the shared
  findings register** (`producer='boq'`) via the findings store capability.
  `POST /api/boq/opportunities/{id}/run`.
- BOQ defects now flow through the same pipeline as risk findings: they count
  toward the review gate and appear in the exported Bid Review Pack.
- **Frontend BOQ tab**: "Load sample BOQ & check" runs the engine and lists the
  defects (arith / grand-total / duplicate / blank-rate, all "deterministic
  check"). Risks vs BOQ findings are split by `producer` in the UI.
- **TS-013a complete** — all per-module models + migrations (0001–0008) done;
  risk + BOQ persist findings; review/drafting/export/billing wired.

Test suite: 84 passing, ruff clean; frontend builds clean. Verified live.

### Done — 2026-07-23 (session 12: billing + export renderer)

- **TS-022** — `billing` module (Doc §7, §15):
  - pure `plans.py` (free→exhausted, paygo requires-payment, pro/scale quotas;
    money in paise) + `webhook.py` (HMAC-SHA256, constant-time) — unit-tested.
  - `usage_events`, `payment_log` (append-only ledger), `webhook_events`
    (idempotency) + migration `0008`.
  - **webhook is the only truth**: it logs receipt *before* trusting, verifies
    signature, is idempotent by event id, and only then activates a plan /
    credits a paid review; a tampered signature → 400 + a `failed` ledger row.
  - free-tier metering (`authorize-review` → free_first_review, then 402
    `free_exhausted`); reads/updates org plan via a new `auth.orgs_factory`
    capability (billing never imports auth).
- **TS-023** — `export` module: Bid Review Pack renderer (Doc §1.1(8), §11.4):
  - pure `render.py` → **XLSX** (openpyxl) + **DOCX** (python-docx), each
    carrying the "Prepared with TenderShield · reviewed … · pack …" stamp.
  - **export gate enforced**: blocked (403 `review_incomplete`) until
    `review.gate` opens; consumes review/findings/drafting/ingestion/rulepacks
    via capabilities only.
  - frontend Artifacts tab: Export .docx / .xlsx buttons (authenticated blob
    download), enabled only when the gate is open.
  - PDF (WeasyPrint) deferred — heavy system deps.

Test suite: 83 passing, ruff clean; frontend builds clean. 0001→0008 verified.

### Done — 2026-07-23 (session 11: drafting — artifacts + the three validators)

- **TS-020** — `drafting` module (Doc §6.5), the anti-hallucination spine:
  - **three validators** (pure, `validators.py`): reject invented quotes,
    uncited clauses, and invented numbers against a `FactTable` built only from
    accepted findings. Unit-tested for each failure mode + the passing case.
  - deterministic `generator.py`: assembles the **clarification letter** and
    **assumptions & exclusions register** from accepted findings (facts injected,
    structure built) — validators pass by construction, no LLM key needed; an
    LLM polish pass would be subject to the same validators.
  - `Artifact` model + migration `0007` (org-scoped, RLS; versioned,
    `UNIQUE(opportunity, kind, version)`); 0001→0007 verified up+down.
  - `DraftingService.generate` pulls accepted findings via the findings store
    capability, validates, and writes a NEW version (never mutates); refuses
    with `no_accepted_findings` until review has accepted something.
  - endpoints: generate / list / get; **frontend Artifacts tab** — generate
    (disabled until the export gate opens) and read the versioned letter/register.

Test suite: 74 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 10: review workbench + audit + export gate)

- **TS-021** — `review` module, the professional-liability spine (Doc §11.4):
  - accept/edit/reject each finding — updates the review columns via the
    findings store capability (never imports findings); requires `reviewer`
    role; bad decision → 400, unknown finding → 404.
  - append-only `audit_log` table + migration `0006` (org-scoped, RLS on
    Postgres; 0001→0006 verified up+down); every decision writes an audit row.
  - **export gate**: `review.gate` returns `export_allowed` only when there are
    findings and none remain `proposed` — the block that stops export before a
    human has reviewed. Published as `review.service_factory` for drafting/export.
  - `GET queue` / `POST findings/{id}` / `GET gate` / `GET audit` endpoints.
  - **Frontend:** Risks tab now shows an export-gate banner and Accept/Reject
    buttons per finding; reviewed findings show their status.
  - Note: `BigInteger` PK uses a SQLite `Integer` variant so autoincrement works
    in tests while staying BIGSERIAL on Postgres.

Test suite: 68 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 9: findings persistence)

- **TS-013a (findings slice)** — a new pluggable `findings` module owns the
  shared `findings` table (Doc §3.2): SQLAlchemy model + migration `0005`
  (org-scoped, RLS on Postgres; 0001→0005 verified up+down) + `FindingStore`.
  - Producers write via the `findings.store_factory` capability, scoped by a
    `producer` column so a re-run of one producer replaces only its own rows and
    never disturbs another's (unit-tested for idempotency + producer isolation).
  - `risk` now persists its findings on run (still returns them too) and gained
    `findings` as a soft dep — resolved lazily, so risk still runs (in-memory)
    if the findings module is disabled.
  - `GET /api/findings/opportunities/{id}` lists the register, severity-sorted.
  - **Frontend:** the Risks tab now reads the persisted register (with
    review-status), loaded on open and after a run.
  - No module imports another's models — the table stays pluggable behind the
    store capability + the core `Finding` contract.

Test suite: 65 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 8: deadline extraction + deadline wall)

- **TS-015** — deadline extraction (Doc §6.2), the <3-minute promise:
  - pure `deadlines.py` — deterministic date parsing (DD/MM/YYYY, "15 Aug 2026",
    etc.) with keyword→kind classification (submission/pre-bid/clarification/
    validity/EMD/completion), `[pN]` page tracking, and noise control (bare
    dates with no deadline keyword are skipped). Dates are never invented; each
    carries its verbatim source line + page. LLM/relative-formula resolution are
    follow-ups — the deterministic pass already lights up the wall with no key.
  - `Deadline` model + migration `0004` (org-scoped, RLS on Postgres); also adds
    `submission_due`/`clarification_due` to `opportunities`. 0001→0004 verified.
  - extraction runs on document upload; sets the opportunity's `submission_due`
    from the earliest submission date; `GET …/deadlines` + confirm-chip endpoint.
  - **Frontend:** deadline wall on the opportunity overview (countdown colouring
    red<3d/amber<7d, page citations, confirm chips) and the board countdown
    badge now lights up from `submission_due`.
  - Verified full-stack live: uploading a NIT extracted bid submission (2d, red),
    pre-bid and clarification (1d) with page citations; board shows "2d to
    submission" in red. Screenshots captured.

Test suite: 62 passing, ruff clean; frontend builds clean.

### Done — 2026-07-23 (session 7: frontend skeleton — the UI)

- **TS-025** — Next.js 15 + TypeScript + Tailwind app (`frontend/`), Doc §9:
  - landing page (countdown-wall design + sample risk register), auth
    (signup/login), opportunity **board** (countdown badges: red <3d, amber <7d),
    and opportunity **detail** (document checklist + risk workbench tabs);
  - typed API client (`lib/api.ts`), session context (access token in memory +
    localStorage mirror; production uses httpOnly refresh cookie per Doc §5);
  - tri-state provenance badges (extracted fact / deterministic check / AI
    suggestion) as components, not copy (Doc §11.4);
  - `next build` clean (6 routes); bumped Next to 15.5.x (patched CVE).
- **Backend for the SPA:** `GET /api/ingestion/opportunities` (org-scoped list)
  + CORS middleware (`TS_CORS_ORIGINS`, configurable).
- **Verified full-stack, live:** ran FastAPI + Next together and drove a real
  signup → create two opportunities → upload a document flow with a headless
  browser. Screenshots captured: the uploaded doc classified as NIT and the
  missing-doc checklist flagged GCC/BOQ — all through the real API with RLS
  org-scoping (a second org's board is isolated, covered by a new test).

Test suite: 58 passing, ruff clean. Frontend builds clean.

### Done — 2026-07-23 (session 6: clause segmentation + risk engine)

- **TS-016** — clause segmentation (extends ingestion): pure `segment.py`
  (`segment_clauses` — header detection for Clause/GCC/SCC, `[pN]` page
  tracking, cross-ref extraction), `Clause` model + migration `0003_clauses`
  (org-scoped, RLS on Postgres; 0001→0002→0003 chain verified up+down).
  Documents are segmented on registration; `GET …/clauses` lists them.
- **TS-017** — `risk` module, the pattern engine (Doc §6.3):
  - `severity.py` — **deterministic** severity via a sandboxed AST evaluator
    over the pack's `severity_rule` strings (severity keywords resolve to
    themselves, facts from context, missing → 0, malformed → safe default).
    Severity never comes from the LLM.
  - `engine.py` — anchor retrieval, quote verification (normalized + fuzzy
    ≥0.85), absence detection, finding assembly. Pure over dicts.
  - `classifier.py` — injected LLM boundary: `NullClassifier` (no key → absence
    detection still works) / `AnthropicClassifier` (JSON-only, temp 0, tender
    text as untrusted data). Never returns severity.
  - `RiskService` consumes ingestion + rulepacks purely via registry
    capabilities; `POST /api/risk/opportunities/{id}/run`.
  - **Ran live** on the synthetic tender: correct deterministic severities
    (LD/escalation/termination critical, defect high), quotes verified against
    clause text, and a deliberately-wrong quote flagged unverified.
  - Fixed the synthetic payment clause to 120 days (unambiguous `high`); the
    "is 90 days high or medium?" boundary is a QS-validation calibration item.

Test suite: 57 passing, ruff clean.

### Done — 2026-07-23 (session 5: ingestion module + auth boundary hardening)

- **Auth boundary refactor** — the generic request dependencies (`get_session`,
  `current_principal`, `require`) moved to `app/core/deps.py`, which resolves
  auth purely by capability name. Auth now publishes a plain
  `auth.authenticate(request, session)` + `auth.check_role` (instead of
  Depends-wrapped internals). Result: any module gets auth+RBAC+RLS without
  importing auth; auth's own router consumes the same core deps. 43→still green.
- **TS-014** — `ingestion` module, the opportunity aggregate owner:
  - pure `classify.py` (`classify_text` rules-first anchors, `missing_documents`)
    with DB-free unit tests;
  - `Opportunity` + `Document` models (org-scoped, RLS) + migration
    `0002_ingestion_tables` (RLS emitted on PostgreSQL only; up/down verified on
    the 0001→0002 chain);
  - `IngestionService`: create opportunity, classify+register document,
    missing-doc checklist — all scoped by `org_id` (defense-in-depth with RLS),
    consuming `rulepacks.loader` as a lazy soft dep with built-in fallback
    anchors;
  - routes under `/api/ingestion/opportunities`, auth-gated via `core.deps`.
  - First real cross-module consumer: ingestion uses auth through the registry,
    proven by an org-isolation test (org B gets 404 on org A's opportunity) and
    a soft-dep test (works with rulepacks disabled).

Test suite: 49 passing, ruff clean.

### Done — 2026-07-23 (session 4: auth module)

- **TS-011 / TS-012** — `auth` module (Doc §5), built for isolated testing +
  refactoring:
  - **Pure security primitives** (`security.py`): argon2id hashing, RS256 JWT
    mint/decode with `kid`, ephemeral-keypair generation for dev. `refresh.py`:
    token generation + `evaluate_refresh()` (the reuse-detection *verdict* as a
    DB-free pure function). `rbac.py`: roles + `role_at_least`. All covered by
    `test_auth_security.py` with **no DB and no FastAPI** — rewritable in place.
  - **Module internals** (`models.py`, `service.py`, `deps.py`, `router.py`):
    signup/login/refresh/logout/me/add-member; rotating refresh with
    whole-family revocation on replay; RBAC guard; per-request RLS binding
    (`bind_org_context`). Only capabilities (`auth.current_principal`,
    `auth.require`, `auth.keys`) are exposed — consumers never import internals.
  - **TS-013a (auth slice)** — first real Alembic migration `0001_auth_tables`
    (orgs, users, org_members, refresh_tokens), portable across SQLite/Postgres;
    verified up + down.
- Ruff configured for FastAPI's `Depends`-in-defaults idiom; email fields kept
  as plain `str` to avoid an extra dependency.

Test suite: 43 passing, ruff clean. Added argon2-cffi + PyJWT[crypto].

### Done — 2026-07-23 (session 3: deterministic BOQ engine + synthetic tender)

- **Synthetic sample tender** (`evals/in-works/sample_tender/`): a hand-written
  fixture with deliberately planted traps — `boq.csv` (9 rows), `conditions.md`
  (5 clause traps + `[pN]` markers), and `gold_answer.yaml` as its own ground
  truth. Lets the pipeline be proven end-to-end without a real tender or API key.
- **TS-018** — `boq` module: deterministic engine (Doc §6.4, zero LLM) —
  `normalize()` (unit-canon folding + `amount_calc`), DuckDB `run_checks()`
  (arithmetic error, blank rate, duplicate, quantity outlier, grand-total /
  carry-forward mismatch). Findings use the new shared `Finding` contract in
  `app/core/contracts/findings.py`, tagged `deterministic_check`.
- **TS-019** — scope-gap engine: `SpecTextIndex` + trade-checklist cross-
  reference; a gap fires only when a spec trigger is present AND no BOQ line
  matches. `boq` consumes `rulepacks.loader` as a lazily-resolved soft dep and
  degrades to built-in defaults when rulepacks is disabled.
- **Ran it live:** the engine catches exactly the planted defects (duplicate ×2,
  arithmetic, blank rate, grand-total) and 5 civil scope gaps with zero false
  positives (waterproofing correctly NOT flagged). `test_boq.py` asserts this
  against the gold answer, including a determinism (identical-rerun) check.
- **Accuracy harness** now accepts `.md`/`.txt` (not just PDF), so the LLM half
  runs on `conditions.md` directly with an API key.

Test suite: 30 passing, ruff clean. pandas + duckdb added.

### Done — 2026-07-22 (session 2: Phase-0 completion + DB foundation)

- **TS-009** — 3 trade checklists (civil_structure, electrical, hvac) for
  scope-gap detection, drafted from public sources with `confidence:
  unvalidated`; loader parses `boq/trade_checklists/*.yaml` into typed schemas.
- **TS-006** — Phase-0 Week-2 accuracy harness (`scripts/phase0_accuracy_test.py`,
  throwaway by design): runs the 5 in-works patterns over tender PDFs at
  temperature 0, verifies every quote verbatim (invented quote → RED_FLAG),
  wraps tender text as untrusted data.
- **TS-010** — Eval golden-set scaffold `evals/in-works/`
  (classification, deadlines, risk_patterns, boq, drafting) + the scored
  pass/fail bar in `scorecard.md` (Doc §19.5, §11.5).
- **TS-013** — DB foundation in `app/core/db.py`: declarative `Base`,
  `OrgScopedMixin` (org_id + RLS self-registration), `TimestampMixin`,
  `rls_statements()`, `bind_org_context()`, engine/session builders published
  as `db.engine`/`db.sessionmaker` registry capabilities. Alembic scaffold with
  pluggable per-module model discovery; CI gains an up/down migration check.
  Per-module models split out to **TS-013a** (land with each module).

Test suite: 23 passing, ruff clean.

### Done — 2026-07-22 (session 1: project bootstrap)

- **TS-001** — Repo bootstrapped: mandatory AI workflow rules for Claude
  (`CLAUDE.md`) and Cursor (`.cursor/rules/` — workflow, architecture,
  specs/tasks conventions); build blueprint v1.0 vendored to
  `docs/TenderShield_Full_Build_Doc.md` as the requirement source of truth.
- **TS-002** — Task backlog `TS-001`–`TS-025` derived from the blueprint
  (bootstrap + Phase 0 + Phase 1, in the doc's value order; Phase 2+ excluded
  by design until gates pass).
- **TS-003** — Spec suite generated in `specs/`: product overview, data-model
  ownership map, Phase-0 accuracy test, frontend, and per-module specs (core,
  rulepacks, auth, ingestion, risk, boq, drafting, review, billing, assistant),
  each citing its build-doc sections and defining capabilities/events.
- **TS-004** — Backend core: pluggable module framework (FastAPI modular
  monolith). `ModuleSpec` plugin contract, fail-isolated loader
  (`TS_ENABLED_MODULES` boots any subset), `ServiceRegistry` + `EventBus` as
  the only cross-module channels, `health` module, and an architecture test
  that fails the build on any hard cross-module import. 13 tests.
- **TS-005** — CI: ruff + pytest on every push (GitHub Actions).
- **TS-007** — `rulepacks/in-works/` scaffold: pack.yaml, doc-type anchors +
  expected-doc set, BOQ unit-canon map + check thresholds, default contractor
  playbook; backend `rulepacks` module with Pydantic-validated loader
  (malformed YAML skipped, never fatal), `validated_only` filter, REST
  endpoints, `rulepacks.loader` capability.
- **TS-008** — First 5 Phase-0 risk patterns from public sources (payment
  terms, price escalation, LD cap, defect liability/retention, termination
  for convenience) — all `confidence: unvalidated` with `source:` citations
  (Doc §14.1). Test suite now 18 passing, ruff clean.

### Next

The Phase-1 feature engine is complete end-to-end (upload → classify →
deadlines → clauses → risk register → BOQ checks → review → clarification
letter/assumptions → gated DOCX/XLSX/PDF export → billing), the `assistant`
module is built (hidden from the UI by product choice), and the first Phase-2
feature — **baseline lock** (TS-041/042) — now ships end to end. Next:

- **Phase-2 continuation (natural follow-ons to baseline lock):**
  - **TS-043** — notice-deadline countdowns + alerts driven by the notice-rule
    register (the register now exists; wire it to the deadline/notification
    path). Doc §0.1 (P3), §10.
  - **TS-044** — award-document ingestion: parse the negotiated contract/award
    letter so the award baseline is sealed from real award text (today it seals
    the reviewed state). Doc §0.1 (P2/P3).
  - **TS-045** — handover-pack file export (DOCX/PDF) reusing the export
    renderer (today the pack is structured JSON in the UI).
- **The real gate (not code):** domain-accuracy validation — 5 real tenders +
  gold answers + a QS review (Doc §18.3/§19.2) — is the gate that *promotes*
  Phase 2 out of "built-ahead". Set `ANTHROPIC_API_KEY` to turn on the LLM
  classifier + the Week-2 accuracy harness. Founder still needs to collect the
  5 real tenders + gold answers — code can't substitute for these.
- **Production hardening (infra, not logic):** tus resumable upload, Celery/Redis
  streaming, Postgres/RDS deploy, email/WhatsApp send adapters, phone-OTP/Google
  OIDC, live Razorpay/Stripe keys — all logic-ready behind existing interfaces
  (TS-033/034/035/036/037), pending external creds.
- Frontend follow-ups: PDF.js source-page view, a frontend lint/build step in CI.
