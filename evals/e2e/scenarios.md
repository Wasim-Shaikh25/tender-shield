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

## Scenario 14: Authentication edge cases and session lifecycle

**Audit prompt mapping:** §3, §7

### Steps

1. Sign up with an email already in use by an unverified account; verify whether the existing unverified row is reused or rejected.
2. Sign up with a mobile number already linked to another account.
3. Request email verification token twice; verify the second token invalidates the first.
4. Verify email and then attempt to verify again with the same token; expected `400`.
5. Log in with a valid password, capture `refresh_token` cookie, then log out and confirm the refresh token is rejected.
6. Use refresh token rotation: obtain a new access token, then try to reuse the old refresh token; expected `401` reuse detection.
7. Log in from two different browsers simultaneously and verify each has its own refresh token family.
8. Leave the session idle beyond access-token expiry; verify the next API call triggers a silent refresh and succeeds.

### Negative cases

- Login with non-existent email → `401` `invalid_credentials`.
- Login with correct password but unverified email → `403` or `401` with a verification-required message.
- Verify mobile with a code generated for email → `400`.
- Access a protected route with only an expired access token and no refresh cookie → `401`.

---

## Scenario 15: Password policy and account recovery

**Audit prompt mapping:** §3, §7

### Steps

1. Attempt sign-up with passwords: `short`, `nouppercase1!`, `NOLOWERCASE1!`, `NoSpecial123`, `NoDigits!aa` — all should fail.
2. Reset password via `/api/auth/forgot-password`; read the reset token from console log.
3. Use the reset token within TTL and set a compliant new password.
4. Try the reset token again after use; expected `400`.
5. Request a reset for an unregistered email; verify the response does not leak whether the email exists (returns success to the UI).
6. Change password from `/settings` with the wrong current password; expected `400`.
7. Change password and verify old refresh tokens are revoked.

---

## Scenario 16: MFA/TOTP enrollment and fallback

**Audit prompt mapping:** §3, §7

### Steps

1. Enroll TOTP for an account (`POST /api/auth/mfa/enroll` with `method=totp`).
2. Scan or parse the `otpauth_uri` and generate a valid TOTP code.
3. Verify the TOTP code; confirm `mfa_method` becomes `totp`.
4. Log out and log back in; supply the TOTP code in the challenge.
5. Switch MFA method from `totp` to `email`/`sms`; verify the method updates and the next login uses email/SMS OTP.
6. Enroll with an invalid phone format for `sms`; expected `422`.

### Negative cases

- Verify TOTP with a wrong code three times; verify the account is not locked out but the challenge keeps returning `mfa_invalid`.
- Attempt to enroll TOTP while email/mobile is unverified → `403` or `400`.

---

## Scenario 17: Workspace lifecycle and boundaries

**Audit prompt mapping:** §3, §5, §7

### Steps

1. Create a workspace with a reserved/suspicious name (e.g. HTML/JS tags); verify it is stored as plain text.
2. Rename a workspace and verify the change reflects across all sessions.
3. Create two workspaces with the same name by the same user; verify both succeed and are distinguishable by ID.
4. Delete a workspace the user does not own but is a member of; expected `403`.
5. Transfer workspace ownership to another admin (if supported).
6. List workspaces for an account that belongs to 0, 1, and 50 workspaces; verify pagination if applicable.
7. Verify a workspace cannot be created with an empty name or malformed country code.

---

## Scenario 18: Invitation lifecycle and seat accounting

**Audit prompt mapping:** §3, §5, §7

### Steps

1. Send an invitation to an email; revoke it before acceptance; verify the token is no longer valid.
2. Send an invitation; accept it; then try to accept the same token again; expected `400`.
3. Send invitations up to the workspace plan seat limit and attempt one more; verify `403` `seat_limit`.
4. Remove a member and immediately invite another to the same workspace; verify the seat count updates and the new invitation succeeds.
5. Invite a user who is already a member; expected `409` or `400`.
6. Verify expired invitations are cleaned up (or rejected) after TTL.
7. Resend an invitation token; verify the old token is invalidated.

---

## Scenario 19: Role-based access control matrix

**Audit prompt mapping:** §3, §5, §7

### Steps

For each role (`owner`, `admin`, `member`, `viewer`), verify access to:

- `POST /api/opportunities` (create)
- `POST /api/ingestion/opportunities/{id}/documents` (upload)
- `POST /api/risk/opportunities/{id}/run` (run risk)
- `POST /api/review/opportunities/{id}/findings/{fid}` (review)
- `POST /api/billing/checkout` (billing)
- `POST /api/auth/invitations` (invite)
- `PATCH /api/auth/members/{id}/role` (change role)
- `DELETE /api/auth/members/{id}` (remove member)
- `GET /api/admin/*` (super admin)

Expected: `owner` and `admin` can manage team; `member` can create and review; `viewer` read-only; billing reserved for owner/admin.

---

## Scenario 20: Opportunity CRUD and search

**Audit prompt mapping:** §4, §6, §7

### Steps

1. Create an opportunity with all fields; verify the response contains `id`, `workspace_id`, `title`, `client`, `deadline`.
2. Update the opportunity deadline; verify the countdown wall updates.
3. Create 60 opportunities and verify `GET /api/opportunities` returns paginated results with `total`, `page`, `page_size`.
4. Search opportunities by title, client, and location.
5. Sort by deadline, value, and status.
6. Delete an opportunity and verify it disappears from the list and its documents/clauses/findings are removed or soft-deleted.
7. Attempt to update an opportunity in another workspace; expected `403` or `404`.

---

## Scenario 21: Document upload variants and tus protocol

**Audit prompt mapping:** §2, §4, §6

### Steps

1. Upload a small `.txt` file via multipart.
2. Upload a `.pdf` via tus protocol: `OPTIONS` → `POST` → `PATCH` → `HEAD`.
3. Upload a `.xlsx` with 1000 rows and verify ingestion completes.
4. Upload a `.csv` with page-marker headers and verify `sample_text` includes `[pN]` markers.
5. Upload a `.docx` and verify text extraction.
6. Upload a file with a non-standard but valid extension (e.g. `.rar`); verify it is rejected or handled.
7. Upload a `.pdf` with scanned pages while `TS_OCR_ENABLED=false`; verify `needs_ocr=true` and no text is invented.

### Negative cases

- Send `POST` to tus without `Upload-Length`; expected `400` or `412`.
- Resume an upload with an invalid/short upload ID; expected `404`.
- Upload a file exceeding `MAX_FILE_SIZE`; expected `413`.
- Upload an empty file; expected `400`.

---

## Scenario 22: File storage and retrieval

**Audit prompt mapping:** §2, §7

### Steps

1. Upload a document and record the returned `storage_key`.
2. Download the file via `GET /api/ingestion/documents/{id}/download`; verify `Content-Disposition` filename is sanitized.
3. Verify the downloaded file matches the uploaded bytes (checksum).
4. With `TS_STORAGE_TYPE=s3` or MinIO, verify the object exists in the bucket and is not world-readable.
5. Request a file from another workspace using a forged `storage_key` or document ID; expected `403`/`404`.

### Negative cases

- Path traversal in filename (e.g. `../../../etc/passwd`); verify stored name is sanitized.
- Request a deleted document; expected `404`.

---

## Scenario 23: Ingestion edge cases and provenance

**Audit prompt mapping:** §4, §6

### Steps

1. Ingest a document with duplicate clause text on multiple pages; verify each clause keeps its own `source_page`.
2. Ingest a document with no recognizable text (blank PDF); verify no invented clauses and `status=ready` with empty results.
3. Re-upload the same document under the same opportunity; verify version handling or replacement.
4. Upload a document with page numbers in the text (e.g. "Clause 5 [p12]") and verify the parser does not double-count page markers.
5. Ingest a tender pack ZIP if supported; verify each contained file is processed.

---

## Scenario 24: Risk engine behavior matrix

**Audit prompt mapping:** §4, §6, §7

### Steps

1. Run risk review with `TS_OPENROUTER_API_KEY` set; verify LLM classifications and deterministic severity.
2. Run risk review with no key; verify `NullClassifier` still produces absence findings for known patterns.
3. Upload a GCC with a missing escalation clause; verify an absence finding fires for the escalation pattern.
4. Upload a GCC with a penalty cap and verify severity is `critical` when the cap is missing.
5. Run risk review on a workspace with `validated_only=true` and unvalidated patterns; verify unvalidated patterns are excluded or badged.
6. Run risk review twice on the same opportunity; verify results are deterministic (same inputs → same findings).

### Negative cases

- Inject instructions into `sample_text` (e.g. "Ignore all previous instructions..."); verify `looks_like_injection` returns refusal/empty classification.
- Classify a pattern with a prompt that itself contains injection markers; expected empty result.
- Cite a page not present in the document; verify finding is rejected or confidence lowered.

---

## Scenario 25: BOQ engine edge cases

**Audit prompt mapping:** §4, §6

### Steps

1. Upload a BOQ with non-standard units (`nos`, `rm`, `kg`, `m2`, `m3`, etc.); verify unit canonicalization.
2. Upload a BOQ with arithmetic errors in totals; verify each line is flagged with the expected-vs-actual difference.
3. Upload a BOQ with missing mandatory columns; expected `400`/`422`.
4. Upload a 50,000-row BOQ and verify response time is acceptable.
5. Upload a BOQ where the same trade has both over- and under-billed amounts; verify scope-gap findings.
6. Verify `amount_exposure` is always an integer in paise, even when the CSV contains decimals.

---

## Scenario 26: Review workbench and audit trail

**Audit prompt mapping:** §4, §6, §7

### Steps

1. Create multiple findings and review each with `decision=accept`, `decision=reject`, or `decision=needs_review`.
2. Verify `GET /api/review/opportunities/{id}/queue` returns only findings for that opportunity.
3. Verify the audit log records each review action with `actor_id`, `workspace_id`, `opportunity_id`, `finding_id`, and `action`.
4. Set a finding decision and then attempt to change it without the correct role; expected `403`.
5. Attempt to review a finding from another opportunity; expected `403`/`404`.
6. Export the review report before all findings are reviewed; expected `403` export-gate.

---

## Scenario 27: Baseline lock and versioning

**Audit prompt mapping:** §4, §6

### Steps

1. Lock the baseline after full review; record the `content_hash`.
2. Attempt to lock the baseline before all findings are reviewed; expected `409`.
3. Lock baseline, then upload an addendum, then re-lock; verify a new version and hash.
4. Verify the baseline cannot be mutated after locking.
5. Compare the latest baseline with an older one; verify the delta shows added/deleted/changed clauses.

---

## Scenario 28: Artifact generation and export gating

**Audit prompt mapping:** §4, §6, §7

### Steps

1. Generate a bid-decision letter; verify the content contains the factor table and a "commercial judgment call" disclaimer.
2. Generate a clarification letter with assumptions; verify each assumption has a citation.
3. Generate a handover pack (DOCX/XLSX/PDF) and verify it has the review-approval stamp.
4. Attempt to generate an artifact before review is complete; expected `403` or `409`.
5. Generate an artifact, then accept a new finding, then re-generate; verify the version bumps and the old artifact is immutable.
6. Verify generated artifacts do not contain invented numbers or uncited clauses.

---

## Scenario 29: Assistant behavior matrix

**Audit prompt mapping:** §4, §7

### Steps

1. Ask a question about an extracted deadline; verify the answer cites `[p<page>]`.
2. Ask an off-topic question (e.g. "What is the weather?"); verify a polite refusal.
3. Ask "Should we bid?"; verify the response contains the factor table and a "commercial judgment call" banner.
4. Send a prompt-injection attempt through the assistant chat; verify refusal.
5. Ask a question while `TS_OPENROUTER_API_KEY` is unset; verify deterministic tool fallback or refusal.
6. Start a chat session, add messages, and verify `/api/assistant/sessions/{id}/messages` returns history.
7. Verify message counts respect free/paid caps and metered usage is logged.

---

## Scenario 30: Billing webhook and subscription lifecycle

**Audit prompt mapping:** §4, §7, §8

### Steps

1. Complete a checkout and capture the client redirect.
2. Verify the subscription is **not** activated by the redirect alone.
3. Send a valid billing webhook with the correct secret; verify subscription status updates.
4. Send an invalid webhook (wrong signature, duplicate event, malformed body); verify rejection.
5. Upgrade from `free` to `pro`; verify invoice, seat limit, and feature flags.
6. Downgrade; verify proration or credit handling.
7. Cancel subscription; verify workspace reverts to `free` at period end or immediately depending on policy.
8. Verify invoice sequential numbering and GST computation (CGST/SGST vs IGST).

---

## Scenario 31: Notifications and preferences

**Audit prompt mapping:** §4, §8

### Steps

1. Create an opportunity with a deadline 2 days away; trigger the deadline digest and verify the notification is queued.
2. Create an opportunity with a deadline in the past; verify no notification is sent.
3. Disable email notifications in preferences; verify email channel is skipped.
4. Disable SMS notifications; verify SMS channel is skipped.
5. Trigger the digest twice for the same deadline window; verify deduplication (one notification per user per opportunity per window).
6. Verify notification content includes the opportunity title, deadline, and a link.

---

## Scenario 32: Admin, audit, and governance

**Audit prompt mapping:** §3, §7, §8

### Steps

1. As super-admin, list all users and verify pagination.
2. List all workspaces and verify each workspace has an owner and creation date.
3. View the audit log and filter by `actor_id`, `workspace_id`, `action`.
4. Verify the audit log cannot be modified by any API.
5. Impersonate a normal user calling `/api/admin/*`; expected `403`.
6. Verify the `CODEOWNERS` and branch-protection rules are present in the repo.
7. Run `alembic upgrade head` and `alembic downgrade base` cleanly on a fresh database.

---

## Scenario 33: Security — authentication bypass and injection

**Audit prompt mapping:** §7

### Steps

1. Attempt to access `/api/auth/export` without authentication; expected `401`.
2. Try to set `is_superadmin=true` during sign-up or profile update; verify the server ignores it.
3. Send `DELETE /api/auth/account` with an empty password; expected `400`.
4. Pass a malformed JWT (wrong signature, expired, missing claims); verify `401`.
5. Send SQL injection patterns in opportunity title, search query, and file name; verify no SQL errors or unexpected data leakage.
6. Send XSS payloads in opportunity title and finding comments; verify they are escaped or stripped in API response and rendered UI.
7. Send a `Content-Type: application/json` request with XML/XXE payload; verify safe rejection.

---

## Scenario 34: Security — IDOR and cross-tenant isolation

**Audit prompt mapping:** §5, §7

### Steps

1. User A creates opportunity `O1`. User B (same workspace) can access `O1`.
2. User C (different workspace) attempts `GET /api/opportunities/{O1}`; expected `403` or `404`.
3. User C attempts `POST /api/review/opportunities/{O1}/findings/{fid}`; expected `403`/`404`.
4. User C attempts `GET /api/billing/invoices` with a forged `workspace_id` header; verify only their own invoices are returned.
5. Test every list endpoint (`/api/opportunities`, `/api/findings`, `/api/billing/invoices`, `/api/team/members`) with multiple tenants and verify no leakage.
6. If PostgreSQL is used, run direct SQL as a non-superuser and verify RLS blocks reads/writes across `workspace_id`.

---

## Scenario 35: Security — file and request abuse

**Audit prompt mapping:** §7

### Steps

1. Upload a file named `<script>alert(1)</script>.pdf`; verify safe filename in storage and response.
2. Upload a `.zip` bomb / very large compressed file; verify `413` or early abort.
3. Upload a `.pdf` that contains an embedded executable; verify it is stored but not executed and antivirus scan (if enabled) quarantines or rejects it.
4. Send `1000` rapid login attempts from one IP; verify rate-limit response (`429`) or account lockout.
5. Send `1000` rapid API requests with a valid token; verify rate-limit response.
6. Try to read `/etc/passwd` or `..\..\web.config` through any file endpoint; verify `404`/`400`.

---

## Scenario 36: Accessibility and UI

**Audit prompt mapping:** §4, §7

### Steps

1. Run `npm run a11y` after `npm run build`; verify 0 critical/serious WCAG 2.1 AA violations.
2. Navigate every page using only the keyboard (Tab/Enter/Escape); verify focus order and visible focus indicators.
3. Verify form inputs have associated `<label>` or `aria-label`.
4. Run the UI through a screen reader (or `axe-core` + NVDA/JAWS checklist) and verify headings, landmarks, and button labels are announced.
5. Test color contrast on all text/background combinations in the default Tailwind theme.

---

## Scenario 37: Performance and load

**Audit prompt mapping:** §8

### Steps

1. Upload a 10 MB tender PDF and measure ingestion time; expected under 60 seconds in dev.
2. Upload a 50,000-row BOQ and measure BOQ check time; expected under 30 seconds.
3. Create 1,000 opportunities and measure `GET /api/opportunities` response time with `page_size=50`; expected under 500 ms.
4. Run 10 concurrent risk reviews on the same opportunity; verify no race conditions or duplicate findings.
5. Run 50 concurrent logins and verify rate limiting and DB connection pool hold.
6. Measure `GET /api/health/ready` response time; expected under 200 ms.

---

## Scenario 38: Concurrency and race conditions

**Audit prompt mapping:** §6, §7, §8

### Steps

1. Two users edit the same opportunity simultaneously; verify last-write-wins or optimistic locking behavior and no 500 errors.
2. Two admins invite the last available seat at the same time; verify one succeeds and the other gets `seat_limit`.
3. Two users accept the same invitation token concurrently; verify only one succeeds.
4. Two users call `POST /api/billing/checkout` for the same workspace; verify one checkout session is active at a time or handled idempotently.
5. Two risk reviews run concurrently; verify findings are not duplicated.

---

## Scenario 39: Data integrity and migrations

**Audit prompt mapping:** §2, §6, §8

### Steps

1. Run `alembic upgrade head` on a fresh database and verify all tables are created.
2. Run `alembic downgrade -1` repeatedly to base and back to head; verify no errors.
3. Verify foreign keys and constraints match `Base.metadata` (e.g. `users.phone` unique, `workspaces.owner_id` FK).
4. Delete a user and verify cascade deletes `workspaces`, `refresh_tokens`, `workspace_members`, `project_members`, `password_resets`, `verifications`.
5. Delete an opportunity and verify related `documents`, `clauses`, `findings`, `audit_log` rows are handled per policy.
6. Verify `amount_exposure`, `invoice.total`, `boq.amount` are stored as integers (paise) in the DB.

---

## Scenario 40: Privacy, GDPR, and data export/erasure

**Audit prompt mapping:** §3, §5, §7

### Steps

1. `POST /api/auth/export` for an owner of two workspaces; verify the export contains the user profile and all workspace-scoped rows for both workspaces.
2. Verify the export does **not** contain other users' data or other workspaces' data.
3. `DELETE /api/auth/account` with correct password and `confirm: true`; verify the user, memberships, refresh tokens, and owned workspace data are removed.
4. Verify the audit log still references the deleted user by anonymized ID or hashed reference (or by ID if append-only audit permits).
5. Verify exported JSON is machine-readable and contains `created_at` timestamps in ISO 8601.
6. Test export without auth → `401`; with wrong password on deletion → `400`.

---

## Scenario 41: Integrations — OpenRouter and LLM

**Audit prompt mapping:** §2, §4, §7

### Steps

1. With a valid `TS_OPENROUTER_API_KEY`, run risk review and verify `OpenRouterClassifier` returns findings.
2. With `TS_OPENROUTER_MODEL=openrouter/free`, run risk review and verify the `model` in the response is a free model.
3. With an invalid/expired key, verify the classifier fails closed (returns empty list) and the app stays healthy.
4. With `TS_OPENROUTER_MODEL` set to a non-existent slug, verify graceful error and fallback.
5. Verify no LLM prompt or response is logged with PII or full tender text.

---

## Scenario 42: Integrations — storage (MinIO/S3)

**Audit prompt mapping:** §2, §7, §8

### Steps

1. Start MinIO locally and configure `TS_STORAGE_TYPE=s3` with MinIO endpoint.
2. Upload a document; verify the object appears in the MinIO bucket.
3. Download the document and verify bytes match.
4. Restart the backend with a fresh bucket; verify uploads still work.
5. Configure `TS_STORAGE_TYPE=local` and verify files land in `TS_STORAGE_DIR`.
6. Test with `TS_S3_ENDPOINT_URL` using HTTPS and custom DNS.

---

## Scenario 43: Integrations — Redis and Celery

**Audit prompt mapping:** §2, §8

### Steps

1. Start Redis locally and set `TS_REDIS_URL`.
2. Trigger a long ingestion job and verify it is queued in Celery.
3. Verify the deadline-digest scheduler runs from Celery beat.
4. Stop Redis and verify the app degrades to in-memory fallback (with warnings) and still serves requests.
5. Restart Redis and verify queued tasks resume (if persistence enabled) or new tasks queue correctly.

---

## Scenario 44: Integrations — email and SMS (real and fallback)

**Audit prompt mapping:** §2, §4, §8

### Steps

1. Configure `TS_SES_*` + `TS_EMAIL_FROM` and sign up; verify a real email arrives.
2. Configure `TS_MSG91_*` and sign up; verify a real SMS arrives.
3. Without credentials, verify the console fallback prints the OTP and the flow still completes.
4. Test email verification with a malformed token; expected `400`.
5. Test mobile verification with a non-Indian number when MSG91 sender is India-only; expected `400` or fallback.

---

## Scenario 45: Integrations — billing webhooks

**Audit prompt mapping:** §7, §8

### Steps

1. Configure Razorpay test keys and webhook secret.
2. Create a checkout, capture the `razorpay_payment_id`, and send Razorpay's test webhook.
3. Verify the invoice and subscription status update.
4. Repeat with Stripe and `TS_STRIPE_WEBHOOK_SECRET`.
5. Send a webhook with a forged signature; verify `400` and no state change.
6. Send a duplicate event ID; verify idempotent handling.

---

## Scenario 46: Error handling and observability

**Audit prompt mapping:** §8

### Steps

1. Stop the database and call `GET /api/health/ready`; verify `503` with a clear JSON body.
2. Trigger an unhandled exception and verify it is captured in Sentry (when `TS_SENTRY_DSN` is set).
3. Verify logs include `request_id`, `workspace_id`, `user_id`, and `duration_ms` where applicable.
4. Verify `GET /api/health/metrics` includes `http_requests_total`, `http_request_duration_seconds`, and module-specific counters.
5. Verify 404 responses are JSON (`{"detail":"Not Found"}`) and not HTML.

---

## Scenario 47: Backup, restore, and disaster recovery

**Audit prompt mapping:** §8

### Steps

1. Create an opportunity, upload documents, and run risk review.
2. Take a PostgreSQL dump (`pg_dump`) and a storage backup.
3. Restore to a fresh database and storage bucket.
4. Verify all opportunities, documents, clauses, findings, and audit logs are restored.
5. Verify file hashes match after restore.
6. Verify `alembic upgrade head` runs cleanly on the restored DB.

---

## Scenario 48: Cross-browser and device matrix

**Audit prompt mapping:** §4

### Steps

1. Run the sign-up/login flow in Chrome, Firefox, and Safari.
2. Run on a mobile viewport (360x640, 390x844, 768x1024) and verify no horizontal overflow.
3. Test with JavaScript disabled partially (e.g. network throttling); verify server-rendered pages still show.
4. Test with `localStorage` cleared and verify no crash.

---

## Scenario 49: Configuration and environment guards

**Audit prompt mapping:** §2, §7, §8

### Steps

1. Start the app with `TS_ENV=prod` and `TS_CORS_ORIGINS=*`; verify startup fails or logs a fatal guard error.
2. Start with `TS_ENV=prod` and no `TS_JWT_PRIVATE_KEY`; verify startup fails.
3. Start with `TS_ENV=prod` and no `TS_RAZORPAY_WEBHOOK_SECRET`/`TS_STRIPE_WEBHOOK_SECRET`; verify startup fails (if billing enabled).
4. Start with `TS_ENV=dev` and missing keys; verify dev startup succeeds with warnings.

---

## Scenario 50: Fuzz and exploratory

**Audit prompt mapping:** §7

### Steps

1. Send random Unicode strings (emoji, RTL, zero-width joiners) in text fields; verify storage and display.
2. Send very long strings (10,000 chars) in title/description; verify truncation or `400`.
3. Send negative numbers, zero, and very large numbers in numeric fields; verify validation.
4. Rapidly alternate between two workspaces and verify tokens remain valid for the active workspace.
5. Close the browser mid-upload and verify tus resume on reopen.

---

## Scenario coverage matrix

| # | Area | Audit prompt sections |
|---|---|---|
| 1–3 | Auth / MFA | §3, §7 |
| 4–5 | Workspace / tenant isolation | §3, §5, §7 |
| 6–9 | Ingestion / storage | §2, §4, §6 |
| 10–11 | Risk / BOQ | §4, §6, §7 |
| 12–14 | Review / baseline / artifacts | §4, §6, §7 |
| 15 | Assistant | §4, §7 |
| 16–18 | Billing / notifications | §4, §7, §8 |
| 19–21 | Admin / security | §3, §5, §7, §8 |
| 22–24 | Accessibility / performance / concurrency | §4, §7, §8 |
| 25–26 | Data integrity / privacy | §2, §3, §5, §6, §7 |
| 27–30 | Integrations | §2, §4, §7, §8 |
| 31–34 | Observability / DR / config / cross-browser | §8 |

Run scenarios in order where later scenarios depend on earlier ones, or use independent fixtures.

---

## Automation notes

- Use `Playwright` with `test.use({ baseURL: "http://localhost:3000" })`.
- Use the backend `TestClient` or `httpx` for API-only scenarios.
- Seed test data via `backend/tests/conftest.py` fixtures if running from pytest.
- Reset the database between scenarios with `alembic downgrade base && alembic upgrade head` or a transaction rollback.
- Capture screenshots and API response JSON for every failed assertion so the audit prompt can be fed concrete evidence.
