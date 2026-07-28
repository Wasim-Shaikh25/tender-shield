// Session plumbing outside React (R-010): token storage, single-flight
// refresh, multi-tab coordination. Kept framework-free so both
// components/session.tsx (the React state owner) and lib/api.ts (the plain
// fetch wrapper, which cannot use hooks) can share one source of truth
// without a dependency cycle between them.

import { API_BASE } from "./config";
import { SessionExpired } from "./errors";

export type Tokens = {
  access_token: string;
  refresh_token: string;
  role: string;
  workspace_id: string;
  is_superadmin?: boolean;
};

// Phase 1 (R-010 §B.1): the access token is never persisted — memory only,
// held in React state. The refresh token IS persisted (it must survive a
// reload) until Phase 2 moves it to an httpOnly cookie set by the backend.
const REFRESH_KEY = "ts_refresh";
// Non-sensitive first-paint hint only — role/workspace, never a credential —
// so a reload can render the shell before the refresh round-trip resolves.
const HINT_KEY = "ts_hint";

export type SessionHint = { role: string; workspaceId: string; is_superadmin?: boolean };

function hasStorage(): boolean {
  return typeof window !== "undefined";
}

export function loadRefreshToken(): string | null {
  return hasStorage() ? localStorage.getItem(REFRESH_KEY) : null;
}

export function storeRefreshToken(token: string): void {
  if (hasStorage()) localStorage.setItem(REFRESH_KEY, token);
}

export function clearRefreshToken(): void {
  if (hasStorage()) localStorage.removeItem(REFRESH_KEY);
}

export function loadHint(): SessionHint | null {
  if (!hasStorage()) return null;
  const raw = localStorage.getItem(HINT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionHint;
  } catch {
    return null;
  }
}

export function storeHint(hint: SessionHint): void {
  if (hasStorage()) localStorage.setItem(HINT_KEY, JSON.stringify(hint));
}

export function clearHint(): void {
  if (hasStorage()) localStorage.removeItem(HINT_KEY);
}

/** Decode a JWT's `exp` claim to an epoch-ms timestamp. Display/scheduling
 * hint only — never a trust boundary; the server verifies the signature (and
 * expiry) on every request regardless of what the client thinks it decoded. */
export function decodeExpiry(jwt: string): number {
  try {
    const payload = jwt.split(".")[1];
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof json.exp === "number" ? json.exp * 1000 : Date.now() + 60_000;
  } catch {
    return Date.now() + 60_000;
  }
}

type TokensListener = (tokens: Tokens) => void;
const tokensListeners = new Set<TokensListener>();

/** Notified on EVERY successful refresh, whether triggered proactively (the
 * scheduled timer in SessionProvider) or reactively (a 401 retry inside
 * lib/api.ts's req(), which has no access to React state). Without this, a
 * reactive refresh would keep requests working but leave the React-held
 * session's token stale until the next proactive tick. */
export function onTokensRefreshed(fn: TokensListener): () => void {
  tokensListeners.add(fn);
  return () => tokensListeners.delete(fn);
}

const SESSION_EXPIRED_EVENT = "ts:session-expired";

/** Dispatched when a refresh fails outright (expired/revoked refresh token).
 * lib/api.ts's req() has no router/React access to redirect on its own;
 * SessionProvider listens for this event and drives the actual sign-out +
 * redirect, so a 401 encountered from ANY call site — not just the one the
 * user happens to be looking at — ends the session immediately. */
export function notifySessionExpired(): void {
  if (hasStorage()) window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export function onSessionExpired(fn: () => void): () => void {
  if (!hasStorage()) return () => {};
  const handler = () => fn();
  window.addEventListener(SESSION_EXPIRED_EVENT, handler);
  return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
}

let inflight: Promise<Tokens> | null = null;

/** Refresh the access token, collapsing concurrent callers into ONE request.
 *
 * The backend revokes the whole refresh-token family when a refresh token is
 * replayed (auth/refresh.py reuse detection — R-002 §B). Two callers racing
 * to refresh the same stored token would look exactly like a replay to the
 * server, so single-flight here is a correctness requirement, not an
 * optimization (R-010 §B.2) — it also collapses races across browser tabs,
 * since they share the same localStorage-held refresh token.
 */
export function refreshTokens(): Promise<Tokens> {
  if (inflight) return inflight;
  const stored = loadRefreshToken();
  if (!stored) return Promise.reject(new SessionExpired());

  inflight = fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: stored }),
  })
    .then(async (res) => {
      if (!res.ok) {
        // The server rejected the refresh token itself (expired/revoked/
        // reused) — the session is genuinely over, not just unreachable.
        notifySessionExpired();
        throw new SessionExpired();
      }
      const tokens = (await res.json()) as Tokens;
      storeRefreshToken(tokens.refresh_token); // rotated — the old one is now dead
      tokensListeners.forEach((fn) => fn(tokens));
      return tokens;
    })
    // A network-level failure (offline, DNS, CORS) propagates as-is rather
    // than being treated as SessionExpired — a proactive refresh that
    // couldn't reach the server should be retried, not treated as a revoked
    // session; only reactive callers (lib/api.ts) that need a definite
    // outcome catch and normalize this further.
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

/** Best-effort: revokes the refresh-token family server-side (R-010 §B.6).
 * `keepalive` lets the request survive the navigation signOut triggers. */
export async function logoutServerSide(): Promise<void> {
  const refresh = loadRefreshToken();
  if (!refresh) return;
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
    keepalive: true,
  }).catch(() => {});
}

// ---- multi-tab coordination (R-010 §B.5) --------------------------------
// A refresh (or sign-out) in one tab must be reflected in every other open
// tab — otherwise a second tab keeps using a refresh token the first tab
// already rotated away, and the NEXT refresh from that stale tab reads as a
// replay to the backend (the exact family-revocation scenario B.2 guards
// against, just relocated across tabs instead of across requests).
export type BroadcastMessage = { type: "tokens"; tokens: Tokens } | { type: "signout" };

export function openBroadcastChannel(onMessage: (msg: BroadcastMessage) => void): {
  post: (msg: BroadcastMessage) => void;
  close: () => void;
} {
  if (!hasStorage() || !("BroadcastChannel" in window)) {
    return { post: () => {}, close: () => {} };
  }
  const channel = new BroadcastChannel("ts_session");
  channel.onmessage = (e: MessageEvent<BroadcastMessage>) => onMessage(e.data);
  return {
    post: (msg) => channel.postMessage(msg),
    close: () => channel.close(),
  };
}
