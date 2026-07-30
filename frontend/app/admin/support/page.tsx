"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SupportTicket } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminSupportPage() {
  const { session } = useSession();
  const router = useRouter();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    try {
      const list = await api.adminListSupportTickets(
        session.token,
        workspaceId || "00000000-0000-0000-0000-000000000000",
        category || undefined,
        status || undefined
      );
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
  if (!session.is_superadmin) {
    return <p className="p-6 text-sm text-red-600">Superadmin access required.</p>;
  }

  const setTicketStatus = async (id: string, newStatus: string) => {
    if (!session) return;
    await api.adminSetSupportTicketStatus(session.token, workspaceId || "00000000-0000-0000-0000-000000000000", id, newStatus);
    load();
  };

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Support tickets</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex flex-wrap gap-2">
        <input value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)} placeholder="Workspace ID" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
          <option value="">All categories</option>
          {["billing", "technical", "feature", "other"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {["open", "in_progress", "resolved", "closed"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Filter</button>
      </form>

      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 text-left text-slate-500">
          <tr>
            <th className="py-2">Title</th>
            <th className="py-2">Category</th>
            <th className="py-2">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tickets.map((t) => (
            <tr key={t.id}>
              <td className="py-2">{t.title}</td>
              <td className="py-2">{t.category}</td>
              <td className="py-2">{t.status}</td>
              <td className="py-2">
                <select value={t.status} onChange={(e) => setTicketStatus(t.id, e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">
                  {["open", "in_progress", "resolved", "closed"].map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
