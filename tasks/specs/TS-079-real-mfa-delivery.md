# TS-079 — Real email/SMS delivery for `email`/`sms` MFA and OTP codes

**Status:** todo (needs creds)
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** `auth`, `notifications`
**Severity / Gate:** P2 · Phase 1 (remaining)

## What this builds

Wires TS-077's `email`/`sms` MFA methods (and TS-036's planned phone OTP) to
an actual delivery channel — today the code path is a real one, but the
send itself is console-logged (TS-074's spec explicitly listed real
email/SMS 2FA delivery as out of scope until credentials exist).

## Implementation (reference plan — not yet built; blocked on provider creds)

- Reuse the `notifications.Sender` protocol and TS-035's planned
  SES/Resend/MSG91 adapters rather than building a parallel send path for
  MFA codes specifically.
- `auth.mfa`'s email/sms code generation stays as-is; only the delivery
  call changes from `ConsoleSender` to a real `Sender` once TS-035 lands.

## Files touched (planned)

- `backend/app/modules/auth/mfa.py` (delivery call site)
- Depends on `backend/app/modules/notifications/sender.py` (TS-035)

## Tests (planned)

- Integration test with a mocked real sender confirming the code reaches
  the configured channel.

## Acceptance criteria

- [ ] An `email`/`sms` MFA enrollment delivers the code via a real
      provider, not console logging, once credentials are configured.

## Commit

Not yet implemented — blocked on provider credentials (same blocker as
TS-035).
