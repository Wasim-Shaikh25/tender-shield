"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type OrgStandard, type OrgStandardCategory } from "@/lib/api";
import { useSession } from "@/components/session";

const BLANK: OrgStandardCategory = {
  key: "",
  label: "",
  typical_days: null,
  expected: true,
  keywords: [],
  note: "",
};

export default function StandardsPage() {
  const { session } = useSession();
  const [mode, setMode] = useState<"prevail" | "side_by_side">("prevail");
  const [rows, setRows] = useState<OrgStandardCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    const s = await api.getOrgStandard(session.token).catch(() => null);
    if (s) {
      setMode(s.mode);
      setRows(s.categories);
    }
    setLoading(false);
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  if (!session) return <p className="text-sm text-slate-500">Sign in to manage your standards.</p>;

  function update(i: number, patch: Partial<OrgStandardCategory>) {
    setRows((r) => r.map((row, ix) => (ix === i ? { ...row, ...patch } : row)));
  }

  async function save() {
    setNote(null);
    const clean = rows
      .filter((r) => r.key.trim() && r.label.trim())
      .map((r) => ({ ...r, key: r.key.trim() }));
    const body: OrgStandard = { mode, categories: clean };
    try {
      await api.setOrgStandard(session!.token, body);
      setRows(clean);
      setNote("Saved — your standard now layers over the universal + regional defaults.");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Save failed");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Your notice standards</h1>
        <p className="mt-1 text-sm text-slate-600">
          TenderShield ships a universal baseline of notice regimes, refined by a regional
          (e.g. India) overlay. Add your firm&apos;s own regimes here — they either{" "}
          <b>prevail</b> over ours or sit <b>side by side</b> so you can compare. These feed the
          notice-rule register and its gap detection on every opportunity.
        </p>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="mb-2 text-sm font-semibold text-ink">How your standard combines with ours</h3>
        <div className="flex flex-wrap gap-2">
          {(["prevail", "side_by_side"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                mode === m
                  ? "border-ink bg-ink text-white"
                  : "border-slate-300 text-slate-600 hover:border-ink"
              }`}
            >
              {m === "prevail" ? "Prevail (yours wins)" : "Side by side (show both)"}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          {mode === "prevail"
            ? "Where a regime shares a key with ours, your values replace ours."
            : "Your regimes are shown alongside ours; nothing is overwritten."}
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row, i) => (
            <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="text-sm">
                  <span className="text-slate-500">Key (short id)</span>
                  <input
                    value={row.key}
                    onChange={(e) => update(i, { key: e.target.value })}
                    placeholder="handover"
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-ink"
                  />
                </label>
                <label className="text-sm">
                  <span className="text-slate-500">Label</span>
                  <input
                    value={row.label}
                    onChange={(e) => update(i, { label: e.target.value })}
                    placeholder="Site handover / possession notice"
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-ink"
                  />
                </label>
                <label className="text-sm">
                  <span className="text-slate-500">Typical days</span>
                  <input
                    type="number"
                    value={row.typical_days ?? ""}
                    onChange={(e) =>
                      update(i, { typical_days: e.target.value ? Number(e.target.value) : null })
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-ink"
                  />
                </label>
                <label className="text-sm">
                  <span className="text-slate-500">Match keywords (comma-separated)</span>
                  <input
                    value={row.keywords.join(", ")}
                    onChange={(e) =>
                      update(i, {
                        keywords: e.target.value
                          .split(",")
                          .map((k) => k.trim())
                          .filter(Boolean),
                      })
                    }
                    placeholder="handover, possession"
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-ink"
                  />
                </label>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={row.expected}
                    onChange={(e) => update(i, { expected: e.target.checked })}
                  />
                  Expected — flag as a gap when a contract omits it
                </label>
                <button
                  onClick={() => setRows((r) => r.filter((_, ix) => ix !== i))}
                  className="text-xs font-medium text-slate-400 hover:text-red-600"
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
          <div className="flex gap-2">
            <button
              onClick={() => setRows((r) => [...r, { ...BLANK }])}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white"
            >
              + Add a regime
            </button>
            <button
              onClick={save}
              className="rounded-md bg-ink px-4 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Save standard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
