"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "./session";

const PUBLIC_PATHS = ["/login", "/forgot-password", "/reset-password"];

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    if (!loading && !isPublic && !session) {
      router.replace("/login");
    }
  }, [loading, isPublic, session, router]);

  if (!isPublic && (loading || !session)) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-slate-500">Loading session…</p>
      </div>
    );
  }

  return children;
}
