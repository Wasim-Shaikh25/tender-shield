# TS-065 — Align `risk` public interface with code

**Status:** done
**Requirement:** spec audit; Doc §6.3
**Spec(s) updated:** `specs/modules/risk.md`
**Module(s):** `risk`
**Severity / Gate:** P2 · Spec audit

## What this builds

A spec-audit finding: `risk.md`'s public-interface section hadn't caught up
with TS-054's `explanation` object addition or the exact capabilities
`risk/module.py` publishes.

## Implementation

Updated `specs/modules/risk.md` to document the `explanation` object shape
(`_build_explanation`, TS-054) as part of the `Finding` output, and to list
the real published capabilities matching `risk/module.py`'s `reg.provide()`
calls.

## Files touched

- `specs/modules/risk.md`

## Tests

None — documentation-only correction.

## Acceptance criteria

- [x] The spec's `Finding` output shape includes `explanation`, matching
      `_build_explanation`'s real fields.

## Commit

Predates commit-granular history (PR #10 bulk import).
