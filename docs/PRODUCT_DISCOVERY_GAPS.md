# Product Discovery Gaps — capabilities that were never built, not just code that is broken

**Created:** 2026-07-28 (TS-126) · **Scope:** whole product
**Predecessor:** `docs/GAP_ANALYSIS.md` (TS-083) audited what exists and found it
defective. This audit asks a different question: **what is missing entirely** —
requirements never written, roles with no workflow, journeys that dead-end,
capabilities the domain expects that nobody has represented anywhere.
**Tracked as:** Gates 5–7 in `tasks/gap_remediation_tracker.md`, tasks TS-110…TS-125.

---

## Product context used for this audit

No product-context brief was supplied, so the fields below are **inferred from the
repository** and are marked as assumptions. Every one of them is a question for the
product owner (see `Product Decisions Required`), and several findings below change
severity depending on the answers.

| Field | Value used | Source |
|---|---|---|
| Product name | TenderShield AI | `CLAUDE.md` |
| Purpose | Pre-bid contractor commercial intelligence: ingest a tender pack, surface risk clauses / deadline traps / BOQ defects with citations, produce bid-decision artifacts | `specs/000-product-overview.md` |
| Target users | P1 mid-market GC commercial head (India, primary), P2 small contractor owner, P3 QS consultancy, P4 EPC team (Phase 3+) | Product overview §Personas |
| Roles | `viewer < reviewer < estimator < admin < owner`, plus a global `is_superadmin` | `auth/rbac.py` |
| Tenant model | Workspace-per-firm, RLS-enforced; `projects` exist as a sub-tenant grouping | `auth/models.py` |
| Critical workflows | Upload pack → classify/segment → extract deadlines → risk + BOQ review → human accept/reject → generate artifacts → export pack | Product overview, module specs |
| Sensitive data | Customer tender packs (commercially confidential), GST/billing identity, auth credentials | R-001, R-007 |
| Payments | Razorpay live (India); Stripe (GCC/UK) not written | R-005 |
| Launch date | **UNKNOWN — assumption:** Phase-1 exit needs 3 paid conversions | Product overview §Phase gates |
| Expected users | **UNKNOWN** | — |
| Production env | **UNKNOWN — assumption:** ap-south-1, per the stated data-residency NFR | Product overview §NFR |
| Compliance | **UNKNOWN — assumption:** India DPDP Act applies (Indian customers, Indian PII); no SOC2/ISO evidence in repo | Inferred |
| Audit-only or remediation authorized | Remediation authorized (consistent with the standing instruction driving Gates 1–4) | Session history |

---

## How findings are classified

- **Confirmed Missing Requirement** — explicitly required by an existing spec, doc or
  NFR, and not implemented.
- **Strongly Implied Requirement** — not written down, but an existing role, entity or
  workflow is incomplete without it.
- **Domain-Expected Capability** — standard for this product category; not yet
  confirmed as in-scope.
- **Product Improvement** — valuable, not required for release.
- **Clarification Required** — insufficient evidence; needs a product decision.

Nothing inferred is presented as confirmed.

---

## The headline finding

**A user cannot upload their own tender.**

`POST /api/ingestion/opportunities/{id}/upload` exists, is fully implemented, and was
hardened in TS-095 with streaming, a pre-buffer size cap, and magic-byte validation.
It has **no user interface**. There is no `<input type="file">`, no `FormData`, and no
call to `/upload` anywhere in `frontend/`. The only way a document enters the system
through the UI is the "Upload sample tender" button, which posts a **hardcoded 12-line
demo string** (`SAMPLE` in `app/opportunities/[id]/page.tsx:25`); the BOQ path is the
same (`SAMPLE_BOQ`, line 38).

So the entire product — a tool whose premise is "ingest a tender pack" — is a
demo that can only ever analyse its own fixture. Everything downstream of ingestion
(risk review, BOQ checks, deadline extraction, artifacts, export, the paywall that
charges ₹7,500 for a review) currently operates exclusively on that fixture.

This reframes the four completed gates. Gates 1–4 correctly fixed tenant isolation,
the paywall, payments, GST invoicing, entitlements, sessions and workspace switching —
a workspace can now be billed, isolated and switched. It cannot yet be *used*.

---

# Gate 5 — Make the core journey real (release-blocking)

## G-01 · Real document upload journey · TS-110

1. **Capability.** Upload real tender files (PDF/XLSX/CSV/DOCX) from the UI: file
   picker, drag-drop, multi-file, per-file progress, type/size validation feedback,
   failure recovery, and a document list showing what was ingested and how it was
   classified.
2. **Affected roles.** estimator, admin, owner (the `/upload` route requires
   `estimator`). viewer sees results only.
3. **Evidence.** `grep -rn "FormData|type=\"file\"" frontend/` returns nothing.
   `frontend/lib/api.ts` has no multipart helper. `registerDocument()` sends
   `{filename, sample_text}` as JSON. The hardened multipart endpoint
   (`ingestion/router.py`, `spool_upload`, `MAX_UPLOAD_BYTES`) has zero callers
   outside tests.
4. **Classification.** **Confirmed Missing Requirement** — the product overview's
   first NFR is "Upload → deadline wall + doc checklist < 3 min p95", which presumes
   an upload exists.
5. **User/business problem.** A customer cannot analyse their own tender. There is no
   path from "I have a 400-page NIT PDF" to any output.
6. **Consequences if omitted.** No real usage, no Phase-1 exit (3 paid conversions
   cannot happen for a product that cannot accept a customer's file), and the TS-095
   upload-hardening work protects an endpoint nobody can reach.
7. **Proposed behavior.** A drop zone on the opportunity page and in an empty state:
   select or drag N files → per-file rows with progress, detected type, and
   classification result → the checklist/deadline wall refreshes as each completes.
   Rejected files (too large, wrong type, corrupt) show the specific reason and stay
   retryable. The existing "Upload sample tender" button remains, relabelled "Try a
   sample", as a genuine demo affordance.
8. **Changes.** *Frontend:* upload component, multipart branch in `lib/api.ts` (must
   not set `Content-Type` — the browser sets the multipart boundary), progress via
   `XMLHttpRequest` or streamed `fetch`, document list UI. *Backend:* none required
   for single-file; **resumable chunked upload is a separate NFR** (product overview
   §1.3) and is not satisfied by this task. *DB:* none. *Permissions:* reuse
   `require("estimator")`. *Ops:* real files make `TS_STORAGE_DIR` a real dependency —
   ties to R-016/TS-106 (S3).
9. **Acceptance criteria.** (a) A real multi-page PDF uploads and produces clauses +
   deadlines. (b) An oversized file is rejected client-side *and* server-side with a
   readable message. (c) A disallowed type is rejected by magic bytes, not extension.
   (d) Upload failure mid-transfer leaves no half-ingested document. (e) Multi-file
   upload reports per-file status independently. (f) The sample button still works.
10. **Priority.** P0.
11. **Release-blocking.** **Yes — the single most blocking item in the product.**
12. **Questions.** Is resumable/chunked upload required for launch, or is
    single-shot ≤ the cap acceptable for v1? What is the real maximum pack size —
    the 800-page NFR implies well above a typical default cap. Is ZIP ingestion
    (stated in §1.3) in scope for launch? (R-003 §B.4 deferred ZIP guards precisely
    because no ZIP path existed.)

## G-02 · Opportunity lifecycle and the bid/no-bid decision · TS-111

1. **Capability.** Move an opportunity through a real lifecycle and record the
   commercial decision the product exists to inform: reviewing → bid / no-bid →
   submitted → won / lost / withdrawn, with who decided, when, and why.
2. **Affected roles.** estimator/admin/owner decide; viewer and reviewer read.
3. **Evidence.** `Opportunity.status` defaults to `"reviewing"` and is **never
   assigned anywhere in the codebase** (`grep` for writes returns nothing). No
   `PATCH /opportunities/{id}` exists. The frontend renders `statusLabel(o.status)`,
   so every card in the product permanently reads "reviewing". No entity anywhere
   records a bid/no-bid outcome.
4. **Classification.** **Confirmed Missing Requirement** — the product overview
   defines the deliverable as "bid-decision artifacts", and the kill-gate metric is
   "<40% second-tender conversion", which is unmeasurable without an outcome record.
5. **User/business problem.** The user does the analysis and then leaves the tool to
   make and record the decision. Nothing closes the loop.
6. **Consequences if omitted.** No pipeline view is possible (G-12, R-012's dashboard
   needs status to segment by). No win/loss learning. The Phase-1 and kill-gate
   metrics in the product overview cannot be computed from production data. Users
   have no reason to return to a completed tender.
7. **Proposed behavior.** A status control on the opportunity header; a decision
   dialog capturing outcome + optional rationale + decided-by/at; status visible on
   cards and filterable on the board; transitions written to the audit trail (G-05).
   Terminal states (won/lost/withdrawn) exclude the record from "live" views without
   deleting it.
8. **Changes.** *Frontend:* status control, decision dialog, board filter. *Backend:*
   `PATCH /ingestion/opportunities/{id}` with a validated transition map; a
   `bid_decision` record (or columns) with `decided_by`, `decided_at`, `rationale`.
   *DB:* migration. *Permissions:* estimator+. *Ops:* none.
9. **Acceptance criteria.** (a) Status transitions are validated server-side — an
   invalid jump is rejected, not silently written. (b) The decision records actor and
   timestamp. (c) The board can filter live vs closed. (d) Every transition appears in
   the audit trail. (e) A closed opportunity is still fully readable.
10. **Priority.** P0.
11. **Release-blocking.** **Yes** — without it the product has no completion state and
    its own success metrics are unmeasurable.
12. **Questions.** What is the authoritative status list for an Indian GC's tender
    pipeline (does "submitted" precede an award wait — are "L1/L2 position" or
    "technical qualification" real states)? Should a no-bid require a reason from a
    fixed list (that list becomes the product's most valuable dataset)? Does the
    decision need approval by a second person for large tenders?

## G-03 · Delete, archive and restore for business records · TS-112

1. **Capability.** Remove or archive an opportunity and its documents; restore within
   a grace window; understand what deletion actually removes.
2. **Affected roles.** admin/owner delete; all roles affected by the resulting view.
3. **Evidence.** The app has exactly **two `DELETE` routes in total**, both on
   `standards` (`grep -rn '@router.delete'`). Nothing can delete or archive an
   opportunity, document, finding, artifact, baseline, project, member, or invitation.
4. **Classification.** **Strongly Implied Requirement** — every create path in the
   product is one-way.
5. **User/business problem.** A test upload, a duplicate, or a wrong-file mistake is
   permanent and pollutes the board and the deadline wall forever. There is also no
   way to remove a document uploaded in error — a real confidentiality concern when
   the wrong client's pack is uploaded to the wrong workspace.
6. **Consequences if omitted.** The board degrades with unusable clutter as usage
   grows; users cannot correct mistakes; a mis-uploaded confidential pack cannot be
   withdrawn, which is a customer-trust and possibly contractual problem.
7. **Proposed behavior.** Soft-delete (archive) by default with a restore window and
   an explicit "delete permanently" for admins; deleting a document removes its
   derived clauses/deadlines/findings and says so before confirming; archived items
   are hidden from live views but reachable via a filter.
8. **Changes.** *Frontend:* archive/restore/delete affordances + confirmation showing
   cascade scope. *Backend:* `DELETE`/`PATCH` routes per entity; cascade semantics
   decided per module (findings and artifacts derive from documents). *DB:*
   `archived_at`/`deleted_at` columns; cascade rules. *Permissions:* admin+ for
   permanent delete. *Ops:* stored blobs must be removed too (`LocalStorage` has no
   delete; the `Storage` protocol gains one under R-016/TS-106).
9. **Acceptance criteria.** (a) Archive hides from live views, keeps data, is
   restorable. (b) Permanent delete removes derived records and stored blobs. (c) The
   confirmation states exactly what will be destroyed. (d) Deletion is audited (G-05).
   (e) Deletion respects RLS — one workspace can never delete another's record.
10. **Priority.** P0 for archive/soft-delete; P1 for permanent delete.
11. **Release-blocking.** **Yes** for archive — an append-only board becomes unusable
    within weeks of real use.
12. **Questions.** Should permanent deletion be available to customers at all, or only
    via support (safer for a records-oriented product with statutory invoices
    attached)? What is the restore window? Do sealed baselines — deliberately
    immutable, hash-verified handover records — resist deletion entirely?

## G-04 · Deadline alerts that are actually delivered · TS-113

1. **Capability.** Proactive deadline alerts (email now, WhatsApp later) at the
   thresholds the product already defines, with per-user opt-in/out.
2. **Affected roles.** all roles with workspace membership; per-user preference.
3. **Evidence.** `notifications/digest.py` implements `ALERT_DAYS = (7, 3, 1, 0)`,
   `deadlines_to_alert()` and `format_digest()` — and has **zero callers** anywhere in
   the app. The notifications module registers `router=None` and a `ConsoleSender`
   that only logs. There is no scheduler (R-016/TS-105), no user preference storage,
   and no in-app notification surface.
4. **Classification.** **Confirmed Missing Requirement** — Doc §11.6/§11.7 specifies
   the digest, and the code was written to that spec but never connected.
5. **User/business problem.** The product's core promise is that you don't miss a
   deadline trap. Today it will only tell you if you happen to open it.
6. **Consequences if omitted.** The central value proposition is unrealised; the
   product stays a once-per-tender tool rather than a daily one, which is the exact
   retention failure R-012 warns about. A customer who misses a submission deadline
   while paying for a deadline product is a churn and reputation event.
7. **Proposed behavior.** A scheduled job evaluates every live opportunity's confirmed
   deadlines daily, sends one digest per user per day (not one per deadline), respects
   per-user preferences and quiet hours, and records what was sent so a retry or a
   duplicate delivery is detectable. In-app notification list mirrors it.
8. **Changes.** *Frontend:* notification preferences in account settings; in-app
   notification surface. *Backend:* wire `digest.py` to a scheduled job; a real email
   adapter (shares the delivery work with R-015/TS-099); a `notification_log` for
   idempotent send-once semantics. *DB:* preferences + send log. *Permissions:*
   per-user. *Ops:* **hard dependency on the job scheduler (R-016/TS-105)** and on a
   real email provider.
9. **Acceptance criteria.** (a) A deadline 7/3/1/0 days out generates exactly one
   alert per user per day. (b) An unconfirmed extracted deadline does not alert
   (citations must be human-confirmed first — the product's own invariant). (c)
   Opt-out is honoured immediately. (d) A retried job does not double-send. (e) An
   archived/closed opportunity stops alerting.
10. **Priority.** P0 (product-defining), sequenced after TS-105.
11. **Release-blocking.** **Yes** — this is the product's primary promise.
12. **Questions.** Is WhatsApp required at launch for the India SMB segment, or is
    email sufficient for v1 (the overview lists WhatsApp alert UI as P2)? Who receives
    alerts by default — every workspace member, or only those assigned to the
    opportunity (there is no assignment concept today, see G-15)?

---

# Gate 6 — Trust, recovery and compliance

## G-05 · Audit trail beyond review decisions · TS-114

1. **Capability.** A workspace-scoped audit record of security- and
   commercially-significant events, not just finding accept/reject.
2. **Affected roles.** admin/owner read; superadmin reads across workspaces.
3. **Evidence.** `audit_log` is written in exactly one place —
   `review/service.py:38`, for finding decisions. No audit record exists for login,
   failed login, MFA change, password reset, member add/remove, role change,
   invitation issue/accept, workspace switch, plan change, payment, refund, export,
   or superadmin action. `AuthService` emits none.
4. **Classification.** **Strongly Implied Requirement** — R-001/R-002 hardened
   tenant isolation and auth, and an isolation guarantee that cannot be *evidenced*
   after the fact is materially weaker.
5. **User/business problem.** Nobody can answer "who added this person to our
   workspace", "who exported our tender pack", or "who changed our plan".
6. **Consequences if omitted.** Security incidents are uninvestigable; enterprise and
   consultancy buyers (persona P3 handling several clients' confidential packs) will
   ask for this in diligence; DPDP breach-notification duties are hard to discharge
   without knowing what was accessed.
7. **Proposed behavior.** A shared `app.core` audit capability that any module can
   call by name; append-only, workspace-scoped, RLS-protected, with actor, action,
   target, source IP, and timestamp; an admin-visible viewer with filters and export.
8. **Changes.** *Frontend:* audit viewer (overlaps R-013/TS-103, which surfaces the
   *existing* review audit — this widens what is recorded). *Backend:* audit
   capability + call sites across auth/billing/export/ingestion. *DB:* generalise
   `audit_log` (it currently lives in `review`, which is the wrong owner for
   cross-cutting events — likely a move to `core`). *Permissions:* admin+.
   *Ops:* retention policy for audit rows.
9. **Acceptance criteria.** (a) Every auth, membership, billing, export and admin
   action writes an audit row. (b) Rows are immutable and RLS-scoped. (c) The viewer
   filters by actor/action/date and exports CSV. (d) Cross-tenant reads are impossible
   — proven against real Postgres, matching this repo's established discipline.
10. **Priority.** P1.
11. **Release-blocking.** **No for a design-partner launch; Yes before any enterprise
    or consultancy contract.**
12. **Questions.** What retention period is required? Is tamper-evidence (hash
    chaining) needed, or is append-only with RLS sufficient for the target buyer?

## G-06 · Data-subject rights and account/workspace closure (DPDP) · TS-115

1. **Capability.** Export everything a workspace holds; delete a workspace or an
   account on request, with a defined retention/erasure path.
2. **Affected roles.** owner requests; superadmin executes/oversees.
3. **Evidence.** No workspace deletion, no account deletion, no personal-data export
   route anywhere. R-016/TS-109 lists "DPDP request paths" but as **documentation to
   publish**, not a capability to build. The privacy claim already made to users
   ("your data lives inside your workspace only", `app/help/page.tsx`) implies
   controls that do not exist.
4. **Classification.** **Domain-Expected Capability** with a likely legal trigger —
   **Clarification Required** on the compliance regime (no compliance brief supplied).
5. **User/business problem.** A customer who leaves cannot take their data or have it
   erased; the company cannot honour a DPDP erasure request without manual SQL.
6. **Consequences if omitted.** Regulatory exposure under India's DPDP Act
   (**assumption** — unconfirmed); a blocking question in any enterprise procurement;
   an unfulfillable promise in the published Help page.
7. **Proposed behavior.** Owner-initiated workspace data export (structured JSON +
   original files) delivered as a job; owner-initiated closure that schedules deletion
   after a grace period, with statutory records (GST invoices) retained per Indian tax
   law and that exception stated plainly to the user.
8. **Changes.** *Frontend:* account/workspace settings actions with clear
   consequences. *Backend:* export job, deletion orchestration across every module
   that owns workspace-scoped tables, blob deletion. *DB:* deletion-request tracking.
   *Permissions:* owner + superadmin. *Ops:* depends on the job system (TS-105) and
   storage delete (TS-106); needs a documented retention matrix.
9. **Acceptance criteria.** (a) Export contains every workspace-scoped entity and all
   stored files. (b) Deletion removes all workspace data except statutorily retained
   invoices, and that exception is disclosed. (c) Deletion is irreversible after the
   grace period and audited. (d) A deleted workspace's data is unreachable from every
   module, verified against real Postgres.
10. **Priority.** P1.
11. **Release-blocking.** **Clarification Required** — blocking if DPDP applies at
    launch, which is likely for an India-first product handling Indian business PII.
12. **Questions.** **Does DPDP apply at launch, and is there a named data
    fiduciary/DPO?** What retention is required for GST invoices (typically 8 years —
    needs confirmation), and does that override an erasure request? Are customer
    tender packs classified as personal data, business-confidential, or both?

## G-07 · Member removal and invitation lifecycle · TS-116

1. **Capability.** Remove a member, change a role safely, and list/resend/revoke
   pending invitations.
2. **Affected roles.** admin/owner manage; every member affected.
3. **Evidence.** `POST/GET /workspaces/{id}/members` exist; there is **no DELETE**.
   `POST /invitations` exists; there is **no list, no revoke, no resend**. Invitations
   consume seats (R-009 §B.3) and expire after 7 days, so an unrevokable pending
   invitation silently holds a paid seat for a week.
4. **Classification.** **Strongly Implied Requirement** — offboarding is the missing
   half of an onboarding feature that already exists and already bills for seats.
5. **User/business problem.** An employee who leaves keeps access to every tender in
   the workspace, permanently. A mistyped invitation cannot be cancelled.
6. **Consequences if omitted.** A serious access-control gap (ex-employees retain
   access to confidential commercial data); seats leak and customers are billed for
   people who cannot be removed; support burden.
7. **Proposed behavior.** Member list with role editing and removal (the existing
   last-owner guard already prevents orphaning); removal revokes the member's sessions
   for that workspace; pending-invitation list with revoke and resend.
8. **Changes.** *Frontend:* members/invitations UI (overlaps R-013/TS-103 — that task
   builds the screens, this one supplies the missing endpoints they need). *Backend:*
   `DELETE /workspaces/{id}/members/{user_id}`, invitation list/revoke/resend,
   session revocation on removal. *DB:* none beyond an invitation status. *Permissions:*
   admin+. *Ops:* none.
9. **Acceptance criteria.** (a) A removed member immediately loses access — existing
   tokens for that workspace stop working, not just future ones. (b) The last owner
   cannot be removed. (c) A revoked invitation cannot be redeemed and releases its
   seat. (d) Removal and revocation are audited. (e) Seat counts update immediately.
10. **Priority.** P0 for member removal, P1 for invitation management.
11. **Release-blocking.** **Yes** — "cannot remove a departed employee's access" is
    not a shippable state for a confidential-document product.
12. **Questions.** On removal, what happens to records that member created — retained
    with attribution (recommended for an audit-oriented product) or reassigned? Should
    removal be immediate or scheduled?

## G-08 · Processing failure visibility and recovery · TS-117

1. **Capability.** See that a review/ingestion run failed, why, and retry it.
2. **Affected roles.** estimator/admin; superadmin for investigation.
3. **Evidence.** Runs are synchronous with no persisted run record. There is no job
   status, no failure record, no retry. A failed OCR or LLM call surfaces as an HTTP
   error and vanishes. `Opportunity.status` cannot express "processing failed" (and is
   never written at all — G-02).
4. **Classification.** **Strongly Implied Requirement** — the 25-minute p95 NFR for an
   800-page pack cannot be met synchronously, so an async model with visible state is
   implied by the NFR itself.
5. **User/business problem.** A long review that fails leaves the user with nothing and
   no explanation, having possibly consumed a paid review.
6. **Consequences if omitted.** Silent failure on the most expensive operation in the
   product; support cannot diagnose; billing disputes ("I paid and got nothing") with
   no evidence either way.
7. **Proposed behavior.** Persisted run records with state and error detail, progress
   in the UI, user-initiated retry, and metering that does not consume an entitlement
   for a run that failed for our reasons.
8. **Changes.** *Frontend:* run status/progress, failure state, retry. *Backend:* run
   records; retry semantics; **metering interaction** — `authorize_review` currently
   meters at start (`review_started`), so a failed run must either not consume or must
   be refunded. *DB:* run table. *Permissions:* estimator+. *Ops:* built on TS-105.
9. **Acceptance criteria.** (a) A failed run is visible with a cause. (b) Retry does
   not double-charge or double-meter. (c) A run that fails for an internal reason does
   not consume the free/paid review. (d) Support can see the failure reason.
10. **Priority.** P1.
11. **Release-blocking.** **Yes if reviews are async at launch** (TS-105); otherwise
    P1 immediately after.
12. **Questions.** Does a failed review refund the metered entitlement automatically?
    What is the acceptable retry count before escalating to support?

---

# Gate 7 — Expose what is already built

Seven backend modules are implemented, tested, registered and routable, and have **no
user interface at all**. This is the cheapest value in the entire backlog: the
engine work is already paid for.

| Gap | Capability (already built server-side) | Endpoints | Task | Class |
|---|---|---|---|---|
| G-09 | **Deadline calendar / timeline**, including `.ics` subscription | `GET /timeline/opportunities/{id}/timeline`, `…/timeline.ics` | TS-118 | Confirmed Missing (UI) |
| G-10 | **Review queue + audit viewer** — the human-review workflow the export gate depends on | `GET /review/…/queue`, `GET /review/…/audit` | TS-119 | Confirmed Missing (UI) |
| G-11 | **Bid qualification / eligibility check** — turnover, experience, equipment criteria | `GET/POST /qualification/opportunities/{id}` | TS-120 | Confirmed Missing (UI) |
| G-12 | **Cross-tender comparison** | `GET /comparison/opportunities` | TS-121 | Confirmed Missing (UI) |
| G-13 | **Addendum cross-reference / diff** — what changed between versions of a pack | `GET/POST /crossref/opportunities/{id}` | TS-122 | Confirmed Missing (UI) |
| G-14 | **Rule-pack transparency** — which patterns ran, at what version and confidence | `GET /rulepacks`, `GET /rulepacks/{id}/patterns` | TS-123 | Strongly Implied |
| G-16 | **Support/ops investigation console** | `GET /auth/admin/*` exist; no investigation tooling | TS-125 | Domain-Expected |

Two of these deserve individual treatment because they are not merely "unexposed" —
they are load-bearing:

**G-10 (review queue)** is the gate on export. `ExportService._gate_ok` blocks export
until every finding is accepted or rejected, and the only way to do that today is to
click through findings inline on one opportunity's Risks tab. There is no queue, no
bulk action, no cross-opportunity view. For an 800-page pack producing dozens of
findings this is the difference between a usable and an unusable workflow, and it sits
directly on the paid path. It is also the workflow the `reviewer` role is named
for, and the one thing that role cannot currently do. **P0, release-blocking.**

**G-09 (timeline/.ics)** already implements calendar subscription — the single highest-
leverage retention feature in a deadline product, because it puts TenderShield inside
the tool the customer already lives in (Outlook/Google Calendar). It is finished and
unreachable. **P1, exceptional value-to-effort.**

**G-15 · Search and findability · TS-124** — **Strongly Implied.** There is no search
anywhere: not across opportunities, not within a pack's clauses, not across findings.
`doc_chunks` exists (suggesting retrieval was planned) and `assistant` can answer
questions but is deliberately unsurfaced. Once a workspace holds 50 tenders the board
becomes unnavigable. Also note: **there is no concept of assigning an opportunity to a
person** — which G-04 needs to decide who gets alerted, and which a team product
normally requires. *P1; assignment may be P0 depending on the answer to G-04's
question.*

---

## Cross-cutting observations

**Roles are enforced but unmanageable and invisible.** All five roles gate real
endpoints (`viewer` 36×, `estimator` 13×, `admin` 11×, `reviewer` 3×). But the UI has
no member management, shows identical navigation to every role, and never displays the
caller's own role. `reviewer` is the thinnest: of the three endpoints it gates, two
are the review queue and audit (no UI — G-10) and one is `baseline/freeze` (reachable
via the Handover tab). So the role exists and has exactly one reachable action, and
the workflow it is actually named for is the unreachable one.

**`projects` and `project_members` are a fully-built sub-tenant layer with no UI and
no clear product purpose.** Four endpoints, two tables, RLS coverage, membership
guards — and nothing in the product references projects. Either they are a deliberate
future capability or dead weight carrying real complexity and attack surface.
**Clarification Required.**

**Every module ships with its own spec, but no spec describes an end-to-end user
journey.** The specs are excellent per-module contracts; nothing states "here is what
a commercial head does on Tuesday morning". The gaps above cluster precisely in the
seams between modules, which is what that missing document would have surfaced.

---

## Product Decisions Required

Answers change scope, sequencing and release-blocking status. Ordered by impact.

1. **Compliance:** Does DPDP apply at launch? Is there a named data fiduciary? This
   decides whether G-06 blocks release or follows it.
2. **Launch shape:** Is the target a small design-partner cohort (3 firms, per the
   Phase-1 exit gate) or general availability? A design-partner launch can defer G-05,
   G-06 and much of Gate 7; GA cannot.
3. **Upload envelope:** Maximum pack size, resumable/chunked required at launch?, ZIP
   ingestion in or out? (G-01)
4. **Tender lifecycle:** the authoritative status list, and whether no-bid reasons are
   a controlled vocabulary. (G-02)
5. **Deletion policy:** can customers permanently delete, or only archive with
   support-mediated deletion? Restore window? Do sealed baselines resist deletion?
   (G-03)
6. **Alerting:** WhatsApp at launch or email only? Who is alerted by default —
   everyone, or an assignee (which requires building assignment)? (G-04, G-15)
7. **Teams:** on member removal, are their records retained with attribution or
   reassigned? (G-07)
8. **Failed runs:** does a failed review automatically refund the metered
   entitlement? (G-08)
9. **Projects:** is the `projects` layer a real roadmap capability or should it be
   removed? (Cross-cutting)
10. **Assistant:** `specs/frontend.md` states the end-user AI assistant is
    *intentionally* unsurfaced. Confirm that remains true — six working endpoints and
    two tables are currently dark.

---

## Recommended sequencing

Gate 5 first, in order: **G-01 (upload) → G-10 (review queue) → G-02 (lifecycle) →
G-03 (archive) → G-04 (alerts, after TS-105)**. That sequence is the shortest path to
a product a design partner can actually use end to end on their own tender.

Gate 6 (trust/compliance) is gated on the launch-shape and DPDP answers.

Gate 7 is opportunistic and cheap — each item is a UI over a finished, tested backend
— and G-09 (`.ics` calendar) is the best value-to-effort item in the whole backlog.
