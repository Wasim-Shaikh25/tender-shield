"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Tokens } from "@/lib/api";
import {
  type BroadcastMessage,
  clearHint,
  clearRefreshToken,
  decodeExpiry,
  loadRefreshToken,
  logoutServerSide,
  onSessionExpired,
  onTokensRefreshed,
  openBroadcastChannel,
  refreshTokens,
  storeHint,
  storeRefreshToken,
} from "@/lib/auth-client";

// R-010: access token in memory only (never localStorage — see auth-client's
// REFRESH_KEY/HINT_KEY comments for what IS persisted and why); refreshed
// proactively before expiry and reactively on a 401 (lib/api.ts). `status` is
// a real three-state so a reload never flashes "signed out" before the
// refresh round-trip resolves (R-010 §B8) — `session` alone can't carry that
// distinction because it's legitimately null in both the loading and the
// truly-signed-out case.
type Session = {
  token: string;
  role: string;
  workspaceId: string;
  is_superadmin?: boolean;
} | null;

type Status = "loading" | "authenticated" | "unauthenticated";

type Ctx = {
  session: Session;
  status: Status;
  signIn: (t: Tokens) => void;
  signOut: () => void;
};

const SessionContext = createContext<Ctx>({
  session: null,
  status: "loading",
  signIn: () => {},
  signOut: () => {},
});

const REFRESH_SKEW_MS = 60_000; // refresh a minute before expiry (R-010 §B.3)

function toSession(tokens: Tokens): Session {
  return {
    token: tokens.access_token,
    role: tokens.role,
    workspaceId: tokens.workspace_id,
    is_superadmin: tokens.is_superadmin,
  };
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session>(null);
  const [status, setStatus] = useState<Status>("loading");
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Real channel opened by the effect below; this inert default exists only
  // so callers before that effect runs have something safe to call `.post`
  // on (it never actually connects a channel — see openBroadcastChannel).
  const broadcast = useRef<{ post: (msg: BroadcastMessage) => void; close: () => void }>({
    post: () => {},
    close: () => {},
  });

  const scheduleProactiveRefresh = useCallback((accessToken: string) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const delay = Math.max(decodeExpiry(accessToken) - Date.now() - REFRESH_SKEW_MS, 0);
    refreshTimer.current = setTimeout(() => {
      refreshTokens().catch(() => {
        // onSessionExpired (registered below) drives the actual sign-out;
        // nothing further to do here on failure.
      });
    }, delay);
  }, []);

  const adoptTokens = useCallback(
    (tokens: Tokens, opts: { broadcast: boolean } = { broadcast: true }) => {
      setSession(toSession(tokens));
      setStatus("authenticated");
      storeHint({
        role: tokens.role,
        workspaceId: tokens.workspace_id,
        is_superadmin: tokens.is_superadmin,
      });
      scheduleProactiveRefresh(tokens.access_token);
      if (opts.broadcast) broadcast.current.post({ type: "tokens", tokens });
    },
    [scheduleProactiveRefresh]
  );

  const hardSignOut = useCallback(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    clearRefreshToken();
    clearHint();
    setSession(null);
    setStatus("unauthenticated");
  }, []);

  const signIn = useCallback(
    (t: Tokens) => {
      storeRefreshToken(t.refresh_token);
      adoptTokens(t);
    },
    [adoptTokens]
  );

  const signOut = useCallback(() => {
    logoutServerSide(); // best-effort, fire-and-forget (R-010 §B.6)
    hardSignOut();
    broadcast.current.post({ type: "signout" });
  }, [hardSignOut]);

  // First paint: `status` starts "loading" (not "unauthenticated") whenever a
  // refresh token exists, so a route guard gated on `status` (not `session`)
  // never flashes signed-out while this resolves (R-010 §B8) — `session`
  // itself stays null until a real access token is confirmed, deliberately;
  // there is no optimistic/placeholder session, since anything reading
  // `session.token` before that would fire a request with no real bearer.
  useEffect(() => {
    if (!loadRefreshToken()) {
      setStatus("unauthenticated");
      return;
    }
    refreshTokens()
      .then((tokens) => adoptTokens(tokens, { broadcast: false }))
      .catch(() => hardSignOut());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reactive refreshes triggered from lib/api.ts (a 401 the React tree never
  // sees directly) must still update this session's token, or the app keeps
  // paying a refresh round-trip on every request instead of just the one
  // that caught the 401.
  useEffect(() => onTokensRefreshed((tokens) => adoptTokens(tokens, { broadcast: true })), [adoptTokens]);

  // A refresh that fails outright (expired/revoked token) — signal fired
  // from lib/auth-client.ts, which has no router/React access of its own.
  useEffect(() => onSessionExpired(() => { hardSignOut(); broadcast.current.post({ type: "signout" }); }), [hardSignOut]);

  // Multi-tab coordination (R-010 §B.5): a channel opened once per provider
  // instance, wired to the CURRENT adoptTokens/hardSignOut on every render.
  useEffect(() => {
    const channel = openBroadcastChannel((msg) => {
      if (msg.type === "tokens") adoptTokens(msg.tokens, { broadcast: false });
      if (msg.type === "signout") hardSignOut();
    });
    broadcast.current = channel;
    return () => channel.close();
  }, [adoptTokens, hardSignOut]);

  return (
    <SessionContext.Provider value={{ session, status, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export const useSession = () => useContext(SessionContext);
