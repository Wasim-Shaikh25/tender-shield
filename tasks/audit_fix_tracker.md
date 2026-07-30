# Audit Fix Tracker

Generated from `PRODUCTION_READINESS_AUDIT.md`. Maps every `TS-*` finding to a
requirement, recommended solution, and task ID.

| # | ID | Title | Severity | Release-blocking | Task ID(s) |
|---|---|---|---|---|---|
| 1 | TS-A01 | Any authenticated user can join any workspace as owner | **Critical** | **YES** | TS-095 |
| 2 | TS-A02 | Google sign-in grants `owner` to every user regardless of actual role | **Critical** | **YES** | TS-096 |
| 3 | TS-A03 | Row-Level Security is defined but structurally inoperative | **Critical** (conditional — see Q1 in §3.6) | **YES** | TS-097 |
| 4 | TS-B01 | Client controls the payment amount; the webhook activates plans without validating it | **Critical** | **YES** | TS-098 |
| 5 | TS-P02 | Rulepack patterns are still unvalidated; paying workspaces receive zero risk findings | **Critical** | Yes | TS-125 |
| 6 | TS-A04 | Workspace and project member lists are readable cross-tenant | **High** | **YES** | TS-099 |
| 7 | TS-A05 | Google sign-in with an existing email raises an unhandled 500 | **High** | **YES** (a permanent lockout for affected users) | TS-100 |
| 8 | TS-I01 | Uploads are fully buffered in memory before any size check | **High** | **YES** at "millions of users" scale | TS-101 |
| 9 | TS-I02 | SSE progress endpoint busy-spins a CPU core per connected client | **High** | **YES** if async processing is enabled at launch | TS-102 |
| 10 | TS-B02 | Webhook processing is not atomic; idempotency check is racy | **High** | No — but fix before meaningful payment volume | TS-105 |
| 11 | TS-F01 | Frontend/backend contract mismatch breaks the session provider | **High** | **YES** — likely a blank screen after sign-in | TS-103 |
| 12 | TS-O01 | Rate limiting is ineffective across instances and behind a proxy | **High** | **YES** — the brute-force control does not function as designed | TS-104 |
| 13 | TS-A06 | `switch_workspace` does not persist the rotated refresh token | **High** | Yes | TS-122 |
| 14 | TS-A07 | `POST /api/auth/resend-verification` returns raw verification token | **High** | Yes | TS-123 |
| 15 | TS-O04 | Backend Dockerfile omits required optional extras | **High** | Yes | TS-124 |
| 16 | TS-A10 | `create_invitation` accepts arbitrary `project_id`; `accept_invitation` does not verify project ownership | **High** | **YES** | TS-129 |
| 17 | TS-I04 | Synchronous extraction blocks the async event loop in `upload_document` | **High** | **YES** | TS-133 |
| 18 | TS-I05 | BOQ run endpoint accepts unbounded CSV payloads | **High** | **YES** | TS-134 |
| 19 | TS-F02 | Session provider keeps a stale workspace list after switch/refresh | **High** | **YES** | TS-135 |
| 20 | TS-R02 | Risk classifier uses an invalid default Anthropic model name | **High** | **YES** | TS-136 |
| 21 | TS-O02 | No observability: no metrics, no tracing, no error tracking, no documented backups | Medium | No | TS-108 |
| 22 | TS-I03 | tus resumable upload is non-functional and not multi-instance safe | Medium | No | TS-110 |
| 23 | TS-N01 | Deadline alerts re-send daily with no deduplication, via an N+1 scan | Medium | No | TS-111 |
| 24 | TS-P01 | Untrusted tender text reaches the LLM without delimiting or neutralization | Medium | No | TS-112 |
| 25 | TS-S01 | Virus scanning is a no-op stub | Medium | No | TS-113 |
| 26 | TS-X01 | Cross-module foreign key violates the stated architecture and breaks module-subset boot | Medium | No | TS-114 |
| 27 | TS-B03 | Seat limits are defined but never enforced | Medium | No | TS-109 |
| 28 | TS-S02 | Production startup guard is incomplete | Medium | No | TS-115 |
| 29 | TS-O03 | No branch protection, no CODEOWNERS, no default branch convention | Medium | No | TS-120 |
| 30 | TS-A08 | Invitation tokens stored in plaintext | **Medium** | No | TS-126 |
| 31 | TS-A09 | TOTP enrollment does not require a verification code | **Medium** | No | TS-127 |
| 32 | TS-R01 | Risk classifier uses brittle string slicing and no schema validation | **Medium** | No | TS-137 |
| 33 | TS-D02 | `days_to_submission` mixes UTC and local time for naive deadlines | **Medium** | No | TS-138 |
| 34 | TS-Q01 | Qualification matrix marks missing criteria as `not_met` with HIGH severity | **Medium** | No | TS-139 |
| 35 | TS-X02 | BOQ engine relies on DuckDB reading `df` from caller scope | **Medium** | No | TS-140 |
| 36 | TS-A11 | Cross-reference search loads all clauses regardless of `limit` | **Medium** | No | TS-141 |
| 37 | TS-I06 | `confirm_deadline` does not verify the deadline belongs to the opportunity | **Medium** | No | TS-142 |
| 38 | TS-B05 | Baseline `freeze` has a race condition on `version` numbering | **Medium** | No | TS-143 |
| 39 | TS-S03 | Uploaded filename can inject `Content-Disposition` header in file download | **Medium** | No | TS-144 |
| 40 | TS-A13 | Assistant agent has no output guard and includes user prompt verbatim | **Medium** | No | TS-145 |
| 41 | TS-N02 | Notifications deadline-alert scheduler calls a missing `WorkspaceAdmin` method | **Medium** | No | TS-146 |
| 42 | TS-I07 | `register_document` accepts unbounded `sample_text` and processes it synchronously | **Medium** | No | TS-147 |
| 43 | TS-I08 | Async `process_document` Celery task does not classify, segment clauses, update the submission deadline, or run OCR | **Medium** | No | TS-148 |
| 44 | TS-A14 | Assistant agent uses an invalid default Anthropic model name | **Medium** | No | TS-149 |
| 45 | TS-A15 | Review audit trail endpoint ignores `opportunity_id` | **Medium** | No | TS-150 |
| 46 | TS-B06 | `Artifact.version` uses a non-atomic read-modify-write increment | **Medium** | No | TS-151 |
| 47 | TS-D03 | Timeline ICS export appends `Z` to naive or local datetimes; synthetic `tender_published` uses `created_at` | **Medium** | No | TS-152 |
| 48 | TS-S04 | `LocalStorage` async methods perform synchronous file I/O | **Medium** | No | TS-153 |
| 49 | TS-O05 | Production guard for CORS and allowed hosts can be bypassed with a comma-separated wildcard | **Medium** | No | TS-154 |
| 50 | TS-B07 | Stripe checkout uses hardcoded `example.com` redirect URLs | **Medium** | No | TS-155 |
| 51 | TS-B08 | Stripe webhook verifier swallows all exceptions and returns `None` | **Medium** | No | TS-156 |
| 52 | TS-I09 | tus endpoints perform synchronous file I/O and `OPTIONS` returns a non-compliant empty body | **Medium** | No | TS-157 |
| 53 | TS-A16 | `POST /api/review/findings/{finding_id}` does not scope by opportunity | **Medium** | No | TS-158 |
| 54 | TS-C01 | `Finding.amount_exposure` and monetary thresholds are stored/extracted as `float` major units, violating the minor-units invariant | **Medium** | No | TS-159 |
| 55 | TS-I10 | XLSX/CSV text extraction does not emit page markers, so spreadsheet-derived deadlines and clauses lose page provenance | **Medium** | No | TS-160 |
| 56 | TS-A17 | Email/password login selects an arbitrary workspace for multi-workspace users | **Medium** | No | TS-161 |
| 57 | TS-R03 | Severity evaluator silently defaults missing facts to `0` | **Medium** | No | TS-162 |
| 58 | TS-L01 | `/api/health/details` is unauthenticated outside production. | — | No | TS-118 |
| 59 | TS-L02 | No pagination on any list endpoint. | — | No | TS-118 |
| 60 | TS-L03 | Accessibility not established. | — | No | TS-119 |
| 61 | TS-L04 | `pip install -e ".[dev]"` fails on Debian system Python. | — | No | TS-120 |

---

## TS-A01 — Any authenticated user can join any workspace as owner

**Severity:** **Critical**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-095  
**Location:** - `backend/app/modules/auth/router.py:394-406` — `add_workspace_member`
- `backend/app/modules/auth/service.py` — `add_workspace_member(workspace_id, email, role)`
- Same pattern: `router.py:547-560` (`POST /members`, legacy route)  
**Status:** Confirmed Defect — **reproduced end-to-end**  

### Requirement / Impact

*Technical:* Total collapse of tenant isolation for every workspace whose UUID is known.
Read and write access to all workspace-scoped data. Self-granted `owner` allows locking the
legitimate owner out by role downgrade.

*Business:* Company-ending by the project's own standard (`CLAUDE.md` §4). Tender packs are
pre-award commercial documents; leakage between contractors bidding the same tender is direct
competitive harm and near-certain contractual breach. Under India's DPDP Act and GDPR this is a
reportable personal-data breach. The `audit_log` would not record it (§3.5 item 6).

### Root cause

Authorization is *authenticated but not associated*: the role guard proves the caller has a
role **somewhere**, and the handler then applies it **elsewhere**. This is the classic
"role check without resource binding" defect. `create_project` in the same file gets it right
(`if not self._workspace_member(workspace_id, user_id): raise AuthError("not_workspace_member")`),
which shows the correct pattern already exists in the codebase and was simply not applied here.

### Evidence

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

### Recommended solution

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

### Regression risks

Medium. If any legitimate flow adds members to a workspace other than the token's active one,
it will now 404. Grep confirms only the two routes above and `accept_invitation` write
`WorkspaceMember`; `accept_invitation` is correctly driven by the invitation record and is
unaffected. The super-admin path must be exempted explicitly if platform operators are meant
to administer tenant workspaces.

### Tests to add

1. `test_cannot_add_member_to_foreign_workspace` — probe A, asserting 404 **and** that
   `GET /auth/workspaces` for the attacker is unchanged.
2. `test_cannot_grant_role_above_own_rank` — an `admin` may not mint an `owner`.
3. `test_legacy_members_route_uses_token_workspace`.
4. A parametrized test over **every** route carrying a `{workspace_id}` or `{project_id}` path
   parameter, asserting a foreign ID returns 404. This prevents the whole class from recurring.


## TS-A02 — Google sign-in grants `owner` to every user regardless of actual role

**Severity:** **Critical**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-096  
**Status:** Confirmed Defect — **reproduced end-to-end**  

### Requirement / Impact

*Technical:* Any user with the lowest role escalates to full workspace control by signing in
through a different, legitimate front door. Combined with TS-A01, an escalated `owner` can then
reach into other workspaces entirely.

*Business:* The role model — the basis of seat pricing and of every "who may approve this bid"
control — is unenforceable for Google users. A junior estimator can approve findings, generate
artifacts, alter billing, and remove the workspace owner.

### Root cause

Copy-paste from the first-sign-in branch, where `"owner"` is correct (a brand-new user *is*
owner of the personal workspace just created for them). The existing-user branch reuses the
same literal instead of reading the membership row.

### Evidence

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

### Recommended solution

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

### Regression risks

Low. Genuine owners still receive `owner` because their membership row says so. Users whose only
membership was implicitly assumed will now correctly receive their real role — which is the fix,
though it may surface as "Google users lost permissions" in support channels. Note it in release
notes.

### Tests to add

1. `test_google_login_preserves_membership_role` (probe C) — a `viewer` receives `viewer`.
2. `test_google_login_deterministic_workspace` — a multi-workspace user gets a stable workspace.
3. A parametrized test across all three providers asserting identical role/workspace resolution.

### Similar locations

against the same checklist. Grep for `"owner"` as a literal argument:
`grep -rn '"owner"' backend/app/modules/auth/service.py`.


## TS-A03 — Row-Level Security is defined but structurally inoperative

**Severity:** **Critical** (conditional — see Q1 in §3.6)  
**Release-blocking:** **YES**  
**Task ID(s):** TS-097  
**Location:** `backend/migrations/versions/e26e85245237_workspace_tenant.py:378-382`; `docker-compose.yml`  
**Status:** Confirmed Defect (by inspection) — **not verified against PostgreSQL** (§6.2)  

### Requirement / Impact

The database-level backstop for tenant isolation provides **no protection in the deployed
configuration**. Application-level `workspace_id` filters (which are consistent and good — §1.5)
are the *only* line of defence, so any single missing filter becomes a full isolation breach.
TS-A01 and TS-A04 are exactly that, and RLS did not contain either.

### Root cause

RLS was implemented as a code artifact and validated by asserting on generated SQL text, rather
than by executing it against PostgreSQL and observing that a cross-tenant read is actually
refused. Every one of the four defects would have been caught by a single integration test that
binds workspace A and then attempts to `SELECT` a workspace-B row.

### Evidence

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

### Recommended solution

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

### Tests to add

1. `test_rls_blocks_cross_workspace_select` — bind A, insert a row for B directly, assert A cannot see it.
2. `test_rls_blocks_cross_workspace_insert` — bind A, attempt to insert with B's `workspace_id`, assert rejection (this is the `WITH CHECK` test).
3. `test_rls_applies_to_table_owner` — connect as the owning role, assert the policy still applies (this is the `FORCE` test).
4. `test_unbound_session_reads_no_rows` — no `SET LOCAL`, assert empty rather than error.
5. `test_membership_tables_are_rls_covered` — assert `workspace_members` and `project_members` ∈ `WORKSPACE_SCOPED_TABLES`.

Add a PostgreSQL service container to `.github/workflows/ci.yml` and run these there. Without CI
coverage on PostgreSQL, this finding will silently regress.

### Similar locations

table with a `workspace_id` column appears in `WORKSPACE_SCOPED_TABLES`, so the mixin can never
be forgotten again.


## TS-B01 — Client controls the payment amount; the webhook activates plans without validating it

**Severity:** **Critical**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-098  
**Location:** `backend/app/modules/billing/service.py:161-173` and `:226-237`  
**Status:** Confirmed Defect (by inspection — end-to-end requires live provider credentials)  

### Requirement / Impact

*Technical:* Any workspace admin sets their own price. Invoices record the ₹1 actually paid, so
reconciliation shows a paid invoice and the books look internally consistent.

*Business:* Direct, unbounded revenue loss with no anomaly signal. Currency confusion compounds
it — `amount` is computed from an INR paise table while `currency` is derived from the workspace's
country, so a `GB` workspace is charged the paise figure denominated in GBP (₹4,999.00 → £4,999.00
or £49.99 depending on provider interpretation). That is a live billing-correctness bug even with
no attacker.

### Root cause

Price is treated as request data rather than server-owned reference data. `SUBSCRIPTION_PRICES_INR_PAISE`
exists in the codebase as the authoritative price list but is used only as a *default*, never as a
*constraint* — and never at all on the activation side.

### Evidence

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

### Recommended solution

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

### Regression risks

Medium. Any legitimate flow that passes `amount_minor` (discounts, proration, partial top-ups)
will break — see Q4 in §3.6. Grep confirms the frontend does not currently send it, so the
in-repo risk is low.

### Tests to add

1. `test_checkout_rejects_client_amount` — `amount_minor` in the body is ignored/rejected.
2. `test_checkout_rejects_unknown_plan` — including when an amount is supplied.
3. `test_webhook_underpayment_does_not_activate` — signed `subscription.charged` for ₹1 against `scale` leaves the plan unchanged.
4. `test_webhook_exact_payment_activates`.
5. `test_price_currency_matches_workspace_country` — a `GB` workspace is quoted GBP, not paise-as-GBP.

### Similar locations

`order.paid` with no amount check either: the same ₹1 attack buys a ₹7,500 pay-as-you-go review.
Fix both in one change.


## TS-P02 — Rulepack patterns are still unvalidated; paying workspaces receive zero risk findings

**Severity:** **Critical**  
**Release-blocking:** Yes  
**Task ID(s):** TS-125  
**Status:** Confirmed product blocker — by code and data inspection  


## TS-A04 — Workspace and project member lists are readable cross-tenant

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-099  
**Location:** `:462-469` (`list_project_members`); service methods `list_workspace_members` /
`list_project_members` in `auth/service.py`  
**Status:** Confirmed Defect — **reproduced end-to-end**  

### Requirement / Impact

*Technical:* Enumeration of every user's email address and role, workspace by workspace. Given a
workspace UUID, an attacker learns exactly who holds `owner` and `admin` — a targeting list for
TS-A01 and for phishing.

*Business:* Personal-data disclosure under GDPR/DPDP. Reveals which contractors are collaborating
on which projects — commercially sensitive in a competitive-bidding context. Notably, this
finding **makes TS-A01 substantially easier to exploit at scale**: an attacker who obtains one
workspace UUID can map the entire organisation before escalating.

### Root cause

associated with the caller. RLS would normally contain this, but `workspace_members` and
`project_members` carry no RLS policy (TS-A03 defect 4).

### Evidence

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

### Recommended solution

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

### Regression risks

so nothing currently consumes them.

### Tests to add

/ `{project_id}` route rejects foreign IDs" test from TS-A01.

### Similar locations

both `workspace_id` and `ProjectMember.user_id`, so it is safe; verified by reading the service.


## TS-A05 — Google sign-in with an existing email raises an unhandled 500

**Severity:** **High**  
**Release-blocking:** **YES** (a permanent lockout for affected users)  
**Task ID(s):** TS-100  
**Status:** Confirmed Defect — **reproduced**  

### Requirement / Impact

500 and can never use Google sign-in. The raw `IntegrityError` may surface in error tracking with
the email attached. On a per-request session this leaves the transaction dirty.

### Root cause

to an email lookup when the verified flag is set — so the correct pattern exists in the same file
and was not applied to Google.

### Evidence

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

### Recommended solution

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

### Regression risks

for an address it has not truly verified, linking grants access to the existing account. Gating on
`email_verified` is the industry-standard mitigation and matches the Apple path already shipped.

### Tests to add

`test_google_login_rejects_unverified_email_collision` (asserts 409, not 500, and no linking).

### Similar locations

*or* an existing `apple_id`; worth a security review of that branch under the same policy.


## TS-I01 — Uploads are fully buffered in memory before any size check

**Severity:** **High**  
**Release-blocking:** **YES** at "millions of users" scale  
**Task ID(s):** TS-101  
**Location:** `backend/app/core/storage.py` (`validate_and_store`, size check); `boq/router.py` upload route  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Because uploads are authenticated, a single compromised or malicious `estimator` account is
sufficient. At the stated scale this is also a routine-traffic capacity problem, not only an
attack.

### Root cause

guard. FastAPI's `UploadFile` spools to disk above a threshold, which mitigates but does not
eliminate this — disk is still consumed without limit, and `file.read()` pulls it all back into
RAM regardless.

### Evidence

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

### Recommended solution

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

### Regression risks

path (`tus.py`, `_finalize` → `file_path.read_bytes()`) — it has the same whole-file read, though
bounded by the per-upload `max_size`, so it is capped but still fully buffered.

### Tests to add

`test_upload_rejects_oversized_stream` (lying `Content-Length`);
`test_upload_accepts_at_limit`.

### Similar locations

`ingestion/tus.py` `_finalize`; `baseline/router.py` award-document upload.


## TS-I02 — SSE progress endpoint busy-spins a CPU core per connected client

**Severity:** **High**  
**Release-blocking:** **YES** if async processing is enabled at launch  
**Task ID(s):** TS-102  
**Status:** Confirmed Defect (by inspection)  

### Root cause

that would make polling cooperative.

### Evidence

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

### Recommended solution

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

### Regression risks

second of latency to progress updates, which is imperceptible for multi-second document processing.

### Tests to add

`test_sse_emits_progress_then_done`. A load test asserting CPU stays flat with 50 concurrent
streams would directly target the defect.

### Similar locations

occurrences found, so this is isolated.


## TS-B02 — Webhook processing is not atomic; idempotency check is racy

**Severity:** **High**  
**Release-blocking:** No — but fix before meaningful payment volume  
**Task ID(s):** TS-105  
**Status:** Probable Risk (by inspection; not reproduced under load)  

### Requirement / Impact

tax-filing errors — India GST filings are derived from invoice records). Partial application
produces states no code path expects, e.g. a plan set with no invoice.

### Root cause

invariant at the database level.

### Evidence

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

### Recommended solution

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

### Regression risks

`create_invoice` currently relies on `flush()` to obtain an id before setting `invoice_number`;
that still works inside a larger transaction, but the tests must be re-run carefully.

### Tests to add

`test_webhook_failure_rolls_back_completely`;
`test_webhook_retry_after_failure_applies` (the marker must not block a legitimate retry).

### Similar locations

`auth/service.py accept_invitation` has a comparable check-then-act on `invitation.used_at`,
allowing an invitation to be accepted twice concurrently (lower impact — idempotent in effect).


## TS-F01 — Frontend/backend contract mismatch breaks the session provider

**Severity:** **High**  
**Release-blocking:** **YES** — likely a blank screen after sign-in  
**Task ID(s):** TS-103  
**Location:** `backend/app/modules/auth/router.py:365-371`  
**Status:** Confirmed Defect (backend response shape verified empirically; frontend by inspection)  

### Requirement / Impact

users — cannot work. Most likely the app renders blank after sign-in. Since `SessionProvider`
wraps the application (`app/layout.tsx`), the blast radius is every authenticated page.

> **Not runtime-verified.** No browser was available (§1.6). The backend shape is confirmed
> empirically; the frontend consequence is traced through source. Reproduce in a browser before
> sizing the fix.

### Root cause

some places (`GET /auth/workspaces`) and wrapped objects in others (`GET /billing/invoices` →
`{"invoices": [...]}`), and the TypeScript client encodes one guess per endpoint with nothing
verifying it.

### Evidence

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

### Recommended solution

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

### Regression risks

tolerance first, then change the backend, avoiding a coordinated deploy).

### Tests to add

a frontend unit test rendering `SessionProvider` against a mocked response; an end-to-end
sign-in-and-switch test. **An end-to-end test would have caught this and no existing test could
have** — the backend tests assert on the current shape, and the frontend has no tests at all.

### Similar locations

actual backend response. `adminWorkspaces` (`api.ts:97`) expects `{workspaces}` from
`GET /auth/admin/workspaces` — verify `list_all_workspaces()` returns the wrapper. Given one
confirmed mismatch and no runtime validation anywhere, **assume others exist until checked.**


## TS-O01 — Rate limiting is ineffective across instances and behind a proxy

**Severity:** **High**  
**Release-blocking:** **YES** — the brute-force control does not function as designed  
**Task ID(s):** TS-104  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

not apply or locks out all legitimate users. Given TS-A01 and TS-A02 (which both need only one
authenticated account), effective login rate limiting is more than usually load-bearing here.

### Root cause

backend it was presumably copied from, invalid the moment state is shared. (b) is missing
`ProxyHeadersMiddleware`; `main.py` adds `HTTPSRedirect`, `TrustedHost`, `CORS`, and
`SecurityHeaders` but never trusts `X-Forwarded-For`.

### Recommended solution

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

### Regression risks

than breaking functionality — but the failure is silent, so add a startup log line recording the
resolved client IP strategy.

### Tests to add

`test_ratelimit_uses_forwarded_for_when_configured`;
`test_ratelimit_ignores_forwarded_for_when_hops_zero` (the anti-spoofing test);
`test_same_tick_attempts_both_counted`.

### Similar locations

`notifications/module.py:26` uses a Redis lock with a 23-hour timeout — correct there, but review
it alongside this fix.


## TS-A06 — `switch_workspace` does not persist the rotated refresh token

**Severity:** **High**  
**Release-blocking:** Yes  
**Task ID(s):** TS-122  
**Status:** Confirmed defect — reproduced end-to-end  


## TS-A07 — `POST /api/auth/resend-verification` returns raw verification token

**Severity:** **High**  
**Release-blocking:** Yes  
**Task ID(s):** TS-123  
**Status:** Confirmed defect — reproduced end-to-end  


## TS-O04 — Backend Dockerfile omits required optional extras

**Severity:** **High**  
**Release-blocking:** Yes  
**Task ID(s):** TS-124  
**Status:** Confirmed defect — by code inspection  


## TS-A10 — `create_invitation` accepts arbitrary `project_id`; `accept_invitation` does not verify project ownership

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-129  
**Location:** - `backend/app/modules/auth/router.py:472-485` — `create_invitation`
- `backend/app/modules/auth/service.py:514-550` — `create_invitation`
- `backend/app/modules/auth/service.py:552-599` — `accept_invitation`  
**Status:** Confirmed Defect — **reproduced end-to-end**  

### Requirement / Impact

*Technical:* Cross-tenant project membership injection. An attacker who knows or guesses any
project UUID can join that project and read its member list (which already has no workspace check
— see TS-A04).

*Business:* Compromises the confidentiality of project-team composition, which may reveal
competitors, subcontractors, or bid-partner relationships. Corrupts the `project_members` table
with rows whose `workspace_id` does not match the project they reference, creating a data-integrity
and incident-response problem.

### Root cause

The same "role check without resource binding" pattern as TS-A01/A04: the service validates the
caller's role in their own workspace but never checks that the `project_id` belongs to that
workspace. `Project.workspace_id` exists and is already checked in `add_project_member`, so the
correct pattern is available.

### Evidence

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

### Recommended solution

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

### Tests to add

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


## TS-I04 — Synchronous extraction blocks the async event loop in `upload_document`

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-133  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Combined with TS-I01 (fully-buffered upload), this is a practical DoS vector.

### Root cause

CPU-intensive operation inside an async route.

### Evidence

calls the synchronous, CPU-bound `extract_upload` directly:

```python
# backend/app/modules/ingestion/router.py:164
ocr = request.app.state.ctx.registry.get("ingestion.ocr")
text, ocr_status = extract_upload(file.filename, data, ocr)
```

`extract_upload` performs PDF parsing, table extraction, and optional OCR. Running it on the
main event loop blocks all other requests for the duration of the parse.

### Recommended solution

```python
text, ocr_status = await asyncio.to_thread(extract_upload, file.filename, data, ocr)
```

For production, consider making the non-async path queue to Celery (as the `?async=1` path does)
by default, and stream progress via the existing SSE endpoint.

### Tests to add

while a large PDF is parsed); `test_async_query_runs_in_thread`.

### Similar locations

text; the extraction is deferred to `BaselineService.store_award_document`, which is called from a
sync route so the concern is smaller. `boq/router.py:95-100` `upload_boq` calls `to_csv` on
parsed data inside an `async def` route and has the same pattern (see TS-X02).


## TS-I05 — BOQ run endpoint accepts unbounded CSV payloads

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-134  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

object, causing OOM or extremely long CPU consumption on every request. The `estimator` role is
required, but a compromised account or a single malicious user can crash the worker.

### Evidence

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

### Recommended solution

largest permitted CSV upload) and reject before `pd.read_csv`:

```python
class RunBody(BaseModel):
    csv: str = Field(..., max_length=5 * 1024 * 1024)
```

### Similar locations

so the raw upload path is safer; the BOQ text path bypasses those checks.


## TS-F02 — Session provider keeps a stale workspace list after switch/refresh

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-135  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

first switch/refresh. This undermines the multi-workspace support the session provider is meant
to provide.

### Root cause

the user's context changes.

### Evidence

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

### Recommended solution

```tsx
if (match) {
  setWorkspaces(all ?? workspaces);
}
```

### Tests to add

`switchWorkspace` response and asserting `activeWorkspace` matches the new workspace.

### Similar locations

list and are also affected.


## TS-R02 — Risk classifier uses an invalid default Anthropic model name

**Severity:** **High**  
**Release-blocking:** **YES**  
**Task ID(s):** TS-136  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Paying workspaces with an Anthropic key configured get empty risk findings. This breaks the product's primary value proposition and, combined with `TS-P02` (paid workspaces see only `validated` patterns), can leave users with zero risk output.

### Root cause

A placeholder model name was hardcoded and never replaced with a real default or a configurable setting.

### Evidence

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

### Recommended solution

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

### Regression risks

Low. The change only affects deployments with `ANTHROPIC_API_KEY` set, which are currently broken.

### Tests to add

1. `test_risk_classifier_with_invalid_model_fails_fast` — startup fails or the call raises a clear `ConfigurationError`.
2. `test_risk_classifier_valid_model_returns_findings` — with a mocked Anthropic client, `run_patterns` returns the expected findings.


## TS-O02 — No observability: no metrics, no tracing, no error tracking, no documented backups

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-108  
**Location:** `docs/deployment.md` (65 lines), whole repo  
**Status:** Design Concern  

### Requirement / Impact

`grep` for `backup`, `rollback`, `restore`, `monitor`, `alert`, `Sentry`, `observab` across
`docs/deployment.md` returns **zero matches**. There is no metrics endpoint, no structured logging
configuration, no trace propagation, and no error-tracking integration anywhere in the codebase.
`/api/health` returns a static `{"status": "ok", "version": "0.1.0"}` — it does not check database
connectivity, Redis, storage, or the Celery broker, so an orchestrator liveness probe reports
healthy while every dependency is down.

### Root cause

`grep` for `backup`, `rollback`, `restore`, `monitor`, `alert`, `Sentry`, `observab` across

### Recommended solution

add `prometheus-fastapi-instrumentator` for RED metrics; add Sentry (or
equivalent) for exceptions; make `/api/health` a real dependency check with a separate
`/api/health/live` for liveness vs `/api/health/ready` for readiness; document RPO/RTO, PostgreSQL
PITR configuration, S3 versioning, and a tested rollback procedure. Alert at minimum on 5xx rate,
webhook signature failures, Celery queue depth, and failed logins per account.


## TS-I03 — tus resumable upload is non-functional and not multi-instance safe

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-110  
**Location:** `backend/app/modules/ingestion/tus.py:34,90-115`  
**Status:** Confirmed Defect  

### Requirement / Impact

Three issues: (1) `tus_create` returns `{}` with HTTP 200 and **no `Location` header** — the tus
1.0 protocol requires `201 Created` plus `Location`, so a standard tus client cannot discover the
upload id and the flow is unusable; (2) `UPLOAD_DIR = pathlib.Path("/tmp/tender-shield-tus")` is
node-local, so a resumed `PATCH` routed to a different pod returns 404 — resumability, the entire
point of tus, does not survive load balancing; (3) no expiry or cleanup of abandoned `.part`
files, an unbounded disk leak on a `/tmp` filling silently. Also `_load_state`/`_file_path`
interpolate the `upload_id` path parameter into a filesystem path without validating it is a hex
UUID (low exploitability, but free to fix).

### Root cause

Three issues: (1) `tus_create` returns `{}` with HTTP 200 and **no `Location` header** — the tus

### Recommended solution

return `201` with `Location`; move chunk state to Redis or S3 multipart upload;
add a TTL sweeper; validate `upload_id` with `re.fullmatch(r"[0-9a-f]{32}", upload_id)`.


## TS-N01 — Deadline alerts re-send daily with no deduplication, via an N+1 scan

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-111  
**Location:** `backend/app/modules/notifications/module.py:47-82`  
**Status:** Confirmed Defect  

### Requirement / Impact

`_deadline_alert_tick` runs every 24 h and emails **every member** about **every unconfirmed
deadline** falling within the next 7 days. Nothing records that an alert was already sent, so the
same deadline generates an email to every member **every day for seven consecutive days**. A
workspace with 10 members and 5 live tenders averaging 4 deadlines each receives 200 emails/day.
The scan is also a nested N+1 (workspaces × opportunities × deadlines × members) with no
pagination, executed in a single session while holding a 23-hour Redis lock.

### Root cause

`_deadline_alert_tick` runs every 24 h and emails **every member** about **every unconfirmed

### Recommended solution

add a `deadline_alerts_sent(deadline_id, member_id, threshold_days)` table and
send only on threshold crossings (e.g. 7/3/1 days); batch the queries; add per-user notification
preferences (§3.5 item 9). See Q6 in §3.6 — confirm the intended cadence first.


## TS-P01 — Untrusted tender text reaches the LLM without delimiting or neutralization

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-112  
**Location:** `backend/app/modules/assistant/agent.py:31-46`  
**Status:** Design Concern  

### Requirement / Impact

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

### Root cause

`CLAUDE.md` §4 requires that "tender text is untrusted input — prompt-injection defenses apply

### Recommended solution

wrap document-derived content in explicit delimiters with a standing instruction
that content inside them is data and never instructions; strip or escape delimiter sequences from
the extracted text; keep the deterministic path (which needs no LLM) as the default. Add
adversarial fixtures to `evals/` containing injection attempts and assert the assistant does not
comply.


## TS-S01 — Virus scanning is a no-op stub

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-113  
**Location:** `backend/app/core/storage.py:200-202`  
**Status:** Confirmed Defect  

### Requirement / Impact

```python
def _scan_stub(_data: bytes) -> None:
    """Placeholder virus scan. Production should call a sandboxed scanner or API."""
    return
```

Called on every upload with `scan=True`, and does nothing. Uploaded files are stored and later
served back through `/api/files/{key}` with `Content-Disposition: attachment`, so browser-side
execution risk is limited — but the platform becomes a malware distribution channel between
collaborating contractors. Carried forward from the previous audit; still unaddressed.

### Root cause

```python

### Recommended solution

integrate ClamAV (via `clamd`) or an equivalent scanning API, run it in the async
processing path rather than the request path, and quarantine rather than delete on detection so
false positives are recoverable. Fail closed in production if the scanner is unreachable.


## TS-X01 — Cross-module foreign key violates the stated architecture and breaks module-subset boot

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-114  
**Location:** `backend/app/modules/findings/models.py`  
**Status:** Confirmed Defect  

### Requirement / Impact

`CLAUDE.md` §2 states: "Foreign keys may reference core tables (orgs/users) but not another
module's tables directly; use IDs + events." `findings.opportunity_id` declares a foreign key to
`opportunities`, a table owned by the `ingestion` module.

**Reproduced during this audit:** enabling `findings` without `ingestion` raises
`sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 'findings.opportunity_id'
could not find table 'opportunities'`, breaking the "app must boot with any subset of modules"
guarantee (spec core B2). `tests/test_architecture.py` cannot catch this because it inspects Python
imports, not SQLAlchemy metadata.

### Root cause

`CLAUDE.md` §2 states: "Foreign keys may reference core tables (orgs/users) but not another

### Recommended solution

drop the FK constraint and keep `opportunity_id` as a plain indexed `Uuid`, with
referential integrity maintained via events (the pattern the architecture already prescribes). Add
an architecture test asserting that no module's tables declare a `ForeignKey` to a table owned by
another module. Audit all model files for the same pattern — `baselines`, `artifacts`,
`chat_sessions`, `deadlines`, `doc_chunks`, and `clauses` all carry an `opportunity_id`.


## TS-B03 — Seat limits are defined but never enforced

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-109  
**Location:** `backend/app/modules/billing/plans.py:9-14`  
**Status:** Confirmed Defect  

### Requirement / Impact

`PLAN_LIMITS` defines `seats` for every plan (free 2, paygo 3, pro 10, scale 25). `grep -rn "seats"
backend/app/` shows the key is **never read anywhere**. `add_workspace_member` and
`accept_invitation` perform no seat check, so a free workspace can add unlimited members. Since
seats are a priced dimension of every plan, this is direct revenue leakage — and it is the second
instance (with TS-B01) of a documented commercial constraint existing as data but never enforced
in code.

### Root cause

`PLAN_LIMITS` defines `seats` for every plan (free 2, paygo 3, pro 10, scale 25). `grep -rn "seats"

### Recommended solution

enforce in `add_workspace_member` and `accept_invitation`, raising a
`PaywallError` with an upsell payload consistent with the existing paywall pattern. See Q5 in §3.6.


## TS-S02 — Production startup guard is incomplete

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-115  
**Location:** `backend/app/main.py:56-79`  
**Status:** Design Concern  

### Requirement / Impact

`_validate_prod_settings` is a good pattern with gaps. It requires `TS_RAZORPAY_WEBHOOK_SECRET`
but **not** `TS_STRIPE_WEBHOOK_SECRET`, so a Stripe-billed deployment starts with unverifiable
webhooks (it fails closed, returning 400 — no revenue is stolen, but no payment is ever activated
either: a silent total billing outage). It also does not require `TS_REDIS_URL` (see TS-O01), does
not validate that `cookie_samesite="none"` is paired with `Secure`, applies the weak-secret check
only to Razorpay, and does not verify that the JWT keys parse as a valid RSA keypair — a malformed
PEM fails at first login rather than at boot.

### Root cause

`_validate_prod_settings` is a good pattern with gaps. It requires `TS_RAZORPAY_WEBHOOK_SECRET`

### Recommended solution

extend the guard to cover all of the above; parse the keypair at startup and
fail fast; require at least one notification sender in production.


## TS-O03 — No branch protection, no CODEOWNERS, no default branch convention

**Severity:** Medium  
**Release-blocking:** No  
**Task ID(s):** TS-120  
**Location:** repository configuration  
**Status:** Design Concern  

### Requirement / Impact

All 13 branches report `"protected": false`, and there is no `main`/`master` branch (§2.0). There
is no `CODEOWNERS`, no PR template, and no required-review configuration. CI runs on every push and
PR (good) but nothing prevents a direct push of unreviewed code to the de-facto trunk. For a
codebase handling payments and multi-tenant commercial data, unenforced review is a governance gap.

### Root cause

All 13 branches report `"protected": false`, and there is no `main`/`master` branch (§2.0). There

### Recommended solution

designate and protect a default branch; require PR review plus green CI before
merge; add `CODEOWNERS` for `auth/`, `billing/`, and `core/`.

---

### Low-severity findings


## TS-A08 — Invitation tokens stored in plaintext

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-126  
**Status:** Confirmed defect — by code inspection  


## TS-A09 — TOTP enrollment does not require a verification code

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-127  
**Status:** Confirmed defect — by code inspection  


## TS-R01 — Risk classifier uses brittle string slicing and no schema validation

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-137  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

into deterministic severity scoring, producing incorrect findings without the user noticing.

### Root cause

response parsing.

### Evidence

```python
raw = msg.content[0].text
return json.loads(raw[raw.index("[") : raw.rindex("]") + 1])
```

The parser finds the first `[` and the last `]` in the response. If the model emits any other
square brackets — in an explanation, a clause reference, or a formatting artifact — the slice will
be wrong and `json.loads` will fail or return malformed data. There is no Pydantic validation of
the required fields (`found`, `facts`, `source_quote`, `source_page`).

### Recommended solution

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

### Regression risks

same keys.

### Similar locations

answer is grounded-only or that it cites only provided facts (see TS-A13).


## TS-D02 — `days_to_submission` mixes UTC and local time for naive deadlines

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-138  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

remains.

### Root cause

compared against local wall-clock time.

### Evidence

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

### Recommended solution

encountered, assume UTC rather than local time:

```python
ref = datetime.now(UTC)
if submission_due.tzinfo is None:
    submission_due = submission_due.replace(tzinfo=UTC)
delta = submission_due - ref
```

### Similar locations

only after comparison with `datetime.now(UTC)`, so it has the same local-time bug.


## TS-Q01 — Qualification matrix marks missing criteria as `not_met` with HIGH severity

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-139  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

register and hiding real problems in a wall of noise.

### Evidence

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

### Recommended solution

`INFO`:

```python
if found is None:
    status = "not_mentioned"
    severity = Severity.LOW
else:
    status = "unknown"   # present but not verified
    severity = Severity.MEDIUM
```


## TS-X02 — BOQ engine relies on DuckDB reading `df` from caller scope

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-140  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Celery workers, refactored callers) and is harder to maintain or reason about.

### Root cause

formatting for numeric placeholders.

### Evidence

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

### Recommended solution

alias, and avoid `str.format` for SQL even with trusted numeric values:

```python
conn = duckdb.connect()
conn.register("df", df)
rows = conn.execute(CHECKS_SQL, [tolerance, outlier_quantile, outlier_multiplier]).fetchall()
```

### Similar locations

use DuckDB scope injection.


## TS-A11 — Cross-reference search loads all clauses regardless of `limit`

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-141  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

exhausted by a single search request. A very long `q` string also increases processing time.

### Root cause

of `q`.

### Evidence

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

### Recommended solution

move scoring to the database or at least apply a `LIMIT` after tokenisation. Short-term fix:

```python
limit: int = Query(20, ge=1, le=100)
```


## TS-I06 — `confirm_deadline` does not verify the deadline belongs to the opportunity

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-142  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

workspace, mutating the wrong tender's timeline.

### Evidence

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

### Recommended solution

`where` clause and return 404 when the deadline does not belong to the requested opportunity.


## TS-B05 — Baseline `freeze` has a race condition on `version` numbering

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-143  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

`next_version`, producing two baselines with the same version number and ambiguous ordering.

### Evidence

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

### Recommended solution

advisory lock or atomic `INSERT ... ON CONFLICT DO NOTHING` retry:

```python
class Baseline(Base, WorkspaceScopedMixin):
    __table_args__ = (UniqueConstraint("opportunity_id", "version"),)
```


## TS-S03 — Uploaded filename can inject `Content-Disposition` header in file download

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-144  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

the header. Although the route returns `application/octet-stream`, `Content-Disposition` injection
is a security hardening gap.

### Evidence

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

### Recommended solution

```python
import re
safe = re.sub(r'[^\w.\-]', '_', filename)
headers={"Content-Disposition": f'attachment; filename="{safe}"'},
```

### Similar locations

fixed `opportunity_id` UUID template, so they are safe; `main.py` is the only user-controlled
path.


## TS-A13 — Assistant agent has no output guard and includes user prompt verbatim

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-145  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

manipulated by crafted tender text uploaded by a malicious user.

### Root cause

post-hoc validation that the response only cites the provided tool results.

### Evidence

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

### Recommended solution

response, validate citations against the provided context, and run a lightweight prompt-injection
classifier on the user message. At minimum, add a post-processor that rejects answers whose
citations are not in the tool context.

### Tests to add

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


## TS-N02 — Notifications deadline-alert scheduler calls a missing `WorkspaceAdmin` method

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-146  
**Status:** Confirmed Defect (by inspection — requires APScheduler to be enabled)  

### Requirement / Impact

When APScheduler is enabled, every `deadline_alert_tick` raises `AttributeError: 'WorkspaceAdmin' object has no attribute 'list_all_workspaces'`. The exception is caught by APScheduler and the job continues, but no alert emails are sent. In the default Docker build APScheduler is not installed (`TS-O04`), so this is a latent failure that will surface as soon as the `scheduler` extra is installed.

### Root cause

The `auth.workspace_factory` capability contract is overloaded. Billing and export consume `WorkspaceAdmin` operations (`is_paying`, `get_user`, `set_plan`, `mark_free_review_used`), but notifications expects an admin list-workspaces operation. The wrong class is bound to the slot for this consumer.

### Evidence

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

### Recommended solution

Add `list_all_workspaces()` to `WorkspaceAdmin` so the existing registry binding works:

```python
class WorkspaceAdmin:
    ...
    def list_all_workspaces(self) -> list[dict]:
        rows = self.s.execute(select(Workspace.id, Workspace.name, Workspace.plan))
        return [{"workspace_id": str(r[0]), "name": r[1], "plan": r[2]} for r in rows]
```

Or, if `WorkspaceAdmin` is intended to be a narrow billing/admin interface, publish `AuthService` under a separate `auth.admin_factory` capability and have notifications consume that.

### Regression risks

Low. Billing/export use existing `WorkspaceAdmin` methods that are unchanged.

### Tests to add

1. `test_deadline_alert_tick_sends_email` — with APScheduler mocked, schedule the tick for a workspace with an upcoming deadline and verify at least one `Message` is queued.
2. `test_workspace_admin_list_all_workspaces` — assert `WorkspaceAdmin` exposes the method notifications expects.


## TS-I07 — `register_document` accepts unbounded `sample_text` and processes it synchronously

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-147  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

A single `POST /api/ingestion/opportunities/{id}/documents` with a multi-megabyte `sample_text` will hold a worker thread for a long time, perform many regex searches, and insert many rows. This is a straightforward CPU/memory DoS against the backend.

### Root cause

The `sample_text` field has no `max_length`, and the ingestion service assumes the input is reasonably sized. The synchronous route does not degrade large inputs to an async worker or stream.

### Evidence

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

### Recommended solution

1. Cap `sample_text` in the request body:

```python
class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    sample_text: str = Field("", max_length=1_000_000)
    supersedes: str | None = Field(None, max_length=36)
```

2. For the sync `upload_document` path, pass extracted text through a `DocChunk` generator and only classify/segment the first N characters (e.g. 200 KB) in the request; schedule the rest for the Celery worker (which must be fixed per `TS-I08`).

### Regression risks

Low. Legitimate tender documents rarely exceed a few hundred kilobytes of extracted text.

### Tests to add

1. `test_register_document_rejects_oversized_sample_text` — `422` when `sample_text` exceeds the cap.
2. `test_upload_document_large_text_does_not_block` — assert a 50 MB extracted text is either rejected or offloaded to the worker.


## TS-I08 — Async `process_document` Celery task does not classify, segment clauses, update the submission deadline, or run OCR

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-148  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Any document uploaded with `?async=1` is left with `kind="other"` and no `Clause` rows. The deadline wall may miss the `submission_due` update. Scanned PDFs uploaded asynchronously never get OCR applied. Downstream modules (risk, crossref, drafting, assistant) see an empty or incomplete corpus.

### Root cause

The async task was written as a minimal text-and-deadline extractor and not kept in sync with the synchronous `register_document` pipeline. It also does not receive the registry, so it cannot resolve the configured OCR provider.

### Evidence

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

### Recommended solution

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

### Regression risks

Medium. The async task is currently only exercised by `?async=1` uploads; the sync path is the default. The refactor should share the same helpers so behavior converges.

### Tests to add

1. `test_process_document_sets_kind_and_clauses` — enqueue the task and assert the resulting document has `kind != "other"` and `Clause` rows.
2. `test_process_document_updates_submission_due` — assert `Opportunity.submission_due` is set from a submission deadline in the text.
3. `test_process_document_uses_ocr_provider` — with a fake OCR provider, verify scanned PDFs are OCR'd instead of `needs_ocr`.


## TS-A14 — Assistant agent uses an invalid default Anthropic model name

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-149  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

The assistant silently degrades to a generic error message for every free-form query when an Anthropic key is configured. Users may not realize the assistant is broken because there is no HTTP error.

### Root cause

Same as `TS-R02`: a placeholder model name hardcoded in the LLM adapter and never wired to a setting.

### Evidence

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

### Recommended solution

Share the `TS_ANTHROPIC_MODEL` setting introduced for `TS-R02`:

```python
ctx.registry.provide(
    "assistant.agent",
    AnthropicAgent(model=s.anthropic_model, max_tokens=s.anthropic_max_tokens),
)
```

Fail fast on startup for unrecognized model names.

### Regression risks

Low. No currently working assistant path is affected.

### Tests to add

1. `test_assistant_with_invalid_model_returns_error` — the agent returns a clear error rather than silently swallowing.
2. `test_assistant_valid_model_uses_shared_setting` — the module passes the configured model to `AnthropicAgent`.


## TS-A15 — Review audit trail endpoint ignores `opportunity_id`

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-150  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

A reviewer for one opportunity can see audit entries for every other opportunity in the workspace (e.g., findings accepted/rejected, notes added). This is a workspace-internal data-leakage and compliance issue. It also makes the per-opportunity audit UI useless.

### Root cause

The audit log schema was built workspace-scoped but not opportunity-scoped, and the service signature accepts an `opportunity_id` parameter that it never uses.

### Evidence

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

### Recommended solution

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

### Regression risks

Low. Requires a migration, but opportunity-level audit is the intended behavior.

### Tests to add

1. `test_audit_trail_filters_by_opportunity` — create audit entries for two opportunities and assert the endpoint returns only the requested one.
2. `test_audit_log_stores_opportunity_id` — after `review_finding`, the `AuditLog` row has the finding's `opportunity_id`.


## TS-B06 — `Artifact.version` uses a non-atomic read-modify-write increment

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-151  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Concurrent artifact generation (e.g., two reviewers clicking "Generate" at the same time, or the UI retrying a slow request) can fail with 500 errors.

### Root cause

The version increment is not serialized. SQLAlchemy's `func.max` read and the subsequent insert are not an atomic single statement.

### Evidence

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

### Recommended solution

Use an advisory lock or a single atomic insert with `INSERT ... ON CONFLICT DO NOTHING` and retry:

```python
from sqlalchemy import text
def _next_version_atomic(self, opp, kind) -> int:
    # PostgreSQL example
    self.s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"), {"key": f"artifact:{opp}:{kind}"})
    return self.s.scalar(select(func.coalesce(func.max(Artifact.version), 0)).where(...)) + 1
```

For SQLite, use an application-level `threading.Lock` or move the operation to the worker. Long-term, add a unique constraint and a retry loop around the insert.

### Regression risks

Low. The fix only changes the version-assignment path; artifact content and ordering are unchanged.

### Tests to add

1. `test_generate_artifact_concurrent` — two concurrent `generate` calls for the same opportunity/kind produce versions `1` and `2` without 500s.
2. `test_generate_artifact_no_duplicate_versions` — assert the unique constraint is never violated under load.


## TS-D03 — Timeline ICS export appends `Z` to naive or local datetimes; synthetic `tender_published` uses `created_at`

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-152  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

Calendar entries are offset from the real deadline, which can mislead users into missing a submission or showing up at the wrong time. The synthetic publication date is misleading.

### Root cause

The ICS exporter does not normalize timestamps to UTC before formatting, and the fallback publisher date is not a real extracted fact.

### Evidence

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

### Recommended solution

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

### Regression risks

Low. Consumers of the ICS feed will get correct UTC timestamps.

### Tests to add

1. `test_export_ics_uses_utc` — a naive `due_at` of `2026-07-29 15:30:00` is emitted as `20260729T153000Z`, and a local timezone `due_at` is converted to the correct UTC time.
2. `test_export_ics_rejects_unzoned_created_at` — the synthetic `tender_published` event carries a UTC timestamp if `created_at` is naive.

### Similar locations

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


## TS-S04 — `LocalStorage` async methods perform synchronous file I/O

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-153  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

load this stalls other requests and can make the app unresponsive. The issue is invisible on
small files or light traffic.

### Root cause

implementations.

### Evidence

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

### Recommended solution

```python
async def write(self, key, data, content_type):
    path = self.root / key
    await asyncio.to_thread(lambda: path.parent.mkdir(parents=True, exist_ok=True))
    await asyncio.to_thread(path.write_bytes, data)
    return str(path.relative_to(self.root))
```

Do the same for `read` and `delete`.

### Tests to add

and assert they overlap rather than execute sequentially.

### Similar locations

also performs synchronous file I/O in async routes (`TS-I09`).


## TS-O05 — Production guard for CORS and allowed hosts can be bypassed with a comma-separated wildcard

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-154  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

validation. `CORSMiddleware` receives a list containing `"*"` and `allow_credentials` is forced
to `False`, so any origin can make cross-origin requests (without cookies). An admin can
unknowingly deploy with an open CORS/hosts policy.

### Root cause

elements.

### Evidence

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

### Recommended solution

`settings.allowed_host_list()` and raise if either contains `"*"` or is empty after stripping:

```python
if "*" in settings.cors_origin_list():
    errors.append("TS_CORS_ORIGINS must be explicit in production (no wildcard)")
if "*" in settings.allowed_host_list():
    errors.append("TS_ALLOWED_HOSTS must be explicit in production (no wildcard)")
```

### Tests to add

`test_prod_settings_reject_wildcard_in_allowed_hosts_list`.

### Similar locations

but only to disable credentials; the startup guard should reject the wildcard outright.


## TS-B07 — Stripe checkout uses hardcoded `example.com` redirect URLs

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-155  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

instead of the application. The UI never receives the session completion signal, so the user
sees a broken payment flow even though the webhook may activate the workspace server-side.

### Root cause

request-derived URLs.

### Evidence

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

### Recommended solution

single `TS_PUBLIC_APP_URL` and derive `/billing/stripe/success` and `/billing/stripe/cancel`),
and pass them to `checkout.Session.create`. Validate they are HTTPS in production.


## TS-B08 — Stripe webhook verifier swallows all exceptions and returns `None`

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-156  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

so operators cannot distinguish "wrong secret" from "Stripe SDK broken". The service returns
400, so Stripe may stop retrying or retry pointlessly, and payment activation may never happen.

### Root cause

failures.

### Evidence

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

### Recommended solution

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

### Similar locations

consume this verifier.


## TS-I09 — tus endpoints perform synchronous file I/O and `OPTIONS` returns a non-compliant empty body

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-157  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

tus uploads also block the event loop during every chunk read/write. Some tus clients may
refuse to start uploads when `OPTIONS` is non-compliant.

### Root cause

inline; the `OPTIONS` probe was not implemented to spec.

### Evidence

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

### Recommended solution

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

### Tests to add

`test_tus_create_does_not_block_event_loop`.

### Similar locations

anti-pattern.


## TS-A16 — `POST /api/review/findings/{finding_id}` does not scope by opportunity

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-158  
**Location:** `backend/app/modules/review/service.py:52-66`; `backend/app/modules/findings/store.py:49-55,63-83`  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

workspace can accept, reject, or edit it. This cross-opportunity write corrupts the wrong
tender's review state and audit trail.

### Root cause

the opportunity being reviewed. The store's `get`/`set_review` methods are workspace-scoped but
not opportunity-scoped.

### Evidence

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

### Recommended solution

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

### Regression risks

context; the frontend calls are per-opportunity.

### Tests to add

`test_finding_store_get_scopes_by_opportunity`.

### Similar locations

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


## TS-C01 — `Finding.amount_exposure` and monetary thresholds are stored/extracted as `float` major units, violating the minor-units invariant

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-159  
**Location:** `backend/app/modules/drafting/validators.py:18-44`; `backend/app/modules/drafting/service.py` and
`backend/app/modules/baseline/service.py` (amount casts); `backend/app/modules/boq/engine.py:96-99`;
`backend/app/modules/standards/service.py:25-29` and `models.py`; `backend/app/modules/standards/service.py:_extract_number`  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

findings can expose or compare amounts at the wrong scale; monetary fields cannot safely represent
non-INR currencies or sub-rupee figures in minor units.

### Root cause

enforced in the shared contract, the database schema, or the consumers. Major-unit `float` values
propagate through risk, drafting, baseline, BOQ, and standards, carrying rounding errors and breaking
cross-currency consistency.

### Evidence

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

### Recommended solution

2) Change `FindingRow.amount_exposure` to `BigInteger` and migrate existing data. 3) Update
`FactTable` to parse amounts into integer paise and compare integer values with no tolerance. 4)
Reimplement BOQ engine with `Decimal`/minor-unit arithmetic. 5) Update standards `PolicyBody.threshold`
to `int` and `_extract_number` to return minor units. 6) Update `_rupees()` formatting to divide by 100.

### Regression risks

rendering the value must format it as currency. Existing tests that expect float comparisons will need
updates.

### Tests to add

`test_fact_table_rejects_major_unit_float`; `test_boq_amount_calc_no_float_rounding`;
`test_standards_threshold_minor_units`.

### Similar locations

`backend/app/modules/baseline/service.py` cast `amount_exposure` to `float`;
`backend/app/modules/standards/models.py` maps `threshold` to `Numeric(12, 4)`;
`backend/app/modules/boq/engine.py` computes `amount`/`amount_calc` with `float` and `round`.


## TS-I10 — XLSX/CSV text extraction does not emit page markers, so spreadsheet-derived deadlines and clauses lose page provenance

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-160  
**Location:** `backend/app/modules/ingestion/doc_text.py:27-45`; `backend/app/modules/ingestion/segment.py:41-68`;
`backend/app/modules/ingestion/deadlines.py:83-105`  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

stored as a single "Preamble" segment with `clause_ref=None`, violating the "every extracted fact has
`source_page`" invariant and making it impossible to cite the source sheet/page for
spreadsheet-derived facts.

### Root cause

downstream page-aware pipeline only understands `[pN]`. No component maps sheets to synthetic page
numbers.

### Evidence

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

### Recommended solution

sheet or `[pN]` per logical page), or update `_PAGE_MARKER`, `segment_clauses`, and `extract_deadlines`
to treat `[sheet:<name>]` as a page boundary and derive a `source_page` from the sheet index. Also
update `DocChunk` and `Clause` `page`/`page_from` accordingly.

### Regression risks

remains unchanged.

### Tests to add

`test_csv_deadline_carries_correct_source_page`;
`test_xlsx_clause_segmentation_not_single_preamble`.

### Similar locations

of `[pN]` markers; `backend/app/modules/ingestion/tasks.py` calls `extract_upload` and should be
included in regression tests.


## TS-A17 — Email/password login selects an arbitrary workspace for multi-workspace users

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-161  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

access token pointing at a different tenant's data. The `switch_workspace` endpoint exists, but the
initial session is non-deterministic.

### Root cause

deterministic. The codebase has no concept of a primary/default workspace, and the login flow has no
workspace-selection step.

### Evidence

```python
member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
workspace_id = member.workspace_id if member else None
role = member.role if member else "owner"
```

There is no `ORDER BY`, `LIMIT 1`, or primary-workspace flag, so the returned row is whichever row
the database happens to return first.

### Recommended solution

`LIMIT 1` to the query; better, return a list of workspaces and require explicit selection when there
are multiple. Persist the choice in the token or session.

### Regression risks

workspace.

### Tests to add

`test_login_multi_workspace_reproducible`.

### Similar locations

explicit workspace selection; the login path should reuse the same membership check.


## TS-R03 — Severity evaluator silently defaults missing facts to `0`

**Severity:** **Medium**  
**Release-blocking:** No  
**Task ID(s):** TS-162  
**Status:** Confirmed Defect (by inspection)  

### Requirement / Impact

`OppFacts` does not include a value the rule expects. This undermines the "numbers never come from
the LLM" guarantee because the downstream severity computation silently invents a numeric default.

### Root cause

`evaluate_severity` catches malformed rules but not missing variables.

### Evidence

```python
if isinstance(node, ast.Name):
    if node.id in _VALID_SEVERITIES:
        return node.id
    return ctx.get(node.id, 0)  # missing facts default to 0/falsy
```

This means a missing fact (e.g., `rate_percent_per_week` not returned by the classifier) becomes
`0` in comparisons. A rule like `"critical if rate_percent_per_week > 0.5 else medium"` would
incorrectly evaluate to `medium` when the fact is missing, instead of failing closed or defaulting.

### Recommended solution

`evaluate_severity` catch it and return the `default` severity while logging a warning. Alternatively,
return a sentinel `None` and propagate it so comparisons short-circuit to the `default`. Document
required facts per pattern and validate the classifier output against them.

### Regression risks

referencing missing facts. Existing tests with complete fact sets continue to pass.

### Tests to add

`test_evaluate_severity_missing_fact_logs_warning`.

### Similar locations

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


## TS-L01 — `/api/health/details` is unauthenticated outside production.

**Severity:** —  
**Release-blocking:** No  
**Task ID(s):** TS-118  

### Requirement / Impact

`health/router.py:48` gates on `settings.is_prod()`, so staging and any non-`prod` environment
expose the full module inventory, failed-module list, and registry capability names to anonymous
callers — a useful reconnaissance map.

### Root cause

`health/router.py:48` gates on `settings.is_prod()`, so staging and any non-`prod` environment

### Recommended solution

require super-admin whenever auth is loaded,
regardless of environment.


## TS-L02 — No pagination on any list endpoint.

**Severity:** —  
**Release-blocking:** No  
**Task ID(s):** TS-118  

### Requirement / Impact

`GET /ingestion/opportunities`,
`/findings/opportunities/{id}`, `/billing/invoices`, `/auth/workspaces/{id}/members`, and
`/assistant/sessions` all return complete result sets. Only `crossref` accepts a `limit`. Response
sizes and query cost grow unbounded with tenant age.

### Root cause

`GET /ingestion/opportunities`,

### Recommended solution

add cursor pagination with a default
and maximum page size.


## TS-L03 — Accessibility not established.

**Severity:** —  
**Release-blocking:** No  
**Task ID(s):** TS-119  

### Requirement / Impact

Across `frontend/app/` and `frontend/components/`
there are 12 `<input>` elements and 10 `<label>` elements, with 10 total occurrences of
`aria-*`/`role=`/`alt=` attributes in the entire frontend. No skip link, no focus-trap handling in
modals, no automated a11y check in CI. **This is Not Tested rather than Failed** — no browser or
screen reader was available (§1.6), and the shared `Field` component may associate labels
correctly.

### Root cause

Across `frontend/app/` and `frontend/components/`

### Recommended solution

add `eslint-plugin-jsx-a11y` and `axe-core` to CI, then re-assess against WCAG
2.1 AA.


## TS-L04 — `pip install -e ".[dev]"` fails on Debian system Python.

**Severity:** —  
**Release-blocking:** No  
**Task ID(s):** TS-120  

### Requirement / Impact

Reproduced:
`ERROR: Cannot uninstall PyJWT 2.7.0, RECORD file not found. Hint: The package was installed by
debian.` The audit worked around this with a virtualenv. CI is unaffected (it uses
`actions/setup-python`), but a new contributor following the README hits this immediately.

### Root cause

Reproduced:

### Recommended solution

document the virtualenv requirement in `README.md`, or add `--ignore-installed PyJWT` to the
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

