import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { SessionProvider } from "@/components/session";
import { AuthGate } from "@/components/auth-gate";
import { HeaderActions } from "@/components/header-actions";

export const metadata: Metadata = {
  title: "TenderShield AI",
  description: "Tender risk + BOQ assurance — surface traps before you bid.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>
          <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
              <Link href="/" className="flex items-center gap-2 font-bold text-ink">
                <span className="grid h-7 w-7 place-items-center rounded-md bg-ink text-sm text-white">
                  TS
                </span>
                TenderShield
              </Link>
              <nav className="flex items-center gap-5 text-sm text-slate-600">
                <Link href="/opportunities" className="hover:text-ink">Opportunities</Link>
                <Link href="/analytics" className="hover:text-ink">Analytics</Link>
                <Link href="/controltower" className="hover:text-ink">Control Tower</Link>
                <Link href="/plan" className="hover:text-ink">Plan</Link>
                <Link href="/assistant" className="hover:text-ink">AI Assistant</Link>
                <Link href="/rulepacks" className="hover:text-ink">Rulepacks</Link>
                <Link href="/standards" className="hover:text-ink">Standards</Link>
                <Link href="/help" className="hover:text-ink">Help</Link>
                <HeaderActions />
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-6 py-8">
            <AuthGate>{children}</AuthGate>
          </main>
        </SessionProvider>
      </body>
    </html>
  );
}
