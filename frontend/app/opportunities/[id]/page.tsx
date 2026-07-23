"use client";

import { use, useEffect, useState } from "react";
import { api, type Finding, type MissingDocs } from "@/lib/api";
import { useSession } from "@/components/session";
import { SeverityBadge, SourceBadge } from "@/components/badges";

const SAMPLE = `[p1]
NOTICE INVITING TENDER (NIT No. TS/DEMO/2026/001)
Construction of an office building with one basement, deep excavation adjacent to an existing structure, on a site with high sub-soil water. Completion: 30 months.
[p2]
Clause 14 — Price basis. The contract shall be on a firm price basis and no escalation whatsoever shall be payable.
[p4]
Clause 33 — Compensation for delay. Liquidated damages at the rate of 1% of the contract value shall be levied for each week of delay.
[p6]
Clause 52 — Termination. The Employer may terminate the contract for its convenience at any time, and the contractor shall have no claim for compensation.`;

export default function OpportunityDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useSession();
  const [tab, setTab] = useState<"overview" | "risks">("overview");
  const [title, setTitle] = useState("Opportunity");
  const [missing, setMissing] = useState<MissingDocs | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    api.getOpportunity(session.token, id).then((o) => setTitle(o.title)).catch(() => {});
    api.missingDocs(session.token, id).then(setMissing).catch(() => {});
  }, [session, id]);

  if (!session) return <p className="text-sm text-slate-500">Sign in to view this opportunity.</p>;

  async function loadConditions() {
    setBusy(true);
    setNote(null);
    try {
      await api.registerDocument(session!.token, id, "conditions.md", SAMPLE);
      setMissing(await api.missingDocs(session!.token, id));
      setNote("Conditions uploaded and segmented into clauses.");
    } finally {
      setBusy(false);
    }
  }

  async function runRisk() {
    setBusy(true);
    try {
      const out = await api.runRisk(session!.token, id);
      setFindings(out.findings);
      setTab("risks");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
        <div className="flex gap-2">
          <button
            onClick={loadConditions}
            disabled={busy}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-white disabled:opacity-50"
          >
            Upload sample conditions
          </button>
          <button
            onClick={runRisk}
            disabled={busy}
            className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Working…" : "Run risk review"}
          </button>
        </div>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      <div className="flex gap-1 border-b border-slate-200">
        {(["overview", "risks"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${
              tab === t ? "border-b-2 border-ink text-ink" : "text-slate-500 hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-3 font-semibold text-ink">Document checklist</h3>
          {missing ? (
            <div className="flex flex-wrap gap-2">
              {missing.expected.map((k) => {
                const present = missing.present.includes(k);
                return (
                  <span
                    key={k}
                    className={`rounded-full px-3 py-1 text-sm ${
                      present ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {present ? "✓" : "!"} {k.toUpperCase()}
                  </span>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Loading checklist…</p>
          )}
          <p className="mt-4 text-sm text-slate-500">
            Deadline wall lands here once extraction (TS-015) is wired — this slice shows the
            document checklist and the risk workbench.
          </p>
        </div>
      )}

      {tab === "risks" && (
        <div className="space-y-3">
          {!findings ? (
            <p className="text-sm text-slate-500">
              Run the risk review to populate the register. Absence findings appear even without an
              LLM key; clause judgments need <code>ANTHROPIC_API_KEY</code> on the server.
            </p>
          ) : findings.length === 0 ? (
            <p className="text-sm text-slate-500">No findings yet — upload the conditions and run again.</p>
          ) : (
            findings.map((f, i) => (
              <div key={i} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-2 flex items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <span className="text-xs uppercase tracking-wide text-slate-400">{f.category}</span>
                  <SourceBadge source="ai_suggestion" />
                  {f.source_page && <span className="text-xs text-slate-400">p{f.source_page}</span>}
                </div>
                <h4 className="font-semibold text-ink">{f.title}</h4>
                <p className="mt-1 text-sm text-slate-600">{f.detail}</p>
                {f.source_quote && (
                  <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-sm italic text-slate-500">
                    “{f.source_quote}”
                  </blockquote>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
