"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type SupportTicket } from "@/lib/api";
import { useSession } from "@/components/session";

export default function SupportTicketsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [newTicket, setNewTicket] = useState({ title: "", body: "", category: "technical" });
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    try {
      const list = await api.listSupportTickets(session.token);
      setTickets(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
    }
  };

  useEffect(() => {
    if (!session) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) return;
    setError(null);
    try {
      await api.createSupportTicket(session.token, newTicket);
      setNewTicket({ title: "", body: "", category: "technical" });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create ticket");
    }
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Support tickets</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Create ticket</h2>
        <form onSubmit={create} className="space-y-4">
          <div>
            <label htmlFor="ticket-category" className="mb-1 block text-sm font-medium text-slate-700">Category</label>
            <select id="ticket-category" value={newTicket.category} onChange={(e) => setNewTicket({ ...newTicket, category: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
              {["billing", "technical", "feature"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="ticket-title" className="mb-1 block text-sm font-medium text-slate-700">Title</label>
            <input id="ticket-title" value={newTicket.title} onChange={(e) => setNewTicket({ ...newTicket, title: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" required />
          </div>
          <div>
            <label htmlFor="ticket-body" className="mb-1 block text-sm font-medium text-slate-700">Description</label>
            <textarea id="ticket-body" value={newTicket.body} onChange={(e) => setNewTicket({ ...newTicket, body: e.target.value })} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" rows={4} required />
          </div>
          <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Create</button>
        </form>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Your tickets</h2>
        {tickets.length === 0 ? (
          <p className="text-sm text-slate-500">No tickets yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {tickets.map((t) => (
              <li key={t.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{t.title}</p>
                  <p className="text-xs text-slate-500">{t.category} — {t.status}</p>
                </div>
                <Link href={`/support/tickets/${t.id}`} className="text-sm text-indigo-600 hover:underline">Open</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
