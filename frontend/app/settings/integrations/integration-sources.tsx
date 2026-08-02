"use client";

import { useEffect, useState } from "react";
import { api, type IntegrationSource } from "@/lib/api";

const emptySource = {
  adapter_kind: "json_payload",
  name: "",
  opportunity_id: "",
  config: "{}",
  rate_limit_calls_per_minute: "",
};

const ADAPTER_HELP: Record<string, string> = {
  json_payload: '{"text":"paste CSV/JSON payload here"}',
  sharepoint_onedrive: '{"documents":[{"filename":"x.pdf","content":"..."}],"events":[]}',
  erp: '{"rows":[{"costCode":"A","description":"Earthwork","committedCost":1000000,"currency":"INR"}]}',
  schedule: '{"format":"csv","content":"Activity,Start,Finish\\nA,2026-08-01,2026-08-10"}',
  procore: '{"project_id":"12345"}',
  autodesk: '{"hub_id":"","project_id":""}',
  aconex: '{"project_id":""}',
  sharepoint: '{"site_id":"","drive_id":""}',
};

export default function IntegrationSourcesPanel({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [sources, setSources] = useState<IntegrationSource[]>([]);
  const [adapters, setAdapters] = useState<{ kind: string; supported_mimetypes: string[] }[]>([]);
  const [connectors, setConnectors] = useState<{ kind: string; name: string; auth_required: boolean }[]>([]);
  const [form, setForm] = useState(emptySource);
  const [importPayload, setImportPayload] = useState("");
  const [importSourceId, setImportSourceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = () => {
    api.listSources(token).then((r) => setSources(r.sources)).catch(() => setSources([]));
  };

  useEffect(() => {
    api.listSources(token).then((r) => setSources(r.sources)).catch(() => setSources([]));
    api.listAdapters(token).then((r) => setAdapters(r.adapters)).catch(() => setAdapters([]));
    api.listConnectors(token).then((r) => setConnectors(r.connectors)).catch(() => setConnectors([]));
  }, [token]);

  const isConnector = (kind: string) => connectors.some((c) => c.kind === kind);
  const connectorFor = (kind: string) => connectors.find((c) => c.kind === kind);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const body = {
        adapter_kind: form.adapter_kind,
        name: form.name,
        config: JSON.parse(form.config || "{}") as Record<string, unknown>,
        ...(form.opportunity_id ? { opportunity_id: form.opportunity_id } : {}),
        ...(form.rate_limit_calls_per_minute ? { rate_limit_calls_per_minute: Number(form.rate_limit_calls_per_minute) } : {}),
      };
      await api.createSource(token, body);
      setForm(emptySource);
      setMessage("Source created.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create source");
    } finally {
      setLoading(false);
    }
  };

  const startOAuth = async (source: IntegrationSource) => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const redirectUri = `${window.location.origin}/settings/integrations`;
      const r = await api.startOAuth(token, source.id, redirectUri);
      if (r.authorization_url) {
        window.location.href = r.authorization_url;
      } else {
        setMessage("Connector is not configured for OAuth.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "OAuth start failed");
    } finally {
      setLoading(false);
    }
  };

  const poll = async (source: IntegrationSource) => {
    if (!isAdmin) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.pollSource(token, source.id);
      setMessage("Poll completed.");
      console.log(r);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Poll failed");
    } finally {
      setLoading(false);
    }
  };

  const runImport = async () => {
    if (!isAdmin || !importSourceId) return;
    setLoading(true);
    setError(null);
    try {
      const payload = JSON.parse(importPayload || "{}");
      const r = await api.importSource(token, importSourceId, payload);
      setMessage("Import completed.");
      console.log(r);
      setImportPayload("");
      setImportSourceId(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  };

  const allKinds = [
    ...adapters.map((a) => ({ kind: a.kind, label: a.kind, isConnector: false })),
    ...connectors.map((c) => ({ kind: c.kind, label: c.name, isConnector: true })),
  ];

  const selectedHelp = ADAPTER_HELP[form.adapter_kind] ?? "{}";

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="mb-4 text-lg font-semibold text-ink">Integration sources</h2>

      {error && <div className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {message && <div className="mb-3 rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</div>}

      {isAdmin && (
        <form onSubmit={create} className="mb-6 grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor="source-kind" className="text-sm font-medium text-slate-700">Kind</label>
            <select
              id="source-kind"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={form.adapter_kind}
              onChange={(e) => {
                const kind = e.target.value;
                setForm({ ...form, adapter_kind: kind, config: ADAPTER_HELP[kind] ?? "{}" });
              }}
              disabled={loading}
            >
              {allKinds.map((k) => (
                <option key={k.kind} value={k.kind}>{k.label}</option>
              ))}
            </select>
          </div>
          <input
            type="text"
            placeholder="Source name"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            disabled={loading}
          />
          <input
            type="text"
            placeholder="Opportunity ID (optional)"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={form.opportunity_id}
            onChange={(e) => setForm({ ...form, opportunity_id: e.target.value })}
            disabled={loading}
          />
          <input
            type="number"
            placeholder="Rate limit calls/min (optional)"
            className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            value={form.rate_limit_calls_per_minute}
            onChange={(e) => setForm({ ...form, rate_limit_calls_per_minute: e.target.value })}
            disabled={loading}
          />
          <textarea
            className="md:col-span-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
            rows={4}
            placeholder={selectedHelp}
            value={form.config}
            onChange={(e) => setForm({ ...form, config: e.target.value })}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="md:col-span-2 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50 w-fit"
          >
            Create source
          </button>
        </form>
      )}

      {importSourceId && isAdmin && (
        <div className="mb-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Import payload for {sources.find((s) => s.id === importSourceId)?.name}</h3>
          <textarea
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
            rows={6}
            value={importPayload}
            onChange={(e) => setImportPayload(e.target.value)}
            disabled={loading}
          />
          <div className="mt-2 flex gap-2">
            <button onClick={runImport} disabled={loading} className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Run import</button>
            <button onClick={() => setImportSourceId(null)} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700">Cancel</button>
          </div>
        </div>
      )}

      {sources.length === 0 ? (
        <p className="text-sm text-slate-500">No integration sources yet.</p>
      ) : (
        <ul className="space-y-3">
          {sources.map((s) => {
            const conn = connectorFor(s.adapter_kind);
            return (
              <li key={s.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-medium text-ink">{s.name}</p>
                  <p className="text-sm text-slate-500">{s.adapter_kind} · {s.status}</p>
                  {s.last_synced_at && <p className="text-xs text-slate-400">Last synced: {new Date(s.last_synced_at).toLocaleString()}</p>}
                </div>
                {isAdmin && (
                  <div className="flex flex-wrap gap-2">
                    {conn?.auth_required && s.status !== "authorized" && (
                      <button onClick={() => startOAuth(s)} disabled={loading} className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Connect</button>
                    )}
                    {conn && (
                      <button onClick={() => poll(s)} disabled={loading} className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Poll</button>
                    )}
                    {!conn && (
                      <button onClick={() => setImportSourceId(s.id)} disabled={loading} className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Import</button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
