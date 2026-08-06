"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "./session";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";

const PUBLIC_PATHS = ["/login", "/forgot-password", "/reset-password"];

type NavItem = { label: string; href: string; icon?: string };

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

export function AppShellRedesigned({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.some((p) => pathname?.startsWith(p));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
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
        className={cn(
          "block px-3 py-2.5 text-sm font-medium rounded-md transition-colors duration-base",
          active
            ? "bg-ink text-white"
            : "text-text-secondary hover:bg-bg-secondary active:bg-bg-tertiary"
        )}
      >
        {label}
      </Link>
    );
  };

  const sidebarContent = (
    <div className="flex h-full flex-col bg-white border-r border-border-default">
      {/* Logo Section */}
      <div className="p-4 border-b border-border-default">
        <Link
          href="/"
          className="flex items-center gap-3 font-bold text-text-primary hover:opacity-80 transition-opacity"
          onClick={() => setMobileOpen(false)}
        >
          <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-ink text-white text-sm font-semibold">
            TS
          </div>
          <span className="truncate text-base">TenderShield</span>
        </Link>
      </div>

      {/* Workspace Selector */}
      {session && workspaces.length > 0 && (
        <div className="p-3 border-b border-border-default">
          <div className="relative">
            <button
              onClick={() => setWorkspaceOpen(!workspaceOpen)}
              className={cn(
                "w-full px-3 py-2 text-sm font-medium text-left rounded-md transition-colors duration-base",
                "border border-border-default",
                "text-text-primary bg-white hover:bg-bg-secondary",
                "focus:ring-1 focus:ring-ink focus:border-ink"
              )}
            >
              <div className="truncate">{activeWorkspace?.name ?? "Select workspace"}</div>
              <div className="text-xs text-text-muted mt-0.5">{activeWorkspace?.plan ?? "Free"}</div>
            </button>

            {workspaceOpen && workspaces.length > 1 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-border-default rounded-md shadow-lg z-50">
                {workspaces.map((w) => (
                  <button
                    key={w.workspace_id}
                    onClick={() => {
                      switchWorkspace(w.workspace_id);
                      setWorkspaceOpen(false);
                    }}
                    className={cn(
                      "w-full px-3 py-2 text-sm text-left hover:bg-bg-secondary transition-colors",
                      activeWorkspace?.workspace_id === w.workspace_id && "bg-bg-secondary font-medium"
                    )}
                  >
                    <div className="font-medium text-text-primary">{w.name}</div>
                    <div className="text-xs text-text-muted">{w.plan}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
          Main
        </p>
        {MAIN_NAV.map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            onClick={() => setMobileOpen(false)}
          />
        ))}
      </nav>

      {/* Account Section */}
      <div className="border-t border-border-default p-3 space-y-1">
        <p className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted">
          Account
        </p>
        {ACCOUNT_NAV.map((item) => (
          <NavLink
            key={item.href}
            href={item.href}
            label={item.label}
            onClick={() => setMobileOpen(false)}
          />
        ))}
        {session?.is_superadmin && (
          <NavLink href="/admin" label="Admin" onClick={() => setMobileOpen(false)} />
        )}
      </div>

      {/* Sign Out */}
      <div className="border-t border-border-default p-3">
        {session ? (
          <Button
            onClick={handleSignOut}
            disabled={loading}
            variant="secondary"
            size="md"
            className="w-full"
          >
            Sign out
          </Button>
        ) : (
          <Link
            href="/login"
            className="block w-full"
          >
            <Button variant="primary" size="md" className="w-full">
              Sign in
            </Button>
          </Link>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-bg-primary">
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
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform md:static md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "transition-transform duration-base md:transition-none"
        )}
      >
        {sidebarContent}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile header */}
        <header className="flex items-center justify-between border-b border-border-default bg-white px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="p-2 text-text-secondary hover:bg-bg-secondary rounded-md transition-colors"
            aria-label="Open sidebar"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <Link href="/" className="flex items-center gap-2 font-bold text-text-primary">
            <div className="flex items-center justify-center h-7 w-7 rounded-md bg-ink text-white text-xs font-semibold">
              TS
            </div>
            <span className="hidden sm:inline">TenderShield</span>
          </Link>
          <div className="w-8" />
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <div className="px-4 py-6 md:px-6 md:py-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
