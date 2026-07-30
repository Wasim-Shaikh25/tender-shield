"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type SupportTicket, type SupportTicketReply } from "@/lib/api";
import { useSession } from "@/components/session";

export default function SupportTicketDetailPage() {
  const { session } = useSession();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.getSupportTicket(session.token, id)
      .then(setTicket)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load ticket"));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !ticket) return;
    setError(null);
    try {
      await api.replySupportTicket(session.token, id, reply);
      const updated = await api.getSupportTicket(session.token, id);
      setTicket(updated);
      setReply("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reply failed");
    }
  };

  if (!ticket) return <p className="p-6 text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">{ticket.title}</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-xs text-slate-500">{ticket.category} — {ticket.status}</p>
        <p className="mt-2 text-sm text-slate-900 whitespace-pre-wrap">{ticket.body}</p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Replies</h2>
        {ticket.replies?.length ? (
          <ul className="space-y-4">
            {ticket.replies.map((r: SupportTicketReply) => (
              <li key={r.id} className="rounded-md bg-slate-50 p-3">
                <p className="text-xs text-slate-500">{r.created_at}</p>
                <p className="mt-1 text-sm text-slate-900 whitespace-pre-wrap">{r.body}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No replies yet.</p>
        )}

        {ticket.status !== "closed" && (
          <form onSubmit={submit} className="mt-4 space-y-2">
            <textarea value={reply} onChange={(e) => setReply(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" rows={3} required />
            <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Reply</button>
          </form>
        )}
      </section>
    </div>
  );
}
