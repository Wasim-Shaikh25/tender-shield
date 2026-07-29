# TS-066 — Align `drafting` public interface with code

**Status:** done
**Requirement:** spec audit; Doc §6.5
**Spec(s) updated:** `specs/modules/drafting.md`
**Module(s):** `drafting`
**Severity / Gate:** P2 · Spec audit

## What this builds

A spec-audit finding: `drafting.md` hadn't caught up with the `bid_decision`
artifact kind (TS-048) added after the spec's initial draft.

## Implementation

Updated `specs/modules/drafting.md`'s "Public interface"/"Behavior" sections
to document all three artifact kinds `generator.build_body` supports
(`clarification`, `assumptions`, `bid_decision`) and the validators
(`validators.validate`) every kind passes through before storage.

## Files touched

- `specs/modules/drafting.md`

## Tests

None — documentation-only correction.

## Acceptance criteria

- [x] All three artifact kinds `build_body` dispatches on are documented in
      the spec.

## Commit

Predates commit-granular history (PR #10 bulk import).
