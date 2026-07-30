"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type WorkspaceDetail } from "@/lib/api";
import { useSession } from "@/components/session";

export default function AdminWorkspaceDetailPage() {
  const { session } = useSession();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [ws, setWs] = useState<WorkspaceDetail | null>(null);
  const [plan, setPlan] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session || !id) return;
    api.adminGetWorkspace(session.token, id)
      .then((w) => { setWs(w); setPlan(w.plan || "free"); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load workspace"));
  }, [session, id]);

  if (!session) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }
  if (!session.is_superadmin) {
    return <p className="p-6 text-sm text-red-600">Superadmin access required.</p>;
  }

  const savePlan = async () => {
    if (!session || !ws) return;
    setError(null);
    setMessage(null);
    try {
      const updated = await api.adminSetWorkspacePlan(session.token, id, plan);
      setWs(updated);
      setMessage("Plan updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Plan update failed");
    }
  };

  if (!ws) return <p className="p-6 text-sm text-slate-500">Loading...</p>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">{ws.name}</h1>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {message && <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{message}</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div><p className="text-xs text-slate-500">Plan</p><p className="text-sm font-medium">{ws.plan || "free"}</p></div>
          <div><p className="text-xs text-slate-500">Country</p><p className="text-sm font-medium">{ws.country || "—"}</p></div>
          <div><p className="text-xs text-slate-500">Owner</p><p className="text-sm font-medium">{ws.owner_email}</p></div>
          <div><p className="text-xs text-slate-500">Members</p><p className="text-sm font-medium">{ws.member_count}</p></div>
        </div>

        <div className="mt-6 flex items-end gap-2">
          <div>
            <label htmlFor="plan-select" className="mb-1 block text-sm font-medium text-slate-700">Change plan</label>
            <select id="plan-select" value={plan} onChange={(e) => setPlan(e.target.value)} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
              {["free", "pro", "enterprise", "team", "paygo"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <button onClick={savePlan} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white">Save</button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-3 text-lg font-semibold text-ink">Members</h2>
        <ul className="divide-y divide-slate-100">
          {ws.members.map((m) => (
            <li key={m.user_id} className="flex items-center justify-between py-2">
              <span className="text-sm font-medium text-slate-900">{m.user_id}</span>
              <span className="text-xs text-slate-500">{m.role}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
