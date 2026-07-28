"use client";

// Route protection (R-010 §B.7). Before this, an unauthenticated visit to a
// protected page just rendered whatever the page's own `if (!session)` guard
// happened to show (usually a broken or empty state), never a redirect —
// and `status` being a real three-state (not just `session` truthiness)
// means a signed-in user reloading the page never flashes "signed out"
// while the refresh round-trip resolves (R-010 §B8).

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/components/session";

const ROLE_RANK: Record<string, number> = {
  viewer: 0,
  reviewer: 1,
  estimator: 2,
  admin: 3,
  owner: 4,
};

function roleAtLeast(role: string | undefined, min: string): boolean {
  if (!role) return false;
  return (ROLE_RANK[role] ?? -1) >= (ROLE_RANK[min] ?? 0);
}

export function RequireAuth({
  children,
  minRole = "viewer",
}: {
  children: React.ReactNode;
  minRole?: string;
}) {
  const { session, status } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, pathname, router]);

  if (status === "loading") {
    return <div className="animate-pulse text-sm text-slate-400">Loading…</div>;
  }
  if (status === "unauthenticated" || !session) return null;
  if (!session.is_superadmin && !roleAtLeast(session.role, minRole)) {
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
        This page needs the &ldquo;{minRole}&rdquo; role or higher.
      </p>
    );
  }
  return <>{children}</>;
}
