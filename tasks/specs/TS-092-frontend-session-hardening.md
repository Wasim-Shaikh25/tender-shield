# TS-092 — Persist + rotate refresh tokens; single-flight refresh; 401 retry; typed errors; route guards

**Status:** done
**Requirement:** [R-010](../../specs/requirements/R-010-frontend-session.md)
**Spec(s) updated:** none
**Module(s):** frontend
**Severity / Gate:** P0 · Gate 2

## What this builds

A full frontend session-management hardening pass: token custody, refresh
that doesn't trigger the backend's reuse-detection lockout, typed API
errors instead of `[object Object]` strings, multi-tab coordination,
logout that actually reaches the server, and route protection (previously
none at all — an unauthenticated user hitting `/opportunities` saw a broken
page, not a redirect).

## Implementation

```tsx
// frontend/components/session.tsx — token custody (Phase 1 of 2; httpOnly
// cookie is Phase 2, needs backend cookie support / R-016 deployment work)
type Session = {
  token: string;    // access token — MEMORY ONLY, never persisted
  expiresAt: number;
};
const REFRESH_KEY = "ts_refresh";
```

```ts
// frontend/lib/auth-client.ts — single-flight refresh
let inflight: Promise<Tokens> | null = null;

/** Collapses concurrent refresh calls into one request. The backend
 * revokes the WHOLE token family when a refresh token is replayed
 * (auth/refresh.py reuse detection) — two parallel refreshes look exactly
 * like a replay, so this is a correctness requirement, not an optimization. */
export function refreshTokens(): Promise<Tokens> {
  if (inflight) return inflight;
  inflight = fetch(`${API_BASE}/auth/refresh`, {...})
    .then(async (res) => { ...; localStorage.setItem(REFRESH_KEY, tokens.refresh_token); return tokens; })
    .finally(() => { inflight = null; });
  return inflight;
}
```

```ts
// proactive (a minute before expiry) + reactive (401 retry, exactly once) —
// either alone leaves a hole: proactive fails if the tab was asleep,
// reactive alone makes the first action after 15 minutes always slow
const REFRESH_SKEW_MS = 60_000;
async function req<T>(path, opts, auth): Promise<T> {
  if (auth && auth.expiresAt - Date.now() < REFRESH_SKEW_MS) await auth.refresh();
  let res = await fetch(...);
  if (res.status === 401 && !opts.__retried) {
    await auth.refresh();
    res = await fetch(..., { __retried: true });
  }
  ...
}
```

```ts
// typed errors — current `throw new Error(body.detail)` renders the 402
// paywall object (R-004) as literal "[object Object]"
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, readonly detail: unknown) { super(code); }
}
export class PaywallError extends ApiError {
  constructor(readonly upsell: Record<string, unknown>, code: string) { super(402, code, upsell); }
}
```

```ts
// multi-tab coordination — two tabs refreshing independently is the same
// replay scenario, across tabs
const channel = new BroadcastChannel("ts_session");
channel.addEventListener("message", (e) => {
  if (e.data.type === "tokens") adoptTokens(e.data.tokens);   // no refresh of our own
  if (e.data.type === "signout") hardSignOut();
});
```

```ts
// logout must reach the server — signOut previously only cleared
// localStorage; the refresh family stayed valid server-side for 30 days
async function signOut(reason) {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (refresh) await fetch(`${API_BASE}/auth/logout`, { body: JSON.stringify({ refresh_token: refresh }), keepalive: true }).catch(() => {});
  hardSignOut();
  channel.postMessage({ type: "signout" });
}
```

```tsx
// frontend/components/require-auth.tsx — route protection, previously none
export function RequireAuth({ children, minRole = "viewer" }: Props) {
  const { session, status } = useSession();   // real 3-state: loading|authenticated|unauthenticated
  useEffect(() => {
    if (status === "unauthenticated") router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [status]);
  if (status === "loading") return <PageSkeleton />;
  if (!roleAtLeast(session.role, minRole)) return <InsufficientRole required={minRole} />;
  return <>{children}</>;
}
```

## Files touched

- `frontend/components/{session,require-auth}.tsx`
- `frontend/lib/{auth-client,api}.ts`

## Tests

None recorded — frontend component/e2e tests are a separate, later concern.

## Acceptance criteria (frontend.md A7–A15)

- [x] Two concurrent 401s trigger exactly one refresh request, not two.
- [x] A 402 paywall error renders its structured upsell payload, not
      `[object Object]`.
- [x] Signing out in one tab signs out every open tab.
- [x] Logout reaches the server (revokes the refresh family), not just
      local storage.
- [x] An unauthenticated user hitting a protected route is redirected to
      `/login?next=...`, not shown a broken page.

## Commit

Predates commit-granular history (PR #10 bulk import).
