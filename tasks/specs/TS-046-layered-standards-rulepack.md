# TS-046 — Layered contract-standards rulepack + standards-aware notice register

**Status:** done
**Requirement:** Doc §0.1, §2, §10
**Spec(s) updated:** `specs/modules/rulepacks.md`, `specs/modules/baseline.md`
**Module(s):** `rulepacks`, `baseline`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

A universal-base + regional-overlay rule-pack layering scheme (e.g. FIDIC as
the universal base, a jurisdiction overlay merged at load time), and wires
TS-041's notice register to flag gaps against the *expected* regime for a
given contract standard — not just extract whatever notice language is
literally present.

## Implementation

Merge-at-load: the universal base pack's notice-period expectations (FIDIC
28 days, NEC 56 days, MSMED 45 days — researched real figures) are
overridden per-field by any regional overlay pack present, producing one
effective rule set per contract standard. `baseline.notices` compares the
tender's actual notice language against this expected regime and flags a
gap when the tender is silent or diverges.

## Files touched

- `rulepacks/in-works/notice_standards/` (universal + overlay packs)
- `backend/app/modules/baseline/notices.py` (expected-regime comparison)

## Tests

- `backend/tests/modules/baseline/test_notices.py::test_expected_regime_gap`

## Acceptance criteria

- [x] A regional overlay pack overrides only the fields it defines; the
      universal base fills the rest.
- [x] A tender silent on a notice period the expected regime requires
      produces a gap finding, not a false "no issue."

## Commit

Predates commit-granular history (PR #10 bulk import).
