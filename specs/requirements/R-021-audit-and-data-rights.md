# R-021 — Audit trail and data-subject rights

**Status:** draft
**Severity:** P1 — an isolation guarantee that cannot be evidenced after the fact
is materially weaker; data-subject rights may be a legal requirement
**Requirement refs:** Doc §3.2, §16; R-001 (isolation), R-016/TS-109 (legal surface)
**Task refs:** TS-114 (audit), TS-115 (data rights)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-114](../../tasks/specs/TS-114-core-audit-trail.md), [TS-115](../../tasks/specs/TS-115-data-export-account-closure.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-05, §G-06
**Specs to update:** `specs/modules/core.md`, `specs/modules/auth.md`,
`specs/data-model.md`

## Part A — Audit trail beyond review decisions (TS-114)

### Purpose

`audit_log` is written in exactly **one place** in the entire application:

```python
# backend/app/modules/review/service.py:38 — the only writer
AuditLog(...)   # finding accepted / rejected
```

Nothing records: login, failed login, MFA enrolment, password reset, member
add/remove, role change, invitation issued/accepted, workspace switch, plan
change, payment, refund, export, or any superadmin action.

Gates 1–4 hardened tenant isolation (R-001), auth (R-002) and payments (R-005).
None of that hardening can be *evidenced* after an incident. Nobody can answer
"who added this person to our workspace" or "who exported our tender pack".

### Target

- **A.1** A shared audit capability in `app.core`, consumed by name so any module
  can write an audit row without importing another module (CLAUDE.md §2).
- **A.2** `audit_log` moves out of `review` — a cross-cutting concern owned by one
  feature module is the wrong shape. It becomes core-owned, workspace-scoped and
  RLS-protected.
- **A.3** Rows carry actor, action, target type + id, source IP, and timestamp.
  Append-only: no update or delete path exists, for anyone.
- **A.4** Call sites added across auth, billing, ingestion, export and admin.
- **A.5** An admin-visible viewer with filters and CSV export. (R-013/TS-103
  surfaces the *existing* review audit; this widens what is recorded and shares
  that screen.)

### Acceptance criteria

- **A1** Login, failed login, member add/remove, role change, plan change,
  refund, export and superadmin actions each write an audit row.
- **A2** Audit rows cannot be updated or deleted through any route.
- **A3** The viewer filters by actor, action and date range, and exports CSV.
- **A4** A cross-tenant audit read is impossible — **verified against real
  PostgreSQL with FORCE RLS live**, per this repo's established discipline
  (SQLite's RLS no-op has produced three false-green results in this codebase).
- **A5** Moving the table does not lose existing review-decision rows.

### Out of scope

Tamper-evidence (hash chaining), SIEM export, and real-time alerting on
suspicious patterns. Append-only + RLS is the v1 bar.

---

## Part B — Data-subject rights and account closure (TS-115)

### Purpose

There is no workspace deletion, no account deletion, and no data-export route.
R-016/TS-109 lists "DPDP request paths" as **documentation to publish**, not a
capability to build — so today the published document would describe a process
the software cannot perform.

The product already makes a privacy promise to users in shipped copy:

> "Everything you upload lives inside your workspace only — tender packs are
> never shared across firms and are never used to train models."
> — `frontend/app/help/page.tsx`

That promise implies controls (export, erasure) that do not exist.

### Target

- **B.1 Workspace data export.** Owner-initiated, delivered as a job: structured
  JSON of every workspace-scoped entity plus all original uploaded files.
- **B.2 Workspace closure.** Owner-initiated, schedules deletion after a grace
  period, orchestrated across every module owning workspace-scoped tables.
- **B.3 Statutory retention is an explicit, disclosed exception.** Issued GST
  invoices are retained per Indian tax law even after closure, and the user is
  told this plainly at the point of closure rather than discovering it later.
- **B.4 Account (user) deletion** distinct from workspace deletion: a user who is
  the sole owner of a workspace must transfer ownership or close the workspace
  first (the existing last-owner guard already models this constraint).

### Acceptance criteria

- **B1** Export contains every workspace-scoped entity and every stored file.
- **B2** Closure removes all workspace data except statutorily retained invoices,
  and that exception is disclosed *before* the user confirms.
- **B3** After the grace period, deletion is irreversible and audited.
- **B4** A deleted workspace's data is unreachable from every module — verified
  against real PostgreSQL.
- **B5** A sole owner cannot delete their account without first resolving the
  workspace.

### Out of scope

Per-record data-subject requests (as opposed to whole-workspace), consent
management, and cross-border transfer controls.

---

## Questions for the product owner

1. **Does DPDP apply at launch, and is a data fiduciary named?** This decides
   whether Part B blocks release or follows it. No compliance brief was supplied
   for this audit; India-first with Indian business PII makes it likely.
2. **What retention applies to GST invoices** (commonly cited as 8 years — needs
   confirmation), and does it override an erasure request?
3. **Are customer tender packs personal data, business-confidential, or both?**
   The answer changes both the erasure obligation and the breach-notification
   duty.
4. What audit retention period is required, and is tamper-evidence needed for the
   target buyer (enterprise/consultancy diligence often asks)?

## Assumptions

- `assumption:` DPDP applies. Every "release-blocking" judgement in Part B is
  conditional on that being confirmed.
- `assumption:` statutory invoice retention overrides customer erasure requests —
  standard for tax records, but a lawyer should confirm before the closure flow
  ships with that behavior baked in.
