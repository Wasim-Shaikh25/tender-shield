"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/session";
import { api } from "@/lib/api";

const SCOPES = ["read", "write", "signature"];

export default function ApiKeysSettingsPage() {
  const { session } = useSession();
  const router = useRouter();
  const [keys, setKeys] = useState<{ id: string; name: string; scopes: string[] }[]>([]);
  const [name, setName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["read"]);
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const isAdmin = session && ["admin", "owner", "superadmin"].includes(session.role);

  const load = () => {
    if (!session) return;
    api.listPublicApiKeys(session.token)
      .then((r) => setKeys(r.keys))
      .catch(() => setKeys([]));
  };

  useEffect(() => {
    if (!session) {
      if (typeof window !== "undefined") router.replace("/login");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session || !isAdmin) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    setPlaintext(null);
    try {
      const r = await api.createPublicApiKey(session.token, { name, scopes: selectedScopes });
      setKeys([...keys, { id: r.id, name: r.name, scopes: r.scopes }]);
      setPlaintext(r.plaintext_key);
      setName("");
      setSelectedScopes(["read"]);
      setMessage("API key created. Copy it now — it will not be shown again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setLoading(false);
    }
  };

  const revoke = async (id: string) => {
    if (!session || !isAdmin || !confirm("Revoke this API key?")) return;
    try {
      await api.revokePublicApiKey(session.token, id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    }
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  if (!session) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink">Public API keys</h1>

      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</div>}

      {isAdmin && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-ink">Create key</h2>
          <form onSubmit={create} className="grid gap-4">
            <input
              type="text"
              placeholder="Key name"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
            />
            <div className="flex gap-4 text-sm text-slate-700">
              {SCOPES.map((s) => (
                <label key={s} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedScopes.includes(s)}
                    onChange={() => toggleScope(s)}
                    disabled={loading}
                  />
                  {s}
                </label>
              ))}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-fit rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Create key
            </button>
          </form>

          {plaintext && (
            <div className="mt-4 rounded-md bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-800">Copy this key now:</p>
              <code className="block break-all text-sm text-amber-900">{plaintext}</code>
            </div>
          )}
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink">Active keys</h2>
        {keys.length === 0 ? (
          <p className="text-sm text-slate-500">No API keys yet.</p>
        ) : (
          <ul className="space-y-3">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3">
                <div>
                  <p className="font-medium text-ink">{k.name}</p>
                  <p className="text-xs text-slate-500">{k.scopes.join(", ")}</p>
                </div>
                {isAdmin && (
                  <button
                    onClick={() => revoke(k.id)}
                    className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-700"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
