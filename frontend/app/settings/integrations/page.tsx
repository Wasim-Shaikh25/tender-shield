"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";
import { api, type DynamicConnectorConfig } from "@/lib/api";
import IntegrationSourcesPanel from "./integration-sources";

const DEFAULT_COST_LINE_MAPPING = JSON.stringify(
  {
    cost_lines: {
      items: "data.items",
      fields: {
        cost_code: "costCode",
        description: "description",
        committed_cost_minor: "committedCost",
        certified_value_minor: "certifiedValue",
        currency: "currency",
      },
    },
  },
  null,
  2
);

type FormState = {
  name: string;
  base_url: string;
  auth_type: "none" | "bearer" | "basic" | "api_key";
  auth_config: string;
  headers: string;
  pagination: string;
  mappings: string;
  enabled: boolean;
};

const emptyForm: FormState = {
  name: "",
  base_url: "",
  auth_type: "none",
  auth_config: "{}",
  headers: "{}",
  pagination: "{}",
  mappings: DEFAULT_COST_LINE_MAPPING,
  enabled: true,
};

export default function IntegrationsSettingsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [connectors, setConnectors] = useState<DynamicConnectorConfig[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ status: string; http_status: number | null; latency_ms: number; preview: string } | null>(null);

  const isAdmin = session && ["admin", "owner", "superadmin"].includes(session.role);

  useEffect(() => {
    if (!session) {
      if (typeof window !== "undefined") router.replace("/login");
      return;
    }
    api.listDynamicConnectors(session.token)
      .then((r) => setConnectors(r.connectors))
      .catch(() => setConnectors([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const parseJson = (value: string) => {
    const trimmed = value.trim();
    return trimmed ? JSON.parse(trimmed) : {};
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !isAdmin) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const body = {
        name: form.name,
        base_url: form.base_url,
        auth_type: form.auth_type,
        auth_config: parseJson(form.auth_config),
        headers: parseJson(form.headers),
        pagination: parseJson(form.pagination),
        mappings: parseJson(form.mappings),
        enabled: form.enabled,
      };
      if (editing) {
        await api.updateDynamicConnector(session.token, editing, body);
      } else {
        await api.createDynamicConnector(session.token, body);
      }
      setForm(emptyForm);
      setEditing(null);
      setMessage("Connector saved.");
      api.listDynamicConnectors(session.token)
        .then((r) => setConnectors(r.connectors))
        .catch(() => setConnectors([]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save connector");
    } finally {
      setLoading(false);
    }
  };

  const test = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const r = await api.testDynamicConnector(session.token, id);
      setTestResult(r);
      setMessage(`Test ${r.status} (${r.http_status ?? "-"}) in ${r.latency_ms}ms`);
      api.listDynamicConnectors(session.token)
        .then((resp) => setConnectors(resp.connectors))
        .catch(() => setConnectors([]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setLoading(false);
    }
  };

  const poll = async (id: string) => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.pollDynamicConnector(session.token, id);
      setMessage("Poll completed. Check sync jobs for details.");
      console.log(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Poll failed");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id: string) => {
    if (!session || !confirm("Delete this connector?")) return;
    setLoading(true);
    try {
      await api.deleteDynamicConnector(session.token, id);
      api.listDynamicConnectors(session.token)
        .then((r) => setConnectors(r.connectors))
        .catch(() => setConnectors([]));
      setMessage("Connector deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  };

  const edit = (c: DynamicConnectorConfig) => {
    setEditing(c.id!);
    setForm({
      name: c.name,
      base_url: c.base_url,
      auth_type: c.auth_type,
      auth_config: JSON.stringify(c.auth_config || {}, null, 2),
      headers: JSON.stringify(c.headers || {}, null, 2),
      pagination: JSON.stringify(c.pagination || {}, null, 2),
      mappings: JSON.stringify(c.mappings || {}, null, 2),
      enabled: c.enabled ?? true,
    });
    setTestResult(null);
  };

  const cancelEdit = () => {
    setEditing(null);
    setForm(emptyForm);
  };

  const field = (
    label: string,
    value: string,
    onChange: (v: string) => void,
    type: "text" | "password" | "textarea" = "text",
    placeholder = ""
  ) => (
    <div className="space-y-1">
      <label className="text-sm font-medium text-slate-700">{label}</label>
      {type === "textarea" ? (
        <textarea
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
          rows={4}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
        />
      ) : (
        <input
          type={type}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={loading}
        />
      )}
    </div>
  );

  if (!session) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Integrations</h1>

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</div>}

      {isAdmin && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-ink">
            {editing ? "Edit dynamic connector" : "New dynamic connector"}
          </h2>
          <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2">
            {field("Name", form.name, (v) => setForm({ ...form, name: v }))}
            {field("Base URL", form.base_url, (v) => setForm({ ...form, base_url: v }))}
            <div className="space-y-1">
              <label htmlFor="auth-type" className="text-sm font-medium text-slate-700">Auth type</label>
              <select
                id="auth-type"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={form.auth_type}
                onChange={(e) => setForm({ ...form, auth_type: e.target.value as FormState["auth_type"] })}
                disabled={loading}
              >
                <option value="none">None</option>
                <option value="bearer">Bearer token</option>
                <option value="basic">Basic (username / password)</option>
                <option value="api_key">API key header</option>
              </select>
            </div>
            {field(
              "Auth config (JSON)",
              form.auth_config,
              (v) => setForm({ ...form, auth_config: v }),
              "textarea",
              '{"token":""} or {"username":"","password":""} or {"header_name":"X-Api-Key","api_key":""}'
            )}
            {field(
              "Headers (JSON)",
              form.headers,
              (v) => setForm({ ...form, headers: v }),
              "textarea",
              '{"Accept":"application/json"}'
            )}
            {field(
              "Pagination (JSON)",
              form.pagination,
              (v) => setForm({ ...form, pagination: v }),
              "textarea",
              '{"type":"offset","offset_param":"offset","limit_param":"limit","limit":100}'
            )}
            {field(
              "Mappings (JSON)",
              form.mappings,
              (v) => setForm({ ...form, mappings: v }),
              "textarea",
              DEFAULT_COST_LINE_MAPPING
            )}
            <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Enabled
            </label>
            <div className="flex gap-3 md:col-span-2">
              <button
                type="submit"
                disabled={loading}
                className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {loading ? "Saving..." : editing ? "Update connector" : "Create connector"}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>
      )}

      {testResult && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-2 text-lg font-semibold text-ink">Test result</h2>
          <div className="space-y-1 text-sm text-slate-700">
            <p>Status: <span className={testResult.status === "ok" ? "text-green-700" : "text-red-700"}>{testResult.status}</span></p>
            <p>HTTP status: {testResult.http_status ?? "-"}</p>
            <p>Latency: {testResult.latency_ms}ms</p>
            <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-slate-50 p-3 text-xs">{testResult.preview}</pre>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Dynamic connectors</h2>
        {connectors.length === 0 ? (
          <p className="text-sm text-slate-500">No dynamic connectors configured yet.</p>
        ) : (
          <ul className="space-y-3">
            {connectors.map((c) => (
              <li key={c.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-medium text-ink">{c.name}</p>
                  <p className="text-sm text-slate-500">{c.base_url}</p>
                  <p className="text-xs text-slate-400">
                    {c.enabled ? "enabled" : "disabled"}
                    {c.last_test_status && ` · last test: ${c.last_test_status}`}
                  </p>
                </div>
                {isAdmin && (
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => test(c.id!)} disabled={loading} className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Test</button>
                    <button onClick={() => poll(c.id!)} disabled={loading} className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">Poll</button>
                    <button onClick={() => edit(c)} disabled={loading} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700">Edit</button>
                    <button onClick={() => remove(c.id!)} disabled={loading} className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-700">Delete</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {session && <IntegrationSourcesPanel token={session.token} isAdmin={!!isAdmin} />}
    </div>
  );
}
