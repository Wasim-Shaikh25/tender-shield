# R-010 — Frontend session: refresh tokens, 401 recovery, token custody

**Status:** implemented (TS-092), Phase 1 (see `specs/frontend.md` B12 for
behavior/acceptance criteria; Phase 2's httpOnly-cookie move is tracked
separately under R-016).
**Severity:** P0 — every session dies 15 minutes after login
**Requirement refs:** Doc §5, §9
**Task refs:** TS-092
**Gap refs:** `docs/GAP_ANALYSIS.md` §4.2, §4.3
**Specs to update:** `specs/frontend.md`

## Purpose

The frontend discards the refresh token it is handed at login. Access tokens live
15 minutes (`access_ttl_minutes`, `core/config.py:24`), so **every user is
hard-logged-out mid-work with no recovery path**, and there is no 401 interceptor
to even detect it — requests just start failing with raw error strings.

The product's own NFR is 25-minute p95 processing for an 800-page pack
(`specs/000-product-overview.md`). The session expires before the primary
workflow finishes. This is the single most visible functional bug in the app.

## Current

```tsx
// frontend/components/session.tsx:27
const signIn = (t: Tokens) => {
  const s = { token: t.access_token, role: t.role, workspaceId: t.workspace_id,
              is_superadmin: t.is_superadmin };
  setSession(s);
  localStorage.setItem("ts_session", JSON.stringify(s));   // ← t.refresh_token dropped
};
```

```ts
// frontend/lib/api.ts:33
async function req<T>(path: string, opts: RequestInit = {}, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ... });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);   // ← 401 = generic error
  }
  return res.json() as Promise<T>;
}
```

`POST /api/auth/refresh` exists and implements rotation with reuse detection
(`auth/service.py:96`) — a genuinely good implementation with no client.

## Target

### B.1 Token custody

The file's own comment already states the target
(`session.tsx:6`): *"Production keeps the refresh token in an httpOnly cookie and
the access token in memory only (Doc §5)."*

Two-phase, because the httpOnly move needs backend cookie support:

**Phase 1 (ships with this task).** Access token in memory; refresh token in
`localStorage`; a short "session hint" for reload continuity. This is strictly
better than today — the access token, the credential that actually authorizes
requests, stops being persisted at all.

**Phase 2 (with R-016 deployment work).** Refresh token moves to an httpOnly,
`SameSite=Strict`, `Secure` cookie set by `/auth/login`; `/auth/refresh` reads it
from the cookie. The client then holds nothing an XSS can steal. This requires
same-site deployment or a CORS credentials configuration, hence the split.

```tsx
// frontend/components/session.tsx

type Session = {
  token: string;                 // access token — MEMORY ONLY, never persisted
  role: string;
  workspaceId: string;
  isSuperadmin: boolean;
  expiresAt: number;             // epoch ms, decoded from the JWT
};

const REFRESH_KEY = "ts_refresh";   // Phase 2: replaced by an httpOnly cookie
const HINT_KEY = "ts_hint";         // non-sensitive: {workspaceId, role} for first paint
```

### B.2 Single-flight refresh

Concurrent 401s must not each trigger a refresh — the backend's reuse detection
(`refresh.evaluate_refresh`, `auth/refresh.py`) treats a replayed refresh token
as a compromised family and **revokes every session**. A naive
refresh-per-request implementation would log the user out for being fast.

```tsx
// frontend/lib/auth-client.ts

let inflight: Promise<Tokens> | null = null;

/** Refresh the access token, collapsing concurrent callers into one request.
 *
 *  The backend revokes the whole token family when a refresh token is replayed
 *  (auth/refresh.py reuse detection). Two parallel refreshes would look exactly
 *  like a replay, so single-flight is a correctness requirement, not an
 *  optimisation (R-010 §B.2). */
export function refreshTokens(): Promise<Tokens> {
  if (inflight) return inflight;
  const stored = localStorage.getItem(REFRESH_KEY);
  if (!stored) return Promise.reject(new SessionExpired());

  inflight = fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: stored }),
  })
    .then(async (res) => {
      if (!res.ok) throw new SessionExpired();
      const tokens: Tokens = await res.json();
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);   // rotated
      return tokens;
    })
    .finally(() => { inflight = null; });

  return inflight;
}
```

### B.3 Proactive refresh + reactive retry

Both, because either alone leaves a hole: proactive refresh fails if the tab was
asleep; reactive retry alone means the user's first action after 15 minutes is
always slow.

```ts
const REFRESH_SKEW_MS = 60_000;   // refresh a minute before expiry

async function req<T>(path: string, opts: RequestInit = {}, auth?: AuthContext): Promise<T> {
  if (auth && auth.expiresAt - Date.now() < REFRESH_SKEW_MS) {
    await auth.refresh();                     // proactive
  }

  let res = await fetch(`${API_BASE}${path}`, withAuth(opts, auth));

  if (res.status === 401 && auth && !opts.__retried) {
    try {
      await auth.refresh();                   // reactive
      res = await fetch(`${API_BASE}${path}`, { ...withAuth(opts, auth), __retried: true });
    } catch {
      auth.signOut("expired");
      throw new SessionExpired();
    }
  }

  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
}
```

Retry exactly once. A retry loop against a genuinely revoked session hammers the
API and hides the real problem.

### B.4 Typed errors, not `new Error(string)`

The current `throw new Error(body.detail)` is why users see `free_exhausted`
rendered as an error message (`login/page.tsx:29`). The 402 paywall payload
(R-004) is an object, so `body.detail` is `[object Object]` today.

```ts
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly detail: unknown,
  ) { super(code); }
}

export class SessionExpired extends ApiError {
  constructor() { super(401, "session_expired", null); }
}

export class PaywallError extends ApiError {
  constructor(readonly upsell: Record<string, unknown>, code: string) {
    super(402, code, upsell);
  }
}

async function toApiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  const detail = body.detail;
  if (res.status === 402 && detail && typeof detail === "object") {
    return new PaywallError(detail.upsell ?? {}, detail.code ?? "payment_required");
  }
  const code = typeof detail === "string" ? detail : (detail?.code ?? `http_${res.status}`);
  return new ApiError(res.status, code, detail);
}
```

`ApiError.code` then maps to human copy through one table (R-014 §C).

### B.5 Multi-tab coordination

Two tabs refreshing independently is the replay scenario from §B.2 again, across
tabs. Coordinate with a `BroadcastChannel`, falling back to a `storage` event:

```ts
const channel = "BroadcastChannel" in window ? new BroadcastChannel("ts_session") : null;
channel?.addEventListener("message", (e) => {
  if (e.data.type === "tokens") adoptTokens(e.data.tokens);   // no refresh of our own
  if (e.data.type === "signout") hardSignOut();
});
```

Signing out in one tab must sign out every tab.

### B.6 Logout must reach the server

`signOut` currently only clears `localStorage` (`session.tsx:32`). The refresh
family stays valid server-side until it expires — up to 30 days.

```ts
async function signOut(reason?: "expired" | "user") {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (refresh) {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      keepalive: true,        // survives navigation
    }).catch(() => {});       // best effort: local state clears regardless
  }
  hardSignOut();
  channel?.postMessage({ type: "signout" });
}
```

### B.7 Route protection

There is no route guard today — an unauthenticated user reaching
`/opportunities` sees a broken page rather than a redirect.

```tsx
// frontend/components/require-auth.tsx
export function RequireAuth({ children, minRole = "viewer" }: Props) {
  const { session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, pathname, router]);

  if (status === "loading") return <PageSkeleton />;
  if (status === "unauthenticated") return null;
  if (!roleAtLeast(session.role, minRole)) return <InsufficientRole required={minRole} />;
  return <>{children}</>;
}
```

`status` must be a real three-state (`loading | authenticated | unauthenticated`).
Today `session` is `null` both before and after the `useEffect` hydration
(`session.tsx:22`), so a logged-in user briefly looks logged out on every reload.

## Behavior

- **B1** The access token lives in memory only and is never written to storage.
- **B2** The refresh token is persisted (Phase 1) or held in an httpOnly cookie
  (Phase 2) and rotated on every use.
- **B3** Refreshes are single-flight across concurrent requests and across tabs.
- **B4** The client refreshes proactively before expiry and reactively on one 401.
- **B5** A failed refresh signs out cleanly and redirects to `/login?next=…`.
- **B6** Logout revokes the family server-side and propagates to every tab.
- **B7** API errors are typed; 402 carries the upsell payload as an object.
- **B8** Session state is three-valued so first paint never flashes signed-out.

## Acceptance criteria

- **A1** After login, `localStorage` contains no access token.
- **A2** With the access token expired, a data call succeeds transparently and
  the refresh endpoint is called exactly once.
- **A3** Five concurrent calls with an expired token trigger exactly one refresh
  and no family revocation.
- **A4** A revoked refresh token produces one redirect to `/login`, not a loop.
- **A5** Signing out in tab A signs out tab B within 1s.
- **A6** After sign-out, the old refresh token returns `401 invalid_refresh`.
- **A7** A 402 surfaces as `PaywallError` with `.upsell` populated.
- **A8** Reloading while signed in never renders the signed-out state.
- **A9** An unauthenticated visit to `/opportunities` redirects to
  `/login?next=%2Fopportunities` and returns there after login.
- **A10** A session survives ≥ 60 minutes of continuous use without re-login.

## Test scaffolding

There is **no frontend test framework at all** today (R-014 §E). This task adds
Vitest + Testing Library and is a natural first consumer:

```ts
it("collapses concurrent refreshes into one request", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(unauthorized())
    .mockResolvedValueOnce(unauthorized())
    .mockResolvedValueOnce(refreshOk())
    .mockResolvedValue(ok({}));
  await Promise.all([api.listOpportunities(), api.listOpportunities()]);
  expect(fetchMock.mock.calls.filter(([u]) => String(u).endsWith("/auth/refresh"))).toHaveLength(1);
});
```

## Out of scope

- The httpOnly cookie migration (Phase 2) — needs backend cookie support and a
  CORS/credentials decision, tracked in R-016.
- Idle timeout and absolute session lifetime.
- Device/session management UI — R-002 §B.3 provides the endpoints; R-013 the UI.

## Assumptions

- `assumption:` 15-minute access TTL and 30-day refresh TTL stay as configured.
