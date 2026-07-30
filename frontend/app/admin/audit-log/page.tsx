"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type AuditLogEntry } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminAuditLogPage() {
  const { session } = useSession();
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!session) return;
    try {
      const r = await api.adminAuditLog(session.token, workspaceId || "00000000-0000-0000-0000-000000000000");
      setLogs(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load logs");
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

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">Audit log</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <form onSubmit={(e) => { e.preventDefault(); load(); }} className="flex gap-2">
        <input
          value={workspaceId}
          onChange={(e) => setWorkspaceId(e.target.value)}
          placeholder="Workspace ID (empty for global)"
          className="w-full max-w-md rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button type="submit" className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Search</button>
      </form>

      <table className="w-full text-sm">
        <thead className="border-b border-slate-200 text-left text-slate-500">
          <tr>
            <th className="py-2">Time</th>
            <th className="py-2">Actor</th>
            <th className="py-2">Action</th>
            <th className="py-2">Object</th>
            <th className="py-2">Detail</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {logs.map((l) => (
            <tr key={l.id}>
              <td className="py-2">{l.at ?? "—"}</td>
              <td className="py-2">{l.actor_user_id ?? "system"}</td>
              <td className="py-2">{l.action}</td>
              <td className="py-2">{l.object_type}:{l.object_id}</td>
              <td className="py-2"><pre className="text-xs">{JSON.stringify(l.detail).slice(0, 120)}</pre></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
