"use client";

import { use, useCallback, useEffect, useState } from "react";
import { api, type Deadline, type Finding, type MissingDocs } from "@/lib/api";
import { useSession } from "@/components/session";
import { SeverityBadge, SourceBadge } from "@/components/badges";

const SAMPLE = `[p1]
NOTICE INVITING TENDER (NIT No. TS/DEMO/2026/001)
Construction of an office building with one basement, deep excavation adjacent to an existing structure, on a site with high sub-soil water. Completion: 30 months.
Last date of submission of bid: 25/07/2026 up to 15:00 hrs.
Pre-bid meeting shall be held on 24/07/2026.
Last date for seeking clarifications: 24/07/2026.
[p2]
Clause 14 — Price basis. The contract shall be on a firm price basis and no escalation whatsoever shall be payable.
[p4]
Clause 33 — Compensation for delay. Liquidated damages at the rate of 1% of the contract value shall be levied for each week of delay.
[p6]
Clause 52 — Termination. The Employer may terminate the contract for its convenience at any time, and the contractor shall have no claim for compensation.`;

const KIND_LABEL: Record<string, string> = {
  submission: "Bid submission",
  prebid_meeting: "Pre-bid meeting",
  clarification: "Clarification cut-off",
  validity: "Bid validity",
  emd: "EMD",
  completion_milestone: "Completion",
};

export default function OpportunityDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useSession();
  const [tab, setTab] = useState<"overview" | "risks">("overview");
  const [title, setTitle] = useState("Opportunity");
  const [missing, setMissing] = useState<MissingDocs | null>(null);
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!session) return;
    api.getOpportunity(session.token, id).then((o) => setTitle(o.title)).catch(() => {});
    api.missingDocs(session.token, id).then(setMissing).catch(() => {});
    api.deadlines(session.token, id).then((d) => setDeadlines(d.deadlines)).catch(() => {});
  }, [session, id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!session) return <p className="text-sm text-slate-500">Sign in to view this opportunity.</p>;

  async function loadConditions() {
    setBusy(true);
    setNote(null);
    try {
      await api.registerDocument(session!.token, id, "nit-and-conditions.md", SAMPLE);
      await refresh();
      setNote("Uploaded — classified, segmented into clauses, deadlines extracted.");
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

  async function confirm(deadlineId: string) {
    await api.confirmDeadline(session!.token, id, deadlineId);
    refresh();
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
            Upload sample tender
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
        <div className="space-y-6">
          <DeadlineWall deadlines={deadlines} onConfirm={confirm} />
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
          </div>
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
            <p className="text-sm text-slate-500">No findings yet — upload the tender and run again.</p>
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

function DeadlineWall({
  deadlines,
  onConfirm,
}: {
  deadlines: Deadline[];
  onConfirm: (id: string) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h3 className="mb-1 font-semibold text-ink">Deadline wall</h3>
      <p className="mb-4 text-xs text-slate-500">
        Extracted deterministically with page citations — confirm each before you rely on it.
      </p>
      {deadlines.length === 0 ? (
        <p className="text-sm text-slate-500">
          No deadlines yet — upload the tender (its NIT dates are extracted automatically).
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {deadlines.map((d) => {
            const days = d.due_at
              ? Math.ceil((new Date(d.due_at).getTime() - Date.now()) / 86_400_000)
              : null;
            const tone =
              days === null
                ? "text-slate-400"
                : days < 3
                  ? "text-red-600"
                  : days < 7
                    ? "text-amber-600"
                    : "text-emerald-600";
            return (
              <li key={d.id} className="flex items-center justify-between py-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink">{KIND_LABEL[d.kind] ?? d.kind}</span>
                    {d.source_page && (
                      <span className="text-xs text-slate-400">p{d.source_page}</span>
                    )}
                  </div>
                  <div className="text-sm text-slate-500">
                    {d.due_at ? new Date(d.due_at).toLocaleDateString() : "date not parsed"}
                    {days !== null && <span className={`ml-2 font-semibold ${tone}`}>({days}d)</span>}
                  </div>
                </div>
                {d.confirmed ? (
                  <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                    ✓ confirmed
                  </span>
                ) : (
                  <button
                    onClick={() => onConfirm(d.id)}
                    className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:border-ink hover:text-ink"
                  >
                    Confirm
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
