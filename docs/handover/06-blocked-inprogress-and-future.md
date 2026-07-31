# 06 — Blocked, in-progress, gated, and Phases 17–21

Covers the remaining **62** incomplete tasks not detailed in docs 01–05: 1 in-progress, 4 blocked,
1 gated Phase-16 task, and the 58 tasks of Phases 17–21.

---

## In progress

### TS-163 — Account-centric auth re-architecture *(backend + core frontend done; settings UI outstanding)*

Backend and core frontend landed. What remains is the **account/security settings UI**.

- `frontend/app/settings/page.tsx` exists (346 lines) with a `notifications/` subpage.
- Missing, per the task title: **account settings** and **security settings** surfaces —
  email/mobile re-verification, password change, MFA (TOTP) enrolment management, active-session /
  refresh-token revocation.
- Backend endpoints for these already exist in `app/modules/auth/` (TS-011/028/107/117 shipped
  argon2id, RS256 JWT, rotating refresh with reuse detection, TOTP enrol/verify, GDPR export +
  account deletion). **This is a UI-wiring task, not a backend task** — check `frontend/lib/api.ts`
  for the generated client before writing new fetch calls.
- Flip the status to `done` in `tasks/backlog.md` only when the settings UI is actually shipped.

---

## Blocked — all four need live third-party credentials, not code

These are **not** engineering-blocked. The adapters are written; verification needs real keys.
Do not "fix" them by writing more code.

| ID | What exists | What unblocks it |
|---|---|---|
| TS-035 | SES/Resend + MSG91 adapters in `app/modules/notifications/adapters.py` | Live SES + MSG91 credentials; send a real email + SMS end-to-end |
| TS-036 | Google OIDC in `app/modules/auth/google.py`; MSG91 phone OTP | Live Google OAuth client + MSG91 key |
| TS-037 | Stripe + Razorpay providers in `app/modules/billing/providers.py` | Live keys + webhook secrets; verify a real webhook signature |
| TS-079 | Dev-only token return for email/SMS MFA and password reset | Same providers as TS-035; replace the dev token path |

`app/main.py::_validate_prod_settings` already fails fast in production when these are missing or
placeholder — so the guardrail is in place; only verification is outstanding.

---

## Gated Phase-16 task

### TS-222 — Ladder rung 2: supply-and-erection patterns (`rulepacks`) — **P3, deliberately not built**

Strategy §D.2 gates rung 2 on **a paying customer asking for it**. Building it now would be exactly
the scope reflex Build Doc §12.6 warns against. Recorded here so it is not mistaken for an oversight.

When a customer does ask, it is YAML only (zero code — that is the point of the domain ladder proven
by TS-220/221): customs/GST variation, split delivery/erection LD, performance-guarantee tests,
free-issue material, O&M tail. Author with the pack SDK (`backend/app/packsdk/`), validate with
`scripts/pack_validate.py`, test with `scripts/pack_test.py`.

---

## Phases 17–21 — 58 tasks, all gated

**Source of truth:** `docs/TenderShield_Roadmap_Stage1_to_5.md` and `tasks/roadmap_tracker.md`.
None of these has a spec yet — most name a spec file marked `(new)`. **Step one of every phase is
writing that spec** (`specs/README.md` template), because `CLAUDE.md` §1.2 requires spec-before-code.

### The strategic picture (Roadmap Part 1–2)

| Stage | Phase | Outcome | Revenue model | Built? |
|---|---|---|---|---|
| 1 Pre-bid assessment | ≤16 | Fewer dangerous bids | Per-tender + team sub | ✅ substantially complete |
| 2 Baseline lock | **17** | Traceable contract/BOQ baseline | Project activation fee | ⚠️ partial |
| 3 Change & notice control | **18** | Notices not missed, evidence preserved | **Per-project recurring** ★ | ❌ |
| 4 Claims workspace | **19** | Draft claims + exposure dashboard | Premium module | ❌ |
| 5 Portfolio intelligence | **20** | Cross-project benchmarks | Enterprise annual | ❌ |
| — Integrations/advisor | **21** | Ecosystem + channel | Various | ❌ |

**The structural problem this exposes:** stages 1–2 are *transactional*; stages 3–5 are *recurring*.
Every line of the ~24,500-line backend currently sits in the transactional half. **Phase 18 is where
recurring revenue and real switching cost begin** — it is the flagship, and everything before it is
setup.

### Unlock gates — do not skip these

| Phase | Gate |
|---|---|
| 17 | Phase 16 exit gates green (see `tasks/phase16_tracker.md` §Phase 16 exit gates) |
| 18 | **"Two projects use baseline weekly"** (Research Doc §12.4) |
| 19 | Users capture contemporaneous evidence **and** ≥5 real events documented before work completion |
| 20 | Phase 19 in production with ≥1 customer |
| 21 | *"Integration marketplaces only after workflow proof"*; uploads/exports before APIs |

`tasks/roadmap_tracker.md` has a **gate-override log** — if a gate is consciously skipped, record it
there rather than letting it happen implicitly.

### Phase 17 — Baseline completion (TS-235 → TS-242, 8 tasks)

Extends the existing `baseline` module (932 LOC — freeze/verify/notice-register/delta/handover
already exist). The gap is *controls*, not freezing.

- **TS-235** spec first — `specs/modules/baseline.md` update covering controls, notice rules, cost
  codes, approval matrix, handover pack.
- **TS-236** award comparison: diff negotiated contract + accepted BOQ against tender assumptions;
  highlight concessions and new obligations **with citations**.
- **TS-237** risk → project watchlist: accepted tender findings become monitored controls with
  owner, trigger, review cadence. *This is the join between Phase 1 output and Phase 18 input.*
- **TS-238** notice-rule register (`standards` update): per-contract notice types, trigger events,
  **deterministic deadline arithmetic**, required content, addresses, authorized representatives.
- **TS-239** approval matrix (`auth` update): role-based authority limits per action.
- **TS-240** cost-code model: foundation for stage 3/4 valuation.
- **TS-241** commercial handover pack export (site/planning/procurement/finance views) with
  hash-sealed baseline reference.
- **TS-242** baseline adoption telemetry — **this is what measures the Phase 18 unlock gate**, so it
  must ship in Phase 17, not later.

### Phase 18 — Change & notice control ★ (TS-243 → TS-256, 14 tasks)

The recurring-revenue phase. New module `change` + new module `evidence`.

- **TS-243/244** spec + scaffold: `change_events`, `change_sources`, `change_confirmations`
  (workspace-scoped, RLS).
- **TS-245** baseline diff engine → candidate change events with citations.
- **TS-246/247** change-signal ingestion (RFIs, site instructions, minutes, daily reports) and an
  **email ingestion adapter** (forward-to-inbox per project). ⚠️ Correspondence is untrusted input —
  Build Doc §11.3 prompt-injection defences apply in full; reuse `app/core/prompt_guard.py`.
- **TS-248/249/250** variation inbox, impact linking to BOQ/cost codes/subcontracts, and site
  confirmation (changed / not changed / clarification only / contractor risk / client risk /
  unknown) with recorded confirmer + timestamp.
- **TS-251 deterministic notice-deadline engine** — computes deadline and required content from the
  Phase-17 notice-rule register. **Never LLM** (`CLAUDE.md` §4). Highest-consequence code in the
  phase: a missed notice deadline is an extinguished contractual right.
- **TS-252** countdown, escalation, multi-channel alerts with per-event dedup (reuse the TS-111
  notification dedup work).
- **TS-253** notice drafting: contract-specific template, **verified facts only**, all three
  validators applied, **human approval mandatory before issue**.
- **TS-254/255** evidence attachment + chain of custody, and **evidence-completeness scoring** with
  a list of missing contemporaneous records. The Research Doc calls evidence continuity *"the most
  valuable product"*.
- **TS-256** per-project billing lane (server-owned prices, webhook-only activation — same rules as
  `05-express-lane.md`).

### Phase 19 — Claims & evidence workspace (TS-257 → TS-270, 14 tasks)

New module `claims`. Highlights:
- **TS-261 quantum workspace** — deterministic quantity × rate × daywork with reviewer sign-off,
  **zero LLM arithmetic**.
- **TS-262** delay-event register with **no autonomous entitlement conclusion** — the product
  assembles evidence; it does not adjudicate.
- **TS-266 chain-integrity test**: every claim must trace claim → notice → event → baseline
  obligation → tender clause; **a broken link fails the build**. This is the accountability moat made
  executable.
- **TS-267** conflicts control: block serving opposing parties on the same project.
- **TS-269** extends the north-star (TS-234) with recovered claim value.

### Phase 20 — Commercial control tower (TS-271 → TS-280, 10 tasks)

Deterministic exposure model (at-risk revenue, unnotified change, submitted/certified/rejected
value, ageing, cash exposure), risk-adjusted forecast **with an explicit assumptions block** (same
discipline as `pricing/cashflow.py`), portfolio clause trends, payment control, plus economics
(TS-279) and customer-outcome (TS-280) metrics.

### Phase 21 — Integrations, subcontract, advisor (TS-281 → TS-292, 12 tasks)

Adapter framework then SharePoint/OneDrive, Procore, ACC, Aconex, ERP, P6/MS Project.
**TS-288/289 subcontract control** (flow-down clause comparison, **pay-when-paid exposure flags**)
is the highest-value item here for a contractor. **TS-290/291** Advisor Edition + white-label is a
channel play, not a feature.

---

## Task-ID hygiene (matters for every commit)

- IDs are **sequential and never reused** (`tasks/backlog.md` header).
- Next free ID: **TS-299**. TS-297/298 were consumed renumbering a branch-merge collision;
  TS-195–TS-296 belong to Phases 16–21.
- `scripts/task_tracker.py --validate` runs as a **blocking CI job** (`backlog`) and checks unique
  IDs, the status enum (`todo | in-progress | blocked | done`), 5-column row shape, that paths cited
  by *done* tasks exist on disk, and that every `TS-` id in `tasks/*tracker*.md` exists in the
  backlog. Run it before every commit that touches a task.
