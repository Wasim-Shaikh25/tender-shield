"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type RulePackSummary, type RulePackFile, type RagSuggestion } from "@/lib/api";
import { useSession } from "@/components/session";
import { KeyValueSummary } from "@/components/json-summary";

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
          Upload a .zip containing a valid TenderShield rulepack (pack.yaml, risk_patterns/, notice_standards/, boq/, etc.). Source PDF/Word/image files can be included for later RAG-assisted suggestions.
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

      <RagPanel packs={packs} onChange={() => load()} />
    </div>
  );
}

function RagPanel({ packs, onChange }: { packs: RulePackSummary[]; onChange: () => void }) {
  const { session } = useSession();
  const [selectedPack, setSelectedPack] = useState<string>("");
  const [files, setFiles] = useState<RulePackFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [suggestions, setSuggestions] = useState<RagSuggestion[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const loadFiles = useCallback(async (packId: string) => {
    if (!session || !packId) return;
    try {
      const res = await api.listRulepackFiles(session.token, packId);
      setFiles(res.files);
      setSelectedFile(res.files[0]?.id ?? "");
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to load files");
    }
  }, [session]);

  const loadSuggestions = useCallback(async (packId: string) => {
    if (!session || !packId) return;
    try {
      const res = await api.listRagSuggestions(session.token, packId);
      setSuggestions(res.suggestions);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to load suggestions");
    }
  }, [session]);

  useEffect(() => {
    setFiles([]);
    setSelectedFile("");
    setSuggestions([]);
    if (selectedPack) {
      loadFiles(selectedPack);
      loadSuggestions(selectedPack);
    }
  }, [selectedPack, loadFiles, loadSuggestions]);

  async function generate() {
    if (!session || !selectedPack || !selectedFile) return;
    setBusy(true);
    setNote(null);
    try {
      const res = await api.generateRagSuggestions(session.token, selectedPack, selectedFile);
      setSuggestions(res.suggestions);
      setNote(`Generated ${res.suggestions.length} suggestion(s).`);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Suggestion failed");
    } finally {
      setBusy(false);
    }
  }

  async function approve(id: string) {
    if (!session) return;
    setBusy(true);
    try {
      const res = await api.approveRagSuggestion(session.token, id);
      setNote(`Approved. New draft created: ${res.new_rulepack.version}`);
      onChange();
      if (selectedPack) loadSuggestions(selectedPack);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }

  async function reject(id: string) {
    if (!session) return;
    setBusy(true);
    try {
      await api.rejectRagSuggestion(session.token, id);
      if (selectedPack) loadSuggestions(selectedPack);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Reject failed");
    } finally {
      setBusy(false);
    }
  }

  if (!session) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h3 className="mb-4 font-semibold text-ink">RAG-assisted rulepack expansion</h3>
      <p className="mb-4 text-sm text-slate-500">
        Select a rulepack and a source file (PDF/Word/text from the uploaded archive). The AI will propose new patterns/standards based on the source document. Every suggestion must be approved before it becomes a draft rulepack version.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={selectedPack}
          onChange={(e) => setSelectedPack(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        >
          <option value="">Select a rulepack</option>
          {packs.map((p) => (
            <option key={p.id} value={p.id}>
              {p.pack_id}@{p.version} ({p.scope})
            </option>
          ))}
        </select>

        {files.length > 0 && (
          <select
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
          >
            {files.map((f) => (
              <option key={f.id} value={f.id}>
                {f.path}
              </option>
            ))}
          </select>
        )}

        <button
          onClick={generate}
          disabled={busy || !selectedPack || !selectedFile}
          className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Generating…" : "Generate suggestions"}
        </button>
      </div>

      {note && <p className="mb-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      {suggestions.length > 0 && (
        <div className="space-y-3">
          {suggestions.map((s) => (
            <div key={s.id} className="rounded-md border border-slate-200 p-4 text-sm">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-semibold capitalize text-ink">{s.kind}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    s.status === "proposed"
                      ? "bg-amber-100 text-amber-800"
                      : s.status === "approved"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {s.status}
                </span>
              </div>
              <p className="mb-2 text-slate-600">{s.rationale}</p>
              {s.source_quote && (
                <p className="mb-2 text-xs text-slate-500">
                  <span className="font-medium">Quote:</span> {s.source_quote}
                  {s.source_page ? ` (p. ${s.source_page})` : ""}
                </p>
              )}
              <div className="mb-3">
                <KeyValueSummary
                  data={s.proposed_yaml}
                  title="Proposed YAML"
                  maxPreviewKeys={6}
                  rawLabel="Full YAML"
                />
              </div>
              {s.status === "proposed" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => approve(s.id)}
                    disabled={busy}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-ink hover:text-ink disabled:opacity-50"
                  >
                    Approve (create draft)
                  </button>
                  <button
                    onClick={() => reject(s.id)}
                    disabled={busy}
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs text-red-600 hover:border-red-600 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
