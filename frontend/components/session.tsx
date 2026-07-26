"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Tokens } from "@/lib/api";

// Skeleton simplification: access token kept in memory + mirrored to
// localStorage so a reload survives. Production keeps the refresh token in an
// httpOnly cookie and the access token in memory only (Doc §5).
type Session = { token: string; role: string; workspaceId: string; is_superadmin?: boolean } | null;

type Ctx = {
  session: Session;
  signIn: (t: Tokens) => void;
  signOut: () => void;
};

const SessionContext = createContext<Ctx>({ session: null, signIn: () => {}, signOut: () => {} });

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session>(null);

  useEffect(() => {
    const raw = localStorage.getItem("ts_session");
    if (raw) setSession(JSON.parse(raw));
  }, []);

  const signIn = (t: Tokens) => {
    const s = { token: t.access_token, role: t.role, workspaceId: t.workspace_id, is_superadmin: t.is_superadmin };
    setSession(s);
    localStorage.setItem("ts_session", JSON.stringify(s));
  };
  const signOut = () => {
    setSession(null);
    localStorage.removeItem("ts_session");
  };

  return (
    <SessionContext.Provider value={{ session, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export const useSession = () => useContext(SessionContext);
