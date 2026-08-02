# Phase 19 — Claims & Evidence Workspace — Tracker

**Requirement source:** Research Doc §4.G, §5.3, §13; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4
**Specs:** `specs/modules/claims.md` (primary), `specs/modules/evidence.md`, `specs/modules/drafting.md`,
`specs/modules/export.md`, `specs/modules/analytics.md`, `specs/modules/outcomes.md`
**Backlog:** `tasks/backlog.md` §Phase 19 (TS-257 – TS-270)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Turn the contemporaneous evidence captured in Phase 18 into defensible claim packages:
a cited chronology, an evidence checklist, a deterministic quantum workspace, a delay-event register,
draft generators, and a negotiation/settlement lifecycle — all feeding the `margin_protected` north-star
metric.

**Unlock gate (Research Doc §12.4):** *"Do not build claims valuation until users capture
contemporaneous evidence in the platform"* **AND** *"Document at least five real events before work
completion."*

**Phase exit gate:** One claim package assembled end-to-end from platform evidence with an unbroken
chain; recovered value recorded against the north-star metric.

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Spec + scaffold** | TS-257, TS-258 | `claims.md` agreed; module boots; tables migrated | done |
| **1** | **Chronology + checklist** | TS-259, TS-260 | Cited chronology; evidence checklist by claim type | done |
| **2** | **Quantum + delay** | TS-261, TS-262 | Deterministic quantum; delay register with no entitlement conclusion | done |
| **3** | **Drafts + negotiation** | TS-263, TS-264 | Verified-facts drafts; issue→response→negotiation→settlement | done |
| **4** | **Outcome + integrity** | TS-265, TS-266, TS-267 | Recovered value; chain-integrity test; conflict control | in-progress |
| **5** | **Metrics + site evidence** | TS-268, TS-269, TS-270 | Cycle-time metrics; north-star feed; site evidence hooks | todo |

### Why this order

**Spec before tables (TS-257 → TS-258).** Claims carry legal weight; the claim/event/quantum/delay
model must be written before migrations.

**Chronology before drafts (TS-259 → TS-263).** Drafts are assembled from the chronology; without it
there is nothing to populate a claim pack.

**Checklist before quantum (TS-260 → TS-261).** Quantum needs evidentiary support; the checklist
surfaces missing contemporaneous records before valuation.

**Negotiation before outcome (TS-264 → TS-265/TS-269).** Recovered value is only known at settlement.

---

## Task table

| ID | Title | Module | Priority | Status | Acceptance (short) | Blockers |
|---|---|---|---|---|---|---|
| TS-257 | Spec: `claims` module | `claims` | P0 | done | Spec in `specs/modules/claims.md` | Phase 18 |
| TS-258 | `claims` scaffold + migrations | `claims` | P0 | done | Tables + boot + list/create claim API | TS-257 |
| TS-259 | Chronology builder | `claims` | P0 | done | Every entry cited; sorted by occurred_at | TS-258 |
| TS-260 | Evidence checklist per claim type | `claims` | P0 | done | Required-type map; present/missing flags | TS-258 |
| TS-261 | Quantum workspace | `claims` | P0 | done | Quantity × rate + daywork; zero LLM | TS-258 |
| TS-262 | Delay-event register | `claims` | P1 | done | Facts only; no entitlement conclusion | TS-258 |
| TS-263 | Draft generators: particulars, variation proposal, EOT, full pack | `claims` + `drafting` | P0 | done | Verified facts + validators + approval | TS-259, TS-261 |
| TS-264 | Issue → response → negotiation → settlement tracking | `claims` | P1 | done | Append-only; status transitions | TS-258 |
| TS-265 | Outcome feedback into private learning set | `claims` + `outcomes` | P0 | done | Publish settlement event | TS-264 |
| TS-266 | Chain-integrity test | `claims` | P0 | done | claim → notice → event → obligation → clause | TS-258 |
| TS-267 | Conflicts control | `claims` + `auth` | P1 | todo | Block opposing parties on same project | TS-258 |
| TS-268 | Claim-cycle-time + notice-timeliness metrics | `claims` + `analytics` | P1 | todo | Cycle time and status counts | TS-264 |
| TS-269 | North-star extension: recovered claim value | `claims` + `outcomes` | P0 | todo | Feeds `margin_protected` | TS-265 |
| TS-270 | Site evidence capture hooks | `claims` + `evidence` | P1 | todo | Mobile geotagged/ labour/ plant/ daywork record types | TS-260 |

---

## Evidence chain (Phase 19 slice)

```
change event (confirmed)  →  notice (deadline + draft)  →  evidence (custody)
        ↓                                                                    ↓
   delay register  →  quantum workspace  →  chronology  →  claim draft  →  settlement
        ↓                                                                                         ↓
   chain-integrity test  ←  baseline obligation ← tender clause
```

Phase 19 does **not** implement portfolio dashboards, ERP integrations, or autonomous entitlement
conclusions — only the claim package assembly and negotiation lifecycle.

---

## Product invariants (Phase 19)

- **Numbers never from the LLM** — quantum totals and delay days are deterministic code (`CLAUDE.md` §4).
- **Every displayed fact has provenance** — `source_page` + verbatim `source_quote` ≤200 chars.
- **Human approval before issue** — drafts and claim submission require named approval (Build Doc §11.4).
- **No autonomous entitlement conclusion** — the delay register records facts, it does not decide EOT.
- **Webhook is billing truth** — any per-claim premium activation uses the same webhook-only pattern as Phase 18.
- **Modules stay pluggable** — `claims` consumes `change`, `evidence`, `baseline` via registry only.
