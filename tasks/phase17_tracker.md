# Phase 17 — Baseline Lock & Handover Completion — Tracker

**Requirement source:** Research Doc §4.E, §5.2; `docs/TenderShield_Roadmap_Stage1_to_5.md` §4
**Specs:** `specs/modules/baseline.md` (primary), `specs/modules/standards.md`, `specs/modules/auth.md`,
`specs/modules/export.md`, `specs/modules/analytics.md`
**Backlog:** `tasks/backlog.md` §Phase 17 (TS-235 – TS-242)
**Master roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md` · `tasks/roadmap_tracker.md`

**Phase goal.** Turn the existing `baseline` freeze (hash-sealed snapshot) into the **project controls
layer** Stage 3 change detection needs: watchlists, a complete notice-rule register, cost codes,
approval limits, and role-specific handover packs.

**Unlock gate (Research Doc §12.4):** Phase 16 exit gates green before starting implementation sprints.

**Phase exit gate:** Two projects with a locked baseline in weekly use; notice rules configured for at
least two contract forms; cost codes mapped end-to-end.

---

## Sprint map

| Sprint | Theme | Tasks | Exit gate | Status |
|---|---|---|---|---|
| **0** | **Spec** | TS-235 ✅ | `baseline.md` defines controls, notice completion, cost codes, handover views | **done** |
| **1** | **Award delta + watchlist** | TS-236 ✅, TS-237 ✅ | Award-vs-tender diff with citations; accepted findings → watchlist rows | **done** |
| **2** | **Notice register + approval** | TS-238 ✅, TS-239 ✅ | Per-contract notice types with addresses/reps; approval matrix enforced | **done** |
| **3** | **Cost codes + handover** | TS-240, TS-241 | BOQ→cost-code map; site/planning/procurement/finance handover exports | todo |
| **4** | **Telemetry** | TS-242 | Baseline adoption metrics visible; Phase 18 unlock gate measurable | todo |

### Why this order

**Spec before code (TS-235).** The `baseline` module already freezes findings and a basic notice
register. Phase 17 adds *controls* — the Research Doc's bridge to change detection. Without a written
spec, watchlists and cost codes will duplicate `findings` or `ingestion` tables.

**Award comparison before watchlist (TS-236 → TS-237).** Watchlist items need a stable obligation
identity. Award-vs-tender diff defines what changed at handover; watchlists monitor what was accepted
at tender and still applies on site.

**Notice register + approval before cost codes (TS-238/239 → TS-240).** Phase 18's notice-deadline
engine reads the register; approval matrix gates who can issue notices. Cost codes feed variation
valuation in Phases 18–19 and should not block notice work.

---

## Task table

| ID | Title | Module | Priority | Status | Acceptance (short) | Blockers |
|---|---|---|---|---|---|---|
| TS-235 | Spec: baseline completion | `baseline` | P0 | **done** | Spec updated; maps to TS-236–242 | — |
| TS-236 | Award comparison vs tender assumptions | `baseline` | P0 | **done** | Concessions + new obligations with citations | TS-235 |
| TS-237 | Risk → project watchlist | `baseline` | P0 | **done** | Owner, trigger, cadence per accepted finding | TS-235 |
| TS-238 | Notice-rule register (complete) | `baseline` + `standards` | P0 | **done** | Types, triggers, content, addresses, reps | TS-235 |
| TS-239 | Approval matrix | `auth` | P1 | **done** | Role limits on notice/variation/claim actions | TS-235 |
| TS-240 | Cost-code model | `baseline` | P0 | todo | Codes mapped to BOQ + variation categories | TS-235 |
| TS-241 | Handover pack multi-view export | `export` + `baseline` | P1 | todo | Site/planning/procurement/finance views + seal ref | TS-237 |
| TS-242 | Baseline adoption telemetry | `analytics` | P0 | todo | Locked baselines + weekly active users | TS-235 |

---

## Evidence chain (Phase 17 slice)

```
tender finding (accepted)  →  baseline seal  →  watchlist control  →  [Phase 18 change event]
                                      ↓
                            notice-rule register  →  [Phase 18 deadline engine]
                                      ↓
                            cost-code map  →  [Phase 18/19 valuation]
```

Phase 17 does **not** implement change events, notice issuance, or claims — only the frozen controls
that Phase 18 diffs against.

---

## Standing constraints

- **Numbers never from the LLM** — notice deadlines, cost-code totals, and approval checks are
  deterministic (`CLAUDE.md` §4).
- **Every control carries provenance** — watchlist and notice rows link to `baseline_id`, finding id,
  or clause citation; no invented obligations.
- **Workspace isolation** — all new tables RLS-scoped like existing `baselines`.
- **Module boundaries** — `baseline` owns controls data; `auth` owns approval matrix; `analytics`
  owns telemetry aggregation; cross-module via registry + events only.
