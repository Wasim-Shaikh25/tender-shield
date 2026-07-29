# TS-007 — Rule-pack scaffold (`rulepacks/in-works/`)

**Status:** done
**Requirement:** Doc §2, §14
**Spec(s) updated:** none (rule-packs are versioned data, not code — see
  CLAUDE.md §5)
**Module(s):** —
**Severity / Gate:** P0 · Bootstrap

## What this builds

The rule-pack folder shape and manifest itself — the thing every risk
pattern, trade checklist, and playbook plugs into. Rule-packs are versioned
data (`rulepacks/`), never prompt text; every pattern carries `source:` and
`confidence: unvalidated|validated` (CLAUDE.md §5).

## Implementation

```yaml
# rulepacks/in-works/pack.yaml
id: in-works
version: "2026.07.1"
jurisdiction: IN
effective_from: "2026-07-01"
effective_to: null
description: >
  India works tenders (CPWD/state PWD/NHAI/railways/private). Phase-0 seed
  drafted from public sources only — every pattern is confidence: unvalidated
  until the Phase-1 QS checkpoint (Doc §14.3).
reviewer_signoff: null   # set at Phase-1 validation checkpoint (Doc §2.4)
sources:
  - "CPWD Works Manual + CPWD GCC (baseline standard clauses)"
  - "MoF Manual for Procurement of Works, 2nd ed. (2025)"
  - "General Financial Rules (GFR) 2017"
  - "HKA CRUX 2025 / Arcadis-CMAA 2025 dispute-driver taxonomy"
```

Subfolders under `rulepacks/in-works/`: `risk_patterns/` (TS-008),
`boq/trade_checklists/` (TS-009), `playbooks/` (bid-decision playbook data),
`notice_standards/`, plus `doc_types.yaml` at the pack root.

## Files touched

- `rulepacks/in-works/pack.yaml`, `doc_types.yaml`, and the four subfolders

## Tests

None — data scaffold. Individual patterns are validated by schema checks
introduced with the modules that consume them (`risk`, `boq`).

## Acceptance criteria

- [x] Every pack has a manifest (`pack.yaml`) with `id`, `version`,
      `jurisdiction`, `sources`, `reviewer_signoff`.
- [x] Every pattern file under the pack carries `source:` and `confidence:`.

## Commit

Predates commit-granular history (PR #10 bulk import).
