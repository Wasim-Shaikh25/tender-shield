# TS-061 — Spec: `notifications` module

**Status:** done
**Requirement:** spec audit; Doc §11.6, §11.7
**Spec(s) updated:** `specs/modules/notifications.md`
**Module(s):** `notifications`
**Severity / Gate:** P1 · Spec audit

## What this builds

A spec-audit finding: TS-027's digest/sender abstraction had no dedicated
module spec.

## Implementation

`specs/modules/notifications.md` written against the real implementation:
`digest.deadlines_to_alert`/`format_digest`, the `Sender` protocol, and
`ConsoleSender` as the dev-mode implementation (matching TS-027).

## Files touched

- `specs/modules/notifications.md` (new)

## Tests

None — documentation task.

## Acceptance criteria

- [x] `specs/modules/notifications.md` documents the `Sender` interface and
      digest logic matching the real code.

## Commit

Predates commit-granular history (PR #10 bulk import).
