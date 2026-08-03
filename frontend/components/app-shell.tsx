"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "./session";

const PUBLIC_PATHS = ["/login", "/forgot-password", "/reset-password"];

type NavItem = { label: string; href: string };

const MAIN_NAV: NavItem[] = [
  { label: "Dashboard", href: "/dashboard/state" },
  { label: "Opportunities", href: "/opportunities" },
  { label: "Projects", href: "/projects" },
  { label: "Analytics", href: "/analytics" },
  { label: "Control Tower", href: "/controltower" },
  { label: "Plan", href: "/plan" },
  { label: "AI Assistant", href: "/assistant" },
  { label: "Rulepacks", href: "/rulepacks" },
  { label: "Standards", href: "/standards" },
  { label: "Help", href: "/help" },
];

const ACCOUNT_NAV: NavItem[] = [
  { label: "Team", href: "/team" },
  { label: "Settings", href: "/settings" },
  { label: "Billing", href: "/billing" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));
  const [mobileOpen, setMobileOpen] = useState(false);
  const { session, workspaces, activeWorkspace, switchWorkspace, signOut, loading } = useSession();

  if (isPublic) return <>{children}</>;

  async function handleSignOut() {
    await signOut();
    router.push("/login");
  }

  const NavLink = ({ href, label, onClick }: { href: string; label: string; onClick?: () => void }) => {
    const active = pathname === href || pathname?.startsWith(`${href}/`);
    return (
      <Link
        href={href}
        onClick={onClick}
        className={`block rounded-md px-3 py-2 text-sm font-medium transition ${
          active
            ? "bg-slate-100 text-ink"
            : "text-slate-600 hover:bg-slate-50 hover:text-ink"
        }`}
      >
        {label}
      </Link>
    );
  };

  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-100 p-4">
        <Link href="/" className="flex items-center gap-2 font-bold text-ink" onClick={() => setMobileOpen(false)}>
          <span className="grid h-7 w-7 place-items-center rounded-md bg-ink text-sm text-white">TS</span>
          <span className="truncate">TenderShield</span>
        </Link>
        <button
          type="button"
          className="rounded-md p-1 text-slate-400 hover:bg-slate-100 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close sidebar"
        >
          Close
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {session && workspaces.length > 1 ? (
          <select
            value={activeWorkspace?.workspace_id ?? ""}
            onChange={(e) => switchWorkspace(e.target.value)}
            className="mb-4 w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm outline-none focus:border-ink"
          >
            {workspaces.map((w) => (
              <option key={w.workspace_id} value={w.workspace_id}>
                {w.name} · {w.plan}
              </option>
            ))}
          </select>
        ) : activeWorkspace ? (
          <div className="mb-4 truncate rounded-md bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
            {activeWorkspace.name}
          </div>
        ) : null}

        <nav className="space-y-1">
          {MAIN_NAV.map((item) => (
            <NavLink key={item.href} href={item.href} label={item.label} onClick={() => setMobileOpen(false)} />
          ))}
        </nav>

        <div className="mt-6 border-t border-slate-100 pt-4">
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Account</p>
          <nav className="space-y-1">
            {ACCOUNT_NAV.map((item) => (
              <NavLink key={item.href} href={item.href} label={item.label} onClick={() => setMobileOpen(false)} />
            ))}
            {session?.is_superadmin && (
              <NavLink href="/admin" label="Admin" onClick={() => setMobileOpen(false)} />
            )}
          </nav>
        </div>
      </div>

      <div className="border-t border-slate-100 p-3">
        {session ? (
          <button
            type="button"
            onClick={handleSignOut}
            disabled={loading}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Sign out
          </button>
        ) : (
          <Link
            href="/login"
            className="block w-full rounded-md bg-ink px-3 py-2 text-center text-sm font-medium text-white hover:opacity-90"
          >
            Sign in
          </Link>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Mobile overlay */}
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close sidebar"
        />
      )}

      {/* Sidebar — fixed drawer on mobile, static on desktop */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform border-r border-slate-200 bg-white transition-transform md:static md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {sidebarContent}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile header */}
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100"
            aria-label="Open sidebar"
          >
            Menu
          </button>
          <Link href="/" className="flex items-center gap-2 font-bold text-ink">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-ink text-sm text-white">TS</span>
            TenderShield
          </Link>
          <div className="w-8" />
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
