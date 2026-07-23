"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Opportunity } from "@/lib/api";
import { useSession } from "@/components/session";
import { CountdownBadge } from "@/components/badges";

export default function BoardPage() {
  const { session } = useSession();
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!session) return;
    const { opportunities } = await api.listOpportunities(session.token);
    setOpps(opportunities);
    setLoading(false);
  }

  useEffect(() => {
    if (session) refresh();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !title.trim()) return;
    await api.createOpportunity(session.token, title.trim());
    setTitle("");
    refresh();
  }

  if (!session) {
    return (
      <EmptyState
        title="Sign in to see your board"
        body="The opportunity board is your countdown wall — every live tender, days to submission, review status."
        cta={{ href: "/login", label: "Sign in" }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Opportunities</h1>
          <p className="text-sm text-slate-500">Red &lt; 3 days to submission · amber &lt; 7.</p>
        </div>
        <form onSubmit={create} className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="New tender title…"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-ink"
          />
          <button className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            Create
          </button>
        </form>
      </div>

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : opps.length === 0 ? (
        <EmptyState
          title="No opportunities yet"
          body="Create one above, then upload the GCC too — 60% of traps live in the conditions, not the NIT."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {opps.map((o) => (
            <Link
              key={o.id}
              href={`/opportunities/${o.id}`}
              className="rounded-xl border border-slate-200 bg-white p-5 transition hover:border-ink hover:shadow-sm"
            >
              <div className="mb-3 flex items-center justify-between">
                <CountdownBadge due={o.submission_due} />
                <span className="text-xs uppercase tracking-wide text-slate-400">{o.status}</span>
              </div>
              <h3 className="font-semibold text-ink">{o.title}</h3>
              <p className="mt-2 text-sm text-slate-500">Open workbench →</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({
  title,
  body,
  cta,
}: {
  title: string;
  body: string;
  cta?: { href: string; label: string };
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{body}</p>
      {cta && (
        <Link href={cta.href} className="mt-4 inline-block rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">
          {cta.label}
        </Link>
      )}
    </div>
  );
}
