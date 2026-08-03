import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/session";
import { AuthGate } from "@/components/auth-gate";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "TenderShield AI",
  description: "Tender risk + BOQ assurance — surface traps before you bid.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>
          <AuthGate>
            <AppShell>{children}</AppShell>
          </AuthGate>
        </SessionProvider>
      </body>
    </html>
  );
}
