# TenderShield — Project Gap Analysis

**Date:** 2026-07-28
**Branch analysed:** `claude/dev-workflow-modules-58dpqw` (repo HEAD)
**Scope:** business model, monetization/payments/coupons, auth & registration,
multi-tenancy & security, architecture, frontend/UI/UX, code quality, ops.

This document records gaps found by reading the code, not by reading the specs.
Where the code and the spec/README disagree, the code is treated as the truth.

---

## 0. Verdict in one paragraph

The **domain engine is the strong half of this product** — ingestion, clause
segmentation, deterministic severity, quote verification, the three drafting
validators, the review gate and the findings register are real, tested (29 test
files) and architecturally clean. The **commercial half does not exist yet**.
There is no way for a user to pay, no enforcement of the paywall, no coupon or
discount concept at all, and the free-tier watermark that the pricing model
depends on is never applied. Separately, there are **three unmitigated
cross-tenant data leaks** and an **account-takeover path in password reset** that
must be closed before any real customer data lands in this system. The README's
"Phase-1 MVP, feature engine functionally complete" is accurate about the engine
and materially over-states the product.

**Rough state:** engine ~75% · security ~35% · monetization ~15% · frontend ~30%.

### Severity legend

| | Meaning |
|---|---|
| **P0** | Ship-blocker. Data leak, money leak, or account takeover. |
| **P1** | Product is not sellable / not usable without it. |
| **P2** | Real gap, degrades quality or scale, not a blocker. |
| **P3** | Polish / hygiene / future phase. |

---

## 1. Security & multi-tenancy — P0

`CLAUDE.md` §4 states: *"RLS / org isolation on every org-scoped table.
Cross-tenant leakage is company-ending."* Four of these findings violate that
invariant directly.

### 1.1 P0 — Any logged-in user can read any workspace's member list

`backend/app/modules/auth/router.py:215` — `GET /workspaces/{workspace_id}/members`
is guarded only by `current_principal` (any authenticated user). It passes the
**path** `workspace_id` straight to
`AuthService.list_workspace_members` (`service.py:310`), which filters on that
value alone. There is no check that the caller is a member of that workspace.

Response leaks every member's **email address and role**. Iterating workspace
UUIDs enumerates the customer base.

Not mitigated by RLS: `WorkspaceMember` (`auth/models.py:70`) does **not** use
`WorkspaceScopedMixin`, so it is absent from `WORKSPACE_SCOPED_TABLES` and no RLS
policy is ever created for it (see §1.4).

### 1.2 P0 — Same leak on project members, with no workspace filter at all

`router.py:266` — `GET /projects/{project_id}/members` →
`list_project_members` (`service.py:384`) filters on `project_id` only. The
workspace is never consulted, in the query or in a guard. `ProjectMember`
(`models.py:91`) is likewise not workspace-scoped, so again no RLS backstop.

### 1.3 P0 — Cross-tenant privilege escalation via member add

`router.py:202` — `POST /workspaces/{workspace_id}/members` uses
`require("admin")`, which checks the role **in the caller's own token**, then
calls `add_workspace_member(workspace_id, ...)` with the **path** workspace id
(`service.py:290`). An admin of workspace A can therefore add themselves — at
`owner` role — to workspace B and gain full access to another tenant's tenders.

`create_project` (`service.py:321`) does this correctly via `_workspace_member`;
the member routes simply never got the same check. That's the fix pattern.

### 1.4 P0 — RLS is configured in a way that does not actually isolate

`core/db.py:59` `rls_statements()` emits:

```sql
ALTER TABLE t ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON t USING (workspace_id = current_setting('app.workspace_id')::uuid);
```

Three defects:

1. **No `FORCE ROW LEVEL SECURITY`.** In PostgreSQL, RLS is bypassed for the
   table owner. Applications normally connect as the role that owns the schema
   (which is what `docker-compose.yml` and `alembic upgrade head` set up here),
   so in the default deployment **the policies have no effect whatsoever**.
2. **No `WITH CHECK` clause.** `USING` filters reads. Without `WITH CHECK`, an
   `INSERT`/`UPDATE` can write a row carrying another workspace's `workspace_id`.
3. **Key tables are outside the policy set.** `workspaces`, `workspace_members`,
   `project_members`, `users`, `refresh_tokens` and `password_resets` are plain
   `Base` subclasses, so `WORKSPACE_SCOPED_TABLES` never contains them and the
   migration (`e26e85245237_workspace_tenant.py:379`) never covers them.

Additionally, `bind_workspace_context` issues `SET LOCAL`, which is scoped to the
**current transaction**. Services in this codebase call `self.s.commit()`
mid-request (billing, auth and ingestion all do). After that commit the binding
is gone, and the next statement in the same request runs unbound — on a
FORCE-enabled database that fails closed with `unrecognized configuration
parameter`, which will surface as 500s the moment RLS is actually turned on.

**Net effect:** the isolation story today is "every query happens to filter by
`workspace_id` in Python." That is mostly true in the feature modules and false
in the three auth routes above.

### 1.5 P0 — Password reset returns the reset token in the HTTP response

`service.py:501` — `forgot_password` returns `{"ok": True, "token": raw}`, and
`router.py:158` returns that dict verbatim to an **unauthenticated** caller.
Anyone who knows a user's email address can call `POST /auth/forgot-password`,
read the token out of the response, and immediately call `POST /auth/reset-password`.
That is unauthenticated account takeover for every account in the system.

It is marked `# TODO: wire email delivery` and is genuinely convenient in dev,
but it is live on every deployment. Gate it behind an explicit
`TS_DEV_RETURN_TOKENS` setting that defaults to off, and fail startup if it is on
while `TS_ENV=production`.

`create_invitation` (`service.py:416`) has the same shape. It is admin-only, so
P2 rather than P0, but it should move to the same switch.

### 1.6 P1 — Password reset does not revoke sessions

`reset_password` (`service.py:503`) sets the new hash and marks the token used.
It never revokes the user's refresh-token families. An attacker who has a session
keeps it after the victim resets their password — which defeats the main reason
users reset passwords. Call `_revoke_family` for every family of that user.

### 1.7 P1 — MFA is enrollable but never enforced

`login()` (`service.py:71`) issues tokens immediately on password match. It never
reads `user.mfa_method`. `POST /auth/mfa/verify` (`router.py:324`) requires an
already-valid access token and returns a bare `true`/`false` — it issues no
step-up token and nothing consumes its result. So enrolling in MFA changes
nothing about the security of the account.

Two more issues in the same area:
- `mfa_enroll` (`service.py:468`) overwrites `mfa_totp_secret` on every call with
  no re-authentication, so anyone holding a stolen access token can re-enroll MFA
  to a device they control.
- No TOTP replay guard (a code stays valid for its whole window) and no recovery
  codes, so a lost authenticator means a lost account.

### 1.8 P1 — No rate limiting or lockout anywhere

`grep` for rate-limit/lockout/throttle across `backend/app` returns nothing.
`/auth/login`, `/auth/signup`, `/auth/forgot-password` and `/auth/reset-password`
are all unthrottled. Password brute-force, email enumeration by timing, and
reset-token grinding are all open. Argon2id makes online guessing slow, which
also makes `/auth/login` a cheap CPU-exhaustion DoS.

### 1.9 P1 — Upload reads the whole body into memory before the size check

`ingestion/router.py:121`:

```python
data = await file.read()
if len(data) > MAX_UPLOAD_BYTES:   # 2 GB
    raise HTTPException(413, "file_too_large")
```

The 2 GB cap is enforced *after* buffering the entire upload in RAM. A handful of
concurrent large uploads OOMs the worker. Stream to disk with a running byte
count, or enforce the limit at the reverse proxy.

Also missing on this path: content-type / extension allowlist, magic-byte
sniffing, malware scanning, and a per-workspace storage quota.

### 1.10 P2 — Other security gaps

- **`TS_CORS_ORIGINS` defaults to `*`** (`core/config.py:27`). Fine for dev,
  dangerous as a production default — make production startup refuse `*`.
- **JWT keypair is ephemeral when unset** (README). A restart silently
  invalidates every session; two replicas issue mutually unverifiable tokens.
  Should be a hard startup failure outside dev.
- **No account-deletion / data-export endpoints.** DPDP Act (India) gives data
  principals erasure and access rights; there is no code path for either.
- **No secrets-scanning, dependency-audit or SAST step in CI** (`.github/workflows/ci.yml`).
- **Audit log covers review only** (`review/service.py:36`). Login, permission
  changes, billing events and exports are not audited.

---

## 2. Monetization: payments, plans, coupons — P0/P1

This is the weakest area of the project and the one that most directly blocks
revenue. The business model in `specs/000-product-overview.md` §Business model —
one free watermarked review, then ₹7,500 paygo / ₹24,999 Pro / ₹74,999 Scale —
is **not enforceable in the product as built**.

### 2.1 P0 — The paywall is never enforced

`BillingService.authorize_review` (`billing/service.py:52`) contains correct,
tested metering logic. The only caller in the entire codebase is its own HTTP
endpoint, `POST /api/billing/authorize-review` (`billing/router.py:58`).

`POST /api/risk/opportunities/{id}/run` (`risk/router.py:23`) — the endpoint that
actually performs a review — **never calls it**. Neither does BOQ, drafting or
export. And `frontend/lib/api.ts` never calls the billing endpoint at all.

So the paywall is an opt-in courtesy that no client is obliged to observe. Any
user on the free plan can run unlimited reviews forever by using the product
normally. Metering must move into the server-side review path (ideally as an
event-bus subscriber or a shared `billing.authorize` capability resolved through
the registry, so the module boundary in `CLAUDE.md` §2 is preserved).

### 2.2 P0 — The free-tier watermark is never applied

`Grant.watermark` is set to `True` for the free review (`plans.py:52`) and echoed
in the API response (`router.py:70`). `grep -rn "watermark" backend/app` finds no
other reference — nothing in `export/render.py` consumes it. The free review
therefore produces a **clean, unwatermarked, fully sellable Bid Review Pack**.

Since the free tier is deliberately a complete review (Build Doc §706 — "crippled
trials die in contractor WhatsApp groups"), the watermark is the *only* thing
separating free from paid output. Without it there is no reason to ever pay.

### 2.3 P0 — There is no way to actually pay

`POST /api/billing/checkout` (`router.py:34`) does not call Razorpay. It returns
a `notes` dict and a note saying activation happens via webhook. No order id, no
subscription id, no amount, nothing a client SDK can open a checkout with. The
frontend has no billing calls at all (§4.1). The full journey is:

> paywall blocks a review → 402 with an upsell payload → **nothing**

There is no order creation, no client SDK integration, no return/cancel handling,
no payment-status polling, and no receipt.

### 2.4 P0 — Plan is taken from unvalidated `notes`, unbound to amount

`checkout` copies `body.plan` into `notes` with no validation against
`PLAN_LIMITS` (`router.py:49`). The webhook then trusts it:

```python
elif typ == "subscription.charged" and workspace_id:
    self._workspaces().set_plan(workspace_id, notes.get("plan", "pro"))   # service.py:161
```

Nothing ever checks that the amount paid matches the plan granted. Once a real
Razorpay integration exists, a customer who can influence the notes on their own
order pays for Pro and receives Scale. The webhook must resolve the plan from the
**provider's** subscription/plan id and verify `amount` against a server-side
price table, never from `notes`.

Related: `workspace_id` also comes from `notes`. A signed event carrying someone
else's workspace id would be applied to that workspace. Bind the workspace to the
order at creation time and look it up server-side.

### 2.5 P0 — Coupons, discounts, promo codes and trials do not exist

The user explicitly asked about coupons. `grep -rni "coupon|discount|promo|referral|trial"`
across the whole repo returns **zero product hits** — the only matches are the
word "promoted" in prose. There is no:

- coupon/promo-code model, table, redemption ledger or validation
- percentage or fixed-amount discount, first-N-months discount, or free-months
- referral credits (despite the GTM being explicitly WhatsApp/referral-driven,
  Build Doc §706)
- time-limited trial of a paid tier
- annual-vs-monthly pricing, or any annual discount
- volume/seat-based pricing
- pilot/design-partner comp accounts — which matters immediately, because the
  Phase-1 exit gate requires **3 paid conversions** and 10 real tenders, and the
  usual way to get those is discounted pilots

For an India-first, referral-led SMB motion this is a significant commercial gap,
not a nice-to-have. A minimum viable version: a `coupons` table (code, kind,
value, applies-to plans, max redemptions, per-workspace limit, valid window), a
`coupon_redemptions` ledger, server-side validation at checkout, and the discount
applied to the order amount *before* it reaches the provider.

### 2.6 P1 — GST invoicing is dead code

`billing/gst.py` implements CGST/SGST vs IGST correctly and generates the
statutory `TS/2026-27/000042` number format. **Nothing in the application calls
it** — the only importer is `tests/test_hardening.py:19`.

What actually happens (`service.py:89`):
- `invoice_number = f"INV-{inv.id:06d}"` — not the statutory FY series
- amount stored as a single `amount_minor` with **no tax breakdown**
- the `Invoice` model (`models.py:56`) has no `base_minor`, no CGST/SGST/IGST
  columns, no buyer GSTIN, no place of supply, no SAC code
- no PDF invoice is rendered and nothing is emailed
- the number is a global sequence, so gaps appear across workspaces and the
  total customer count leaks to any customer

A GST-registered Indian B2B customer cannot claim input credit from this, which
makes the product hard to expense. Wire `compute_invoice`/`invoice_number` into
`create_invoice`, add the tax columns, and render a PDF.

### 2.7 P1 — Webhook handles only four event types

`process_razorpay_webhook` (`service.py:148`) handles `order.paid`,
`subscription.charged`, `subscription.activated`, `subscription.halted|cancelled`.
Missing: `payment.failed`, `payment.captured`, `refund.created|processed`,
`subscription.pending`, `subscription.completed`, `subscription.updated`,
disputes/chargebacks. There is no dunning, no grace period (a halted subscription
drops straight to `free` mid-month), no proration on upgrade/downgrade, and no
refund path — so a refund silently leaves the customer on a paid plan.

### 2.8 P1 — Idempotency is bypassable

`service.py:177` — the `WebhookEvent` row is only written `if event_id`. An event
with a missing/empty id is processed **every time it is delivered**, and
providers retry. Combined with `order.paid` → `create_invoice`, that produces
duplicate invoices and duplicate credits. Reject events without an id, or key
idempotency off a hash of the raw body.

Also: `PaymentLog.amount_minor` and `.currency` (`models.py:35`) are declared and
never populated — the "append-only financial ledger" has no amounts in it. And
both `PaymentLog` and `WebhookEvent` fall back to `uuid.UUID(int=0)` when the
workspace is unknown, which collides with the `_NO_WORKSPACE` sentinel that
`AuthService._issue_tokens` (`service.py:229`) gives superadmins.

### 2.9 P1/P2 — Plan machinery that is declared but not wired

| Gap | Where |
|---|---|
| **Seat limits never enforced.** `PLAN_LIMITS` declares 2/3/10/25 seats; nothing reads `seats`. Unlimited members on any plan. | `plans.py:9` |
| **Top-ups can't be bought or consumed.** `authorize()` takes `has_topups` and no caller ever passes it; the upsell quotes a top-up price that has no purchase path. | `plans.py:41`, `61` |
| **Paygo can't complete.** `authorize_review` returns `requires_payment=True` and records nothing; with no order creation the paygo journey dead-ends. | `service.py:68` |
| **Stripe is absent.** The product overview promises "Razorpay (IN) + Stripe (GCC/UK) behind one interface". There is no provider interface — `BillingService` is Razorpay-specific end to end. The word `stripe` appears once, in a column comment. | `service.py:119` |
| **Monthly quota uses calendar months**, not billing anniversary, so a customer who subscribes on the 28th gets a near-empty first period. | `service.py:29` |
| **No usage-history or spend endpoint** — customers can't see what they consumed. | — |
| **Free-tier abuse is wide open.** Build Doc §706 requires one free workspace per verified phone plus a disposable-email blocklist. Neither exists; `signup` has no verification of any kind, so unlimited free reviews are one throwaway email away. | `service.py:53` |

---

## 3. Auth, login & registration — P1

Beyond the P0s in §1:

### 3.1 P1 — No email verification for password signup

`signup` (`service.py:53`) creates the user with `email_verified` defaulting to
`False` and never sends anything. `email_verified` is only ever set to `True` by
the Apple path (`service.py:184`). There is no verification email, no resend, no
gating of any feature on verification. This is both the free-tier abuse vector
(§2.9) and the reason deadline-digest notifications will bounce.

### 3.2 P1 — No way to switch workspaces

`login` picks a workspace with `select(WorkspaceMember).where(user_id == ...)`
and **no `ORDER BY`** (`service.py:80`) — for a user in several workspaces, which
one they land in is whatever the database returns first, and it can change between
logins. `GET /auth/workspaces` lists them, but there is **no endpoint to mint a
token for a different workspace**. A consultant working across three client
workspaces (persona P3 in the product overview) cannot reach two of them.

Needs `POST /auth/workspaces/{id}/switch` that verifies membership and re-issues
tokens, plus a workspace switcher in the UI.

### 3.3 P2 — Registration is thin

- Password policy is `min_length=8` only (`router.py:31`) — no complexity, no
  breach-corpus check, no maximum length guard before Argon2.
- No email format validation — `email: str`, not `EmailStr`, so `"not-an-email"`
  is accepted.
- No terms-of-service or privacy-policy acceptance capture. For a paid Indian B2B
  SaaS this should be recorded with a timestamp and version.
- No phone capture at all, despite Build Doc §706 building free-tier
  anti-abuse on verified phone numbers.
- No CAPTCHA / bot defense on signup.
- No `no_workspace` recovery: a user whose only membership is removed gets a hard
  `401 no_workspace` at login (`service.py:86`) with no way back in.

### 3.4 P2 — Social login is half-built

Apple Sign-In is implemented (`auth/apple.py`) but **has no frontend** — there is
no Apple button anywhere in `frontend/`, and `api.ts` has no Apple call. Google
OIDC and phone OTP are backlogged as TS-036 ("needs creds"). For an India-first
SMB product, **Google and phone OTP are the important ones and Apple is the least
important** — this looks like build order driven by what was implementable
offline rather than by user need.

### 3.5 P2 — Session lifecycle gaps

- No "log out everywhere" / active-session list.
- No idle timeout or absolute session lifetime.
- `RefreshToken` rows are never pruned — the table grows without bound.
- No login notification or new-device detection.

---

## 4. Frontend, UI/UX & dashboards — P1

9 pages, ~2.1k lines, 3 runtime dependencies (`next`, `react`, `react-dom`).
Against 20 backend modules this is a thin shell over a deep backend.

### 4.1 P0 — Zero billing UI

There is no pricing page, no plan comparison, no checkout, no payment method
management, no invoice list, no usage meter, no upgrade prompt, and no paywall
interstitial. `frontend/lib/api.ts` contains **no billing calls whatsoever** —
not `status`, not `checkout`, not `invoices`, not `authorize-review`.

A user literally cannot give this product money through its own interface.

### 4.2 P0 — The refresh token is thrown away

`components/session.tsx:27`:

```ts
const s = { token: t.access_token, role: t.role, workspaceId: t.workspace_id, ... };
```

`t.refresh_token` is never stored. Access tokens live 15 minutes
(`access_ttl_minutes`), so **every user is hard-logged-out 15 minutes after
login**, mid-review, with no refresh path and no 401 interceptor to catch it —
requests just start failing with raw error strings. On an 800-page tender pack
whose stated p95 is 25 minutes, the session expires before the review finishes.

This alone makes the app unusable for its own primary workflow.

### 4.3 P1 — Tokens in `localStorage`

`session.tsx:23,30` persists the session to `localStorage`. The file's own
comment concedes production wants an httpOnly cookie for the refresh token and
memory-only for the access token. Any XSS becomes a full account takeover, and
there is no CSP configured in `next.config.mjs`.

### 4.4 P1 — No dashboard

The user asked specifically about dashboards. There is none. `/opportunities`
(`app/opportunities/page.tsx`, 118 lines) is a flat list with a create box. There
is no landing dashboard showing:

- deadlines due this week across all opportunities (the deadline **wall** is
  per-opportunity only — the cross-tender view that would make this a daily-use
  product doesn't exist)
- open critical/high findings across the portfolio
- bid/no-bid pipeline state
- review-completion status per opportunity
- usage vs. plan quota
- team activity

The `analytics` backend module (`modules/analytics/`) is fully implemented with a
router and service and has **no frontend consumer at all**.

### 4.5 P1 — Nine backend modules have no UI

Implemented, routed, tested backend modules with zero frontend surface:

`billing` · `analytics` · `comparison` · `crossref` · `qualification` ·
`timeline` · `notifications` · `rulepacks` · `export` (partially — the download is
a raw `fetch` in the detail page, `app/opportunities/[id]/page.tsx:129`, not in
the API client)

Plus the auth surfaces with no UI: workspace CRUD, workspace switching, member
management, invitations (create *and* accept — an invited user receives a token
with no page to redeem it on), MFA enrollment, and the entire super-admin console
(`/auth/admin/*` exists server-side with no admin UI).

### 4.6 P2 — Design system & UI quality

- **No component library and no design system.** Tailwind utility classes are
  written inline in every page; `Field` is re-declared locally in `login/page.tsx:82`
  and again in other pages. There is no `Button`, `Input`, `Card`, `Modal`,
  `Toast` or `Table` primitive.
- **No design tokens beyond one colour.** `tailwind.config.ts` adds `ink` and
  little else; spacing, typography scale, elevation and state colours are ad hoc.
- **Login and signup share one page with a `useState` toggle** (`login/page.tsx:12`)
  and default to `signup`. There is no `/signup` route, so signup is not
  linkable, not shareable, and not analytics-trackable — which matters for a
  referral-led GTM.
- **No loading skeletons** — `busy` booleans swap button text only.
- **Errors are raw backend codes.** `err.message` renders strings like
  `free_exhausted` and `insufficient_role` directly to the user
  (`login/page.tsx:29`). No error-code → human-copy mapping.
- **No empty-state design**, no onboarding, no product tour, no first-run
  checklist.
- **No accessibility work**: no focus-visible styling, no ARIA on the tab strip
  (`opportunities/[id]/page.tsx:215`), no keyboard navigation, no contrast audit,
  no skip links.
- **No responsive/mobile consideration** — fixed `max-w-*` layouts and wide tables.
- **No dark mode.**
- **No i18n.** India-first B2B will want at least Hindi for site staff.
- **No frontend tests of any kind** — no Jest, Vitest, Testing Library or
  Playwright. CI runs `npm run build` only, so nothing verifies behaviour.
- **No error boundary, no `error.tsx`, no `not-found.tsx`, no `loading.tsx`.**
- **No SEO/meta/OG tags** on the marketing page, no sitemap, no analytics.

---

## 5. Architecture — P1/P2

The module system itself (`core/loader.py`, `core/registry.py`, `core/events.py`)
is genuinely well done: string-named capabilities, an event bus, graceful
degradation when a module is disabled, and `tests/test_architecture.py` enforcing
the no-cross-module-import rule. Keep it. The gaps are around it.

### 5.1 P1 — Everything is synchronous

`POST /risk/opportunities/{id}/run` (`risk/router.py:23`) runs the entire risk
engine inside the HTTP request. The stated NFR is **< 25 min p95 for an 800-page
pack** (`specs/000-product-overview.md` §Non-functional). No load balancer or
browser will hold that connection.

TS-034 (Celery + Redis) is backlogged as "needs Redis", but Redis is not the
blocker — there is no job model, no status endpoint, no progress streaming and no
retry/idempotency design for reprocessing. "Stream results" and "processing
continues offline" are NFRs that nothing in the current shape can satisfy.

### 5.2 P1 — Storage is local-disk only

`ingestion/storage.py` defines a `Storage` protocol and implements only
`LocalStorage`, writing under `settings.storage_dir`. The docstring names S3 with
SSE-KMS as the production adapter; it doesn't exist. Consequences: horizontal
scaling breaks (each replica sees only its own uploads), the `docker-compose`
deployment loses documents on container replacement, and there is no
encryption-at-rest, lifecycle policy, or ap-south-1 residency guarantee — the
last of which is an explicit NFR.

### 5.3 P2 — Operational blind spots

- **No structured logging, metrics or tracing.** Bare `logging` with no request
  ids, no correlation ids, no OpenTelemetry, no Sentry.
- **`/api/health` reports loaded modules but does not check the database.** A
  Postgres outage still returns healthy; no readiness/liveness split.
- **No migration for RLS on the tables missed in §1.4**, and no test that RLS
  actually isolates — `bind_workspace_context` is a documented no-op on SQLite
  and **CI runs on SQLite only** (`.github/workflows/ci.yml`), so the isolation
  guarantee is never exercised anywhere.
- **No backup/restore or disaster-recovery runbook**; `docs/deployment.md`
  doesn't cover RPO/RTO despite a 99.5% availability NFR.
- **No staging environment or deploy pipeline** — CI builds and tests, nothing
  deploys.
- **No LLM cost controls**: no token budget, no per-workspace spend cap, no
  caching of classifier calls, no circuit breaker if Anthropic is down, no model
  pinning strategy.
- **`_broken/` module** (`app/modules/_broken/`) is a deliberate loader-resilience
  fixture living in production source. It belongs in `tests/fixtures/`.

### 5.4 P2 — Data model

- **No soft delete or retention policy** on any table. Tender packs are
  commercially sensitive; there is no purge path and no retention clock.
- **`UsageEvent` has no unique constraint**, so the "race-safe metering" claimed
  in TS-022 is not actually race-safe — two concurrent review starts both pass
  the count check.
- **`Invoice.invoice_number` is assigned after `flush()`** (`service.py:112`)
  using the auto-increment id, with a random hex placeholder in between. Under
  concurrency the placeholder is fine but the sequence is global, not per-FY, and
  gaps are possible on rollback — GST requires a gap-free series.
- **No `updated_at`** on most tables; `TimestampMixin` provides `created_at` only.

---

## 6. Business & product gaps — P1/P2

### 6.1 P1 — The stated Phase-1 exit gate is not measurable yet

`specs/000-product-overview.md` §Phase gates requires deadline **F1 ≥ 0.95**, QS
acceptance **≥ 70%**, 10 real tenders, 3 paid conversions. Today:

- `evals/in-works/` holds one synthetic tender. There is no golden set of real
  tenders and no scoring harness wired into CI — `scripts/phase0_accuracy_test.py`
  is a standalone script.
- **Nothing instruments finding acceptance rate**, even though the review module
  already records accept/reject decisions in its audit log. The kill-gate
  ("finding acceptance <50% after two eval cycles") therefore cannot be evaluated
  from production data. This is a small change with high strategic value: it is
  the metric the whole phase plan turns on.
- 3 paid conversions cannot happen because payment doesn't work (§2.3).

The README is right that domain validation is "the real gate". The gap is that
the *instrumentation to measure it* isn't there either.

### 6.2 P2 — Rule-pack coverage is thin and unvalidated

`rulepacks/in-works/` holds the 5 seed patterns from TS-008, all
`confidence: unvalidated`. The product invariant says only validated patterns are
shown at Phase-1 exit, so as it stands a Phase-1-compliant UI would display
nothing. There is no rule-pack authoring UI, no versioning/rollback workflow, no
per-workspace custom rules, and no shadow-mode evaluation harness (Build Doc §834).

### 6.3 P2 — Commercial & legal surface missing

No terms of service, no privacy policy, no DPA, no SLA document, no refund/
cancellation policy (Razorpay requires published refund terms), no
subprocessor list, no security page. No DPDP Act compliance work: no consent
record, no data-principal request path, no breach-notification procedure, no
data-retention schedule.

### 6.4 P2 — Go-to-market surface missing

No marketing site beyond `app/page.tsx` (77 lines), no pricing page, no case
studies, no lead capture, no demo request, no in-product analytics
(activation, retention, funnel), no NPS/feedback capture, no support channel
(the `/help` page is static copy), no changelog for customers, and no referral
mechanics despite referral being the stated GTM.

---

## 7. What's genuinely good

Worth stating plainly, because it should not be traded away while fixing the above:

- **The module framework** — registry + event bus + graceful degradation, with an
  architecture test that actually enforces the import rule.
- **Determinism discipline** — severity scoring, BOQ arithmetic and date parsing
  are code, not LLM, exactly as the invariants require.
- **Quote verification and the three drafting validators** — the real product
  differentiator, and they exist.
- **The export review gate** — genuinely enforced (`export/service.py` raises
  `review_incomplete`), unlike the billing gate.
- **Backend test coverage** — 29 test files including architecture and migration
  up/down checks.
- **Documentation discipline** — spec-per-module, task IDs, changelog per session.
  Rare and valuable.

---

## 8. Suggested order of work

**Gate 1 — stop the leaks (before any real customer data).**
1. §1.1/§1.2/§1.3 — membership checks on all three workspace/project member routes.
2. §1.5 — put the reset-token-in-response behind a dev-only flag; fail startup in prod.
3. §1.4 — `FORCE ROW LEVEL SECURITY` + `WITH CHECK`; add the missing tables to
   `WORKSPACE_SCOPED_TABLES`; add a Postgres job to CI with a real cross-tenant test.
4. §1.6 — revoke refresh families on password reset.
5. §1.8 — rate-limit the four auth endpoints.
6. §1.9 — stream uploads; enforce the size cap before buffering.

**Gate 2 — make it possible to get paid.**
7. §2.1 — enforce metering inside the review path, not in a side endpoint.
8. §2.2 — apply the watermark in the export renderer.
9. §2.3/§2.4 — real Razorpay order/subscription creation; resolve plan and amount
   server-side, never from `notes`.
10. §4.1 — pricing page, checkout flow, paywall interstitial, invoice list, usage meter.
11. §2.6 — wire GST computation into invoices; add tax columns; render a PDF.
12. §2.5 — coupons/discounts: table, redemption ledger, checkout validation.

**Gate 3 — make it usable.**
13. §4.2 — store the refresh token; add a 401-refresh interceptor.
14. §3.2 — workspace switching, API and UI.
15. §4.4/§4.5 — portfolio dashboard; UI for invitations, members, MFA, export.
16. §3.1 — email verification and delivery (unblocks digests and anti-abuse).

**Gate 4 — scale and prove.**
17. §5.1 — async job pipeline with progress streaming.
18. §5.2 — S3 storage adapter.
19. §6.1 — instrument finding-acceptance rate; build the real-tender golden set.
20. §1.7 — enforce MFA at login with step-up tokens and recovery codes.
