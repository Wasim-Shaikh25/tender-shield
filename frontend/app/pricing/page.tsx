"use client";

// Public pricing page (R-008 §1) — no auth required. Prices here must match
// backend/app/modules/billing/plans.py's PRICES_MINOR exactly; that table is
// the only source of what a plan costs (server-side, R-005 §B.2) — this page
// only displays it, never computes a checkout total from these numbers.

import { useState } from "react";
import Link from "next/link";
import { formatMoney } from "@/lib/money";
import { useSession } from "@/components/session";
import { CheckoutDialog } from "@/components/checkout-dialog";
import type { Plan } from "@/lib/api";

const PLANS: Array<{
  id: Plan;
  name: string;
  priceMinor: number;
  cadence: string;
  line: string;
  features: string[];
  highlight?: boolean;
}> = [
  {
    id: "free",
    name: "Free",
    priceMinor: 0,
    cadence: "",
    line: "One complete tender review. Watermarked export.",
    features: ["1 full review", "All risk patterns", "Deadline wall", "2 seats", "Watermarked export"],
  },
  {
    id: "paygo",
    name: "Pay as you go",
    priceMinor: 750_000,
    cadence: "per tender",
    line: "For occasional bids.",
    features: ["Unlimited tenders, pay per review", "Clean export", "3 seats"],
  },
  {
    id: "pro",
    name: "Pro",
    priceMinor: 2_499_900,
    cadence: "per month",
    highlight: true,
    line: "For firms bidding regularly.",
    features: ["10 reviews / month", "Clean export", "10 seats", "Priority support"],
  },
  {
    id: "scale",
    name: "Scale",
    priceMinor: 7_499_900,
    cadence: "per month",
    line: "For multi-office contractors.",
    features: ["40 reviews / month", "25 seats", "Custom notice standards"],
  },
];

export default function PricingPage() {
  const { session } = useSession();
  const [checkoutFor, setCheckoutFor] = useState<Plan | null>(null);

  return (
    <div className="space-y-8">
      <div className="text-center">
        <h1 className="text-3xl font-bold text-ink">Plans</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-slate-500">
          The free review is a complete review — every risk pattern, every deadline, a full export. It's
          watermarked; paid plans remove the watermark and lift the review cap.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {PLANS.map((p) => (
          <div
            key={p.id}
            className={`flex flex-col rounded-xl border p-6 ${
              p.highlight ? "border-ink shadow-md" : "border-slate-200"
            }`}
          >
            {p.highlight && (
              <span className="mb-2 w-fit rounded-full bg-ink px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                Most popular
              </span>
            )}
            <h2 className="text-lg font-bold text-ink">{p.name}</h2>
            <p className="mt-1 text-2xl font-bold text-ink">
              {p.priceMinor === 0 ? "Free" : formatMoney(p.priceMinor)}
              {p.cadence && <span className="text-sm font-normal text-slate-500"> {p.cadence}</span>}
            </p>
            <p className="mt-2 text-sm text-slate-500">{p.line}</p>
            <ul className="mt-4 flex-1 space-y-1.5 text-sm text-slate-600">
              {p.features.map((f) => (
                <li key={f}>· {f}</li>
              ))}
            </ul>

            {!session && (
              <Link
                href="/login"
                className="mt-5 rounded-md bg-ink px-4 py-2 text-center text-sm font-medium text-white hover:opacity-90"
              >
                {p.id === "free" ? "Start free" : "Sign up"}
              </Link>
            )}
            {session && p.id !== "free" && (
              <button
                onClick={() => setCheckoutFor(p.id)}
                className="mt-5 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                Choose {p.name}
              </button>
            )}
            {session && p.id === "free" && (
              <span className="mt-5 rounded-md border border-slate-200 px-4 py-2 text-center text-sm text-slate-400">
                Default plan
              </span>
            )}
          </div>
        ))}
      </div>

      {checkoutFor && session && checkoutFor !== "free" && (
        <CheckoutDialog
          token={session.token}
          kind={checkoutFor === "paygo" ? "paygo" : "subscription"}
          plan={checkoutFor}
          onClose={() => setCheckoutFor(null)}
          onSuccess={() => setCheckoutFor(null)}
        />
      )}
    </div>
  );
}
