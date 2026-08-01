# Phase 18 — Change & Notice Control — Tracker

**Requirement source:** Research Doc §4.F, §5.3; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4
**Specs:** `specs/modules/change.md` (primary), `specs/modules/notifications.md`,
`specs/modules/drafting.md`, `specs/modules/evidence.md` (new), `specs/modules/billing.md`
**Backlog:** `tasks/backlog.md` §Phase 18 (TS-243 – TS-256)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Convert transactional tender revenue into **per-project recurring subscription** by
detecting variations against the locked baseline, triaging them, confirming on site, and driving
deterministic notice deadlines and drafts.

**Unlock gate (Research Doc §12.4):** *"Two projects use baseline weekly"* — measured by
`GET /api/analytics/baseline-adoption` (TS-242).

**Phase exit gate:** Five real change events documented before work completion on a live project;
notices issued on time via the platform; one customer on per-project billing.

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Spec + scaffold** | TS-243 ✅, TS-244 ✅ | `change.md` agreed; module boots; tables migrated | **done** |
| **1** | **Detection** | TS-245, TS-246, TS-247 | Baseline diff + signal ingestion emit cited candidates | todo |
| **2** | **Inbox + confirmation** | TS-248, TS-249, TS-250 | Triage queue; impact links; site confirmation | todo |
| **3** | **Notice engine** | TS-251, TS-252, TS-253 | Deterministic deadlines; alerts; draft with validators | todo |
| **4** | **Evidence + billing** | TS-254, TS-255, TS-256 | Chain of custody; completeness score; project lane | todo |

### Why this order

**Spec before tables (TS-243 → TS-244).** Change events carry legal weight; the event/source/
confirmation model must be written before migrations.

**Detection before inbox (TS-245/246 → TS-248).** The inbox triages *candidates*; without diff and
signal ingestion there is nothing to triage.

**Confirmation before notice engine (TS-250 → TS-251).** Deadlines attach to confirmed events with
a known `trigger_date` and `notice_type`.

**Evidence and billing last (TS-254–TS-256).** Evidence chain extends confirmations; billing gates
sustained usage once the workflow is proven.

---

## Task table

| ID | Title | Module | Priority | Status | Acceptance (short) | Blockers |
|---|---|---|---|---|---|---|
| TS-243 | Spec: `change` module | `change` | P0 | **done** | Spec in `specs/modules/change.md` | Phase 17 |
| TS-244 | `change` scaffold + migrations | `change` | P0 | **done** | Tables + boot + manual event API | TS-243 |
| TS-245 | Baseline diff engine | `change` | P0 | todo | Cited clause/finding deltas vs seal | TS-244, TS-236 |
| TS-246 | Change-signal ingestion | `change` | P0 | todo | RFI/SI/minutes/daily reports classified | TS-244 |
| TS-247 | Email ingestion adapter | `change` | P1 | todo | Forward-to-inbox + injection defenses | TS-246 |
| TS-248 | Potential-variation inbox | `change` | P0 | todo | Triage queue with confidence bands | TS-245, TS-246 |
| TS-249 | Impact linking | `change` | P0 | todo | BOQ + cost codes + subcontract refs | TS-240, TS-248 |
| TS-250 | Site confirmation workflow | `change` | P0 | todo | Six outcomes + confirmer/timestamp | TS-248 |
| TS-251 | Deterministic notice-deadline engine | `change` | P0 | todo | Never LLM; uses notice register | TS-238, TS-250 |
| TS-252 | Countdown + escalation alerts | `notifications` | P0 | todo | 7/3/1/0 deduped alerts | TS-251 |
| TS-253 | Notice drafting | `drafting` | P0 | todo | Verified facts + validators + approval | TS-251 |
| TS-254 | Evidence attachment + custody | `evidence` | P0 | todo | Type, date, creator, chain | TS-250 |
| TS-255 | Evidence-completeness scoring | `evidence` | P1 | todo | Missing records list per event | TS-254 |
| TS-256 | Per-project billing lane | `billing` | P0 | todo | Webhook-only activation | TS-250 |

---

## Evidence chain (Phase 18 slice)

```
baseline seal  →  change candidate (diff/signal)  →  triage  →  site confirmation
       ↓                                                              ↓
notice register  →  deterministic deadline  →  alert  →  notice draft  →  [Phase 19 claim]
       ↓
evidence attachment + completeness score
```

Phase 18 does **not** implement claims valuation, portfolio dashboards, or ERP integrations — only
change detection through notice preparation.

---

## Product invariants (Phase 18)

- **Numbers never from the LLM** — notice deadlines, exposure totals, completeness scores.
- **Every displayed fact has provenance** — `source_page` + verbatim `source_quote` ≤200 chars.
- **Webhook is billing truth** — per-project activation never from client redirect alone.
- **Modules stay pluggable** — `change` consumes baseline/ingestion via registry only.
