"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type RulePackSummary } from "@/lib/api";

export function RulepackSelector({
  token,
  opportunityId,
}: {
  token: string;
  opportunityId: string;
}) {
  const [all, setAll] = useState<RulePackSummary[]>([]);
  const [applied, setApplied] = useState<RulePackSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    const [allRes, appliedRes] = await Promise.all([
      api.listRulepacks(token),
      api.getOpportunityRulepacks(token, opportunityId),
    ]);
    setAll(allRes.packs);
    setApplied(appliedRes.packs);
    setSelected(new Set(appliedRes.packs.map((p) => p.id)));
  }, [token, opportunityId]);

  useEffect(() => {
    load();
  }, [load]);

  async function apply() {
    setBusy(true);
    try {
      const res = await api.applyOpportunityRulepacks(token, opportunityId, Array.from(selected));
      setApplied(res.packs);
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((s) => !s)}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:border-ink hover:text-ink"
      >
        Rulepacks {applied.length > 0 && `(${applied.length})`}
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
          <h4 className="mb-2 text-sm font-semibold text-ink">Apply rulepacks</h4>
          {all.length === 0 ? (
            <p className="text-xs text-slate-500">No uploaded rulepacks. Go to Rulepacks to upload.</p>
          ) : (
            <div className="mb-3 max-h-60 space-y-2 overflow-auto">
              {all.map((p) => (
                <div
                  key={p.id}
                  className="flex items-start gap-2 rounded-md border border-slate-100 p-2 text-sm hover:bg-slate-50"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => toggle(p.id)}
                    aria-label={`${p.pack_id} ${p.version}`}
                    className="mt-0.5"
                  />
                  <div>
                    <div className="font-medium">{p.pack_id}</div>
                    <div className="text-xs text-slate-500">{p.version} · {p.scope}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setOpen(false)}
              className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:border-ink"
            >
              Cancel
            </button>
            <button
              onClick={apply}
              disabled={busy || all.length === 0}
              className="rounded-md bg-ink px-2 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Apply"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
