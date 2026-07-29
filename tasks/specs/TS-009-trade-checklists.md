# TS-009 — Trade scope-gap checklists (civil, electrical, HVAC)

**Status:** done
**Requirement:** Doc §6.4
**Spec(s) updated:** `specs/modules/boq.md`
**Module(s):** `boq`
**Severity / Gate:** P0 · Bootstrap

## What this builds

The first 3 trade checklists used for BOQ scope-gap detection — items a BOQ
should include given trade/trigger keywords, so their absence can be flagged
as a defect (Doc §6.4).

## Implementation

```yaml
# rulepacks/in-works/boq/trade_checklists/civil_structure.yaml
id: civil_structure
trade: civil
confidence: unvalidated
source: >
  CPWD Works Manual — standard civil work sequences (excavation → dewatering →
  anti-termite → backfill); common omission lists in published QS guidance.
items:
  - key: dewatering
    label: Dewatering
    severity: high
    triggers: ["basement", "below ground water table", "sub-soil water", "deep excavation"]
    boq_patterns: ["dewater", "well point", "pumping of water"]
  - key: shoring
    label: Shoring / earth retention
    severity: high
    triggers: ["deep excavation", "adjacent structure", "excavation exceeding 3", "sheet pil"]
    boq_patterns: ["shoring", "sheet pile", "earth retention", "strutting"]
  - key: anti_termite
    label: Anti-termite treatment
    severity: medium
    triggers: ["foundation", "plinth", "substructure"]
    boq_patterns: ["anti-termite", "anti termite", "termite treatment"]
```

Detection logic: if a `trigger` phrase appears in the spec/BOQ narrative but
none of that item's `boq_patterns` appear as a line item, it's a candidate
scope gap — flagged deterministically by code, not an LLM judgment call.

The three files: `civil_structure.yaml`, `electrical.yaml`, `hvac.yaml`,
each under `rulepacks/in-works/boq/trade_checklists/`.

## Files touched

- `rulepacks/in-works/boq/trade_checklists/{civil_structure,electrical,hvac}.yaml`

## Tests

Exercised indirectly by `scripts/phase0_accuracy_test.py` (TS-006).

## Acceptance criteria

- [x] 3 trade checklists exist, each with `source:` and `confidence:`.
- [x] Each item has `triggers` (when it applies) and `boq_patterns` (how to
      detect its presence), enabling deterministic gap detection.

## Commit

Predates commit-granular history (PR #10 bulk import).
