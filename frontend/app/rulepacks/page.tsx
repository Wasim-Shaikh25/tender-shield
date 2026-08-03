"use client";

import { use, useCallback, useEffect, useState } from "react";
import { api, type RulePackSummary } from "@/lib/api";
import { useSession } from "@/components/session";

export default function RulepacksPage() {
  const { session } = useSession();
  const [packs, setPacks] = useState<RulePackSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [scope, setScope] = useState<"workspace" | "global">("workspace");

  const load = useCallback(async () => {
    if (!session) return;
    try {
      const res = await api.listRulepacks(session.token);
      setPacks(res.packs);
    } catch {
      setNote("Failed to load rulepacks.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !session) return;
    setBusy(true);
    setNote(null);
    try {
      const uploaded = await api.uploadRulepack(session.token, file, scope);
      setNote(`Uploaded ${uploaded.pack_id}@${uploaded.version} as ${uploaded.scope}.`);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function activate(id: string) {
    if (!session) return;
    setBusy(true);
    try {
      await api.activateRulepack(session.token, id);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!session || !confirm("Delete this rulepack?")) return;
    setBusy(true);
    try {
      await api.deleteRulepack(session.token, id);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session) return <p className="text-sm text-slate-500">Sign in to manage rulepacks.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">Rulepacks</h1>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-3 font-semibold text-ink">Upload a rulepack</h3>
        <p className="mb-4 text-sm text-slate-500">
          Upload a .zip containing a valid TenderShield rulepack (pack.yaml, risk_patterns/, notice_standards/, boq/, etc.). Source PDF/Word/image files can be included.
        </p>
        <div className="flex items-center gap-3">
          {session.is_superadmin && (
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as "workspace" | "global")}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
            >
              <option value="workspace">Workspace-private</option>
              <option value="global">Global</option>
            </select>
          )}
          <label className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
            <input type="file" accept=".zip" className="hidden" onChange={upload} disabled={busy} />
            {busy ? "Uploading…" : "Choose .zip"}
          </label>
        </div>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-4 font-semibold text-ink">Available rulepacks</h3>
        {packs.length === 0 ? (
          <p className="text-sm text-slate-500">No rulepacks uploaded yet. Disk packs are still available under the hood.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="pb-2">Pack ID</th>
                <th className="pb-2">Version</th>
                <th className="pb-2">Scope</th>
                <th className="pb-2">Jurisdiction</th>
                <th className="pb-2">Status</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {packs.map((p) => (
                <tr key={p.id} className="border-b border-slate-100">
                  <td className="py-3 font-medium">{p.pack_id}</td>
                  <td className="py-3">{p.version}</td>
                  <td className="py-3 capitalize">{p.scope}</td>
                  <td className="py-3">{p.jurisdiction}</td>
                  <td className="py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        p.is_active
                          ? "bg-emerald-100 text-emerald-700"
                          : p.status === "draft"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {p.is_active ? "active" : p.status}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex gap-2">
                      {!p.is_active && (
                        <button
                          onClick={() => activate(p.id)}
                          disabled={busy}
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-ink hover:text-ink disabled:opacity-50"
                        >
                          Activate
                        </button>
                      )}
                      <button
                        onClick={() => remove(p.id)}
                        disabled={busy}
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs text-red-600 hover:border-red-600 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
