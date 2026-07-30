# End-to-End Automation Test Scenarios

**Task:** TS-166  
**Purpose:** Provide executable, traceable user-journey tests for TenderShield. Each scenario maps to one or more sections of the end-to-end audit prompt (`END_TO_END_PRODUCTION_AUDIT_PROMPT.md`) so the prompt can be run against the evidence produced by these tests.

**How to run these scenarios:**

1. Start the backend and frontend locally (`./scripts/run.sh local` or `docker compose --env-file .env.dev up --build`).
2. Run Playwright (recommended) or Cypress against `http://localhost:3000` and `http://localhost:8000/api`.
3. Use the console OTP fallback to read verification codes from the backend log.
4. Use the synthetic tender sample under `evals/in-works/sample_tender/` for document ingestion tests.

**Test accounts:**

| Role | Email | Phone | Password | Notes |
|---|---|---|---|---|
| Account owner | `owner@example.com` | `+919876543210` | `Test1234!` | Creates workspaces, invites members, deletes account |
| Workspace admin | `admin@example.com` | `+919876543211` | `Test1234!` | Invited by owner, manages team |
| Workspace member | `member@example.com` | `+919876543212` | `Test1234!` | View-only on opportunities, cannot manage billing |
| Super admin | `super@example.com` | `+919876543213` | `Test1234!` | Sees all users and workspaces in `/admin` |

---

## Scenario 1: Account sign-up, email/mobile verification, and login

**Audit prompt mapping:** §3 (Authentication), §6 (Data Integrity), §7 (Security)

### Preconditions

- Clean SQLite/Postgres database or reset test fixtures.
- Backend and frontend running with `TS_ENV=dev`.
- No real SMS/email provider configured (console fallback is sufficient).

### Steps

1. Navigate to `/login`.
2. Click "Create account".
3. Fill the sign-up form: org/firm name, email, mobile, city, DOB, password, confirm password.
4. Submit and observe that the UI moves to the email-verification screen.
5. Read the verification token from the backend console log.
6. `POST /api/auth/verify-email` with the token.
7. Read the mobile verification token from the console log.
8. `POST /api/auth/verify-mobile` with the token.
9. Log in with email and password.
10. Read the login OTP from the console log.
11. `POST /api/auth/mfa/challenge` with the OTP.
12. Verify the response contains `access_token`, `refresh_token` (as `httpOnly` cookie), and `workspaces: []`.

### Expected results

- Both `email_verified` and `mobile_verified` are `true`.
- Login without OTP returns `mfa_required` or equivalent incomplete-session response.
- Access token expires in 15 minutes; refresh token lasts 30 days.
- Unverified accounts cannot log in.

### Negative cases

- Reuse the same email or mobile → `409` duplicate.
- Submit mismatched passwords → `400` validation error.
- Weak password (no uppercase/number/special/min-length) → `400`.
- Expired email/mobile token → `400` or `401`.
- Wrong OTP → `401` `mfa_invalid`.
- Login before verifying email → `401` or `403` with a "verify email first" message.

---

## Scenario 2: Workspace creation and switch

**Audit prompt mapping:** §3 (Authorization), §5 (Workspace/tenant model)

### Preconditions

- Authenticated account owner from Scenario 1.

### Steps

1. After login the user lands on `/` with no workspaces; click "Create workspace".
2. Enter workspace name and country/region.
3. Submit `POST /api/auth/workspaces`.
4. Observe the workspace appears in the header switcher.
5. Create a second workspace.
6. Use the workspace switcher to call `POST /api/auth/workspaces/{id}/switch`.
7. Refresh `/opportunities` and verify the active workspace changed (e.g. workspace name in header).

### Expected results

- Each workspace has its own `workspace_id`.
- `GET /api/auth/workspaces` returns only workspaces the user owns or is a member of.
- Switching returns a new access token bound to the selected workspace.
- Cross-tenant endpoints (`GET /api/opportunities` for the new workspace) do not leak data from the previous workspace.

### Negative cases

- Switch to a workspace the user does not belong to → `403` or `404`.
- Use an expired access token after switch → `401` and silent refresh.

---

## Scenario 3: Team invitations and role management

**Audit prompt mapping:** §3 (Authorization), §5 (Roles and permissions), §6 (Data Integrity)

### Preconditions

- Account owner has at least one workspace.
- `admin@example.com` and `member@example.com` do not yet belong to this workspace.

### Steps

1. Go to `/team`.
2. Click "Invite member" and enter `admin@example.com` with role `admin`.
3. Read the invitation token from the console log.
4. In a separate browser session, sign up as `admin@example.com` and verify email/mobile.
5. Call `POST /api/auth/invitations/{token}/accept`.
6. Observe the new user appears in the workspace member list with role `admin`.
7. Invite `member@example.com` with role `member`.
8. Accept the invitation.
9. As owner, change the member role to `viewer`.
10. As owner, remove `viewer` from the workspace.

### Expected results

- Invitations are scoped to the workspace and expire after a configured TTL.
- Accepted invitation increments seat count and checks plan seat limits.
- Role change is persisted and reflected on next API call.
- Removed member can no longer access workspace resources.

### Negative cases

- Accept an invitation with a workspace already at its plan seat limit → `403`.
- A workspace `member` tries to invite or change roles → `403`.
- A removed member reuses an old access token → `401` after token refresh fails.

---

## Scenario 4: Tender document upload and ingestion

**Audit prompt mapping:** §2 (Technical Baseline), §4 (Feature Completeness), §6 (Data Integrity)

### Preconditions

- Authenticated user in a workspace.
- Sample files: `evals/in-works/sample_tender/conditions.md` and `boq.csv`.

### Steps

1. Go to `/opportunities` and click "New opportunity".
2. Enter title, client, deadline, estimated value, and location.
3. Submit `POST /api/ingestion/opportunities`.
4. Open the opportunity.
5. Upload `conditions.md` via the document upload control (or `POST /api/ingestion/opportunities/{id}/documents` with `sample_text`).
6. Wait for ingestion status (`GET /api/ingestion/opportunities/{id}`) to be `ready`.
7. Upload `boq.csv` as the BOQ.
8. Open the "Deadlines" tab and verify extracted deadlines with page/quote citations.
9. Open the "Clauses" tab and verify segmented clauses.

### Expected results

- Documents are stored in `TS_STORAGE_DIR` or the configured S3/MinIO bucket.
- Each clause/deadline has `source_page` and `source_quote`.
- Ingestion status transitions `pending` → `processing` → `ready` or `error`.
- BOQ rows appear in the BOQ table with deterministic checks.

### Negative cases

- Upload a file larger than the configured max size → `413`.
- Upload a malformed/empty file → `400` or `422` and `status=error`.
- A user from another workspace accesses the opportunity ID → `403`/`404`.

---

## Scenario 5: Risk review and findings

**Audit prompt mapping:** §4 (Feature Completeness), §6 (Data Integrity), §7 (Security)

### Preconditions

- Opportunity with uploaded `conditions.md`.
- `TS_OPENROUTER_API_KEY` set for LLM classification, OR not set for deterministic absence detection only.

### Steps

1. Open the opportunity.
2. Go to the "Risks" tab and click "Run risk review" (`POST /api/risk/opportunities/{id}/run`).
3. Wait for the job to finish.
4. Verify the findings list contains risk clauses with `category`, `severity`, `source_quote`, `source_page`.
5. Click a finding to see the source PDF/text at the quoted page.
6. Mark a finding as reviewed (`POST /api/review/opportunities/{id}/findings/{fid}`).

### Expected results

- `severity` is deterministic (not from LLM text).
- Each finding has an `explanation` object with `matched_pattern.id`.
- Reviewed findings change state and emit an audit log entry.
- Export is blocked until all findings are reviewed.

### Negative cases

- Run risk review on a workspace with a paid plan and an unvalidated pattern → unvalidated patterns are excluded or badged.
- A `viewer` role tries to run risk review → `403`.
- Attempt to review a finding from a different opportunity → `403` or `404`.

---

## Scenario 6: BOQ arithmetic and scope-gap check

**Audit prompt mapping:** §4 (Feature Completeness), §6 (Data Integrity)

### Preconditions

- Opportunity with uploaded `boq.csv`.
- Trade checklists and standards configured or defaults loaded.

### Steps

1. Open the opportunity and go to the "BOQ" tab.
2. Click "Run BOQ check".
3. Verify defects appear with rupee impact, sorted by impact.
4. Open a defect to see the source BOQ row and the expected-vs-actual calculation.
5. Check the "Scope" tab for missing trade items based on the rule-pack checklist.

### Expected results

- All money values are in minor units (paise) in the API.
- The BOQ engine returns deterministic results (zero-LLM).
- Each defect has `unit`, `quantity`, `rate`, `amount`, and a `source_quote`.

---

## Scenario 7: Baseline lock and handover pack

**Audit prompt mapping:** §4 (Feature Completeness), §6 (Data Integrity)

### Preconditions

- Opportunity has completed risk and BOQ review (all findings reviewed).

### Steps

1. Go to the "Handover" tab.
2. Click "Lock baseline".
3. Verify the baseline is created with a content hash.
4. Upload an award document (e.g. a second version of `conditions.md`).
5. Run award-vs-tender comparison.
6. Generate the bid-decision letter (`POST /api/drafting/opportunities/{id}/bid-decision`).
7. Generate the commercial handover pack (`POST /api/drafting/opportunities/{id}/handover`).

### Expected results

- Baseline lock is blocked until all findings are reviewed.
- The baseline hash is recorded in the audit log.
- Award-vs-tender delta shows added/deleted clauses.
- Generated artifacts have a review-approval stamp and are gated by `reviewed=true`.

---

## Scenario 8: Billing, plans, and invoices

**Audit prompt mapping:** §4 (Feature Completeness), §7 (Security), §8 (Operational readiness)

### Preconditions

- Workspace owner is authenticated.
- Razorpay/Stripe keys configured if testing real payments; otherwise use test mode.

### Steps

1. Go to `/billing`.
2. Select a plan and start checkout (`POST /api/billing/checkout`).
3. Complete the test payment or mock webhook.
4. Verify the workspace plan updates and an invoice is created.
5. `GET /api/billing/invoices` returns the invoice list.
6. `GET /api/billing/usage` returns metered usage.

### Expected results

- Billing webhook secret is the only source of truth; client redirect does not activate the subscription.
- Seat limits are enforced when inviting members.
- Free-tier metering is race-safe and stored as an integer count.

### Negative cases

- Forge a billing webhook without the secret → rejected.
- Exceed plan seat limit → `403` with `paywall`/`seat_limit` error.

---

## Scenario 9: Notifications and deadline digest

**Audit prompt mapping:** §4 (Feature Completeness), §8 (Operational readiness)

### Steps

1. Create an opportunity with a deadline within 3 days.
2. Trigger the deadline-digest scheduler (`POST /api/admin/trigger-notifications` or Celery beat).
3. Read the notification from the console log (or real email/SMS if configured).
4. Verify the user can set notification preferences (`POST /api/notifications/preferences`).

### Expected results

- Each user receives at most one digest per deadline window (deduplication).
- Preference changes stop notifications for the disabled channel.

---

## Scenario 10: Account settings and data export / deletion

**Audit prompt mapping:** §3 (Authentication), §5 (Privacy / GDPR), §7 (Security)

### Steps

1. Go to `/settings`.
2. Update profile fields (city, DOB, phone).
3. Change password with current password and new password.
4. `POST /api/auth/export` and verify the JSON export contains the user profile and all workspace-scoped tables the user can access.
5. `DELETE /api/auth/account` with the current password and `confirm: true`.
6. Attempt to log in again with the deleted account → `401`.

### Expected results

- Profile updates persist and trigger re-verification for phone changes.
- Password change requires the old password and enforces the same complexity as sign-up.
- Export includes all user-owned rows and workspace rows they own or are members of; no `users` table rows for others.
- Account deletion removes the user and cascades memberships, refresh tokens, and workspace data for owned workspaces.

### Negative cases

- Export without authentication → `401`.
- Delete account with wrong password → `400` `invalid_password`.
- Delete without `confirm: true` → `400` `confirm_required`.

---

## Scenario 11: Super-admin and workspace governance

**Audit prompt mapping:** §3 (Authorization), §7 (Security), §8 (Operational readiness)

### Steps

1. Log in as `super@example.com`.
2. Navigate to `/admin`.
3. List all workspaces and users.
4. View the audit log (`GET /api/health/details` or `/api/admin/audit-log`).
5. Search or filter audit events by actor, workspace, and action.

### Expected results

- Super-admin endpoints require `is_superadmin=true`.
- Audit log is append-only and owned by the `review` module.
- Regular users cannot access `/admin` or super-admin APIs.

---

## Scenario 12: Security and isolation regression suite

**Audit prompt mapping:** §7 (Security), §6 (Data Integrity)

### Steps

1. **Cross-tenant read:**
   - User A from workspace 1 calls `GET /api/opportunities` with workspace 2’s `workspace_id` in headers or by switching token.
   - Expected: `403` or empty list.

2. **RLS bypass in direct DB access:**
   - If testing with PostgreSQL, run `tests/test_rls_postgres.py` against a non-superuser role.
   - Expected: cross-tenant reads/writes fail.

3. **Prompt injection:**
   - Send a user query to `/api/assistant/chat` containing override instructions.
   - Expected: refusal and no execution of injected instructions.

4. **File path traversal:**
   - Request a stored file with `../` or absolute paths.
   - Expected: `400`/`404` and no filesystem escape.

5. **Unvalidated rule-pack on paid plan:**
   - With a paid workspace and `TS_BETA_UNVALIDATED=false`, run risk review.
   - Expected: unvalidated patterns are excluded.

6. **Money as float:**
   - Inspect API responses for `amount_exposure` and invoice amounts.
   - Expected: integer paise values, never floats.

---

## Scenario 13: Operational readiness and observability

**Audit prompt mapping:** §8 (Operational readiness)

### Steps

1. `GET /api/health` returns `ok`.
2. `GET /api/health/live` returns `200`.
3. `GET /api/health/ready` returns `200` when DB, storage, Redis, and broker are healthy.
4. `GET /api/health/metrics` returns Prometheus text.
5. Trigger an error and verify it appears in Sentry when `TS_SENTRY_DSN` is configured.
6. Verify backup/restore instructions are documented and can be run manually.

---

## Automation notes

- Use `Playwright` with `test.use({ baseURL: "http://localhost:3000" })`.
- Use the backend `TestClient` or `httpx` for API-only scenarios.
- Seed test data via `backend/tests/conftest.py` fixtures if running from pytest.
- Reset the database between scenarios with `alembic downgrade base && alembic upgrade head` or a transaction rollback.
- Capture screenshots and API response JSON for every failed assertion so the audit prompt can be fed concrete evidence.
