"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  api,
  API_BASE,
  ApiError,
  type Artifact,
  type Baseline,
  type BaselineCompare,
  type Deadline,
  type Finding,
  type Gate,
  type HandoverPack,
  type MissingDocs,
  type NoticeGap,
  type NoticeRule,
} from "@/lib/api";
import { useSession } from "@/components/session";
import { SeverityBadge, SourceBadge } from "@/components/badges";
import { artifactLabel, categoryLabel, deadlineLabel, statusLabel } from "@/lib/labels";
import { Paywall, type PaywallDetail } from "@/components/paywall";

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

const SAMPLE_BOQ = `src_sheet,src_row,item_code,description,unit_raw,qty,rate,amount
BOQ,1,1.1,Earthwork in excavation for foundation in ordinary soil,Cum,1200,250,300000
BOQ,2,1.2,Earthwork in excavation for foundation in ordinary soil,cum,1200,250,300000
BOQ,3,2.1,Providing and laying plain cement concrete 1:4:8,Cum,300,4500,1350000
BOQ,4,2.2,Reinforced cement concrete M25 in foundations,cum,450,6800,3060000
BOQ,5,3.1,Thermo-mechanically treated steel reinforcement,MT,85,65000,5525000
BOQ,6,4.1,Brick masonry in cement mortar 1:6,Cum,220,5200,1140000
BOQ,7,5.1,Cement plaster 12mm thick,Sqm,3000,180,540000
BOQ,8,6.1,Supplying and fixing MS railing,Rmt,500,0,0
BOQ,9,7.1,Waterproofing treatment to foundation raft,Sqm,800,950,760000
`;

export default function OpportunityDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useSession();
  const [tab, setTab] = useState<"overview" | "risks" | "boq" | "artifacts" | "handover">(
    "overview"
  );
  const [title, setTitle] = useState("Opportunity");
  const [missing, setMissing] = useState<MissingDocs | null>(null);
  const [deadlines, setDeadlines] = useState<Deadline[]>([]);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [gate, setGate] = useState<Gate | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [notices, setNotices] = useState<NoticeRule[]>([]);
  const [noticeGaps, setNoticeGaps] = useState<NoticeGap[]>([]);
  const [noticeRegion, setNoticeRegion] = useState<string | null>(null);
  const [handoverPack, setHandoverPack] = useState<HandoverPack | null>(null);
  const [compareData, setCompareData] = useState<BaselineCompare | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [paywall, setPaywall] = useState<PaywallDetail | null>(null);

  const refresh = useCallback(async () => {
    if (!session) return;
    api.getOpportunity(session.token, id).then((o) => setTitle(o.title)).catch(() => {});
    api.missingDocs(session.token, id).then(setMissing).catch(() => {});
    api.deadlines(session.token, id).then((d) => setDeadlines(d.deadlines)).catch(() => {});
    api.listFindings(session.token, id).then((f) => setFindings(f.findings)).catch(() => {});
    api.gate(session.token, id).then(setGate).catch(() => {});
    api.listArtifacts(session.token, id).then((a) => setArtifacts(a.artifacts)).catch(() => {});
    api.listBaselines(session.token, id).then((b) => setBaselines(b.baselines)).catch(() => {});
    api
      .noticeRegister(session.token, id)
      .then((n) => {
        setNotices(n.rules);
        setNoticeGaps(n.gaps);
        setNoticeRegion(n.region);
      })
      .catch(() => {});
    api.handover(session.token, id).then(setHandoverPack).catch(() => setHandoverPack(null));
    api.compareBaselines(session.token, id).then(setCompareData).catch(() => setCompareData(null));
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
      await api.runRisk(session!.token, id);
      await refresh();
      setTab("risks");
    } catch (e) {
      if (e instanceof ApiError && e.status === 402 && e.detail && typeof e.detail === "object") {
        setPaywall(e.detail as PaywallDetail);
      } else {
        setNote(e instanceof Error ? e.message : "Review failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function confirm(deadlineId: string) {
    await api.confirmDeadline(session!.token, id, deadlineId);
    refresh();
  }

  async function review(findingId: string, decision: string) {
    await api.reviewFinding(session!.token, findingId, decision);
    refresh();
  }

  async function downloadExport(format: string) {
    const res = await fetch(
      `${API_BASE}/export/opportunities/${id}?format=${format}`,
      { headers: { Authorization: `Bearer ${session!.token}` } }
    );
    if (!res.ok) {
      setNote("Export blocked — complete the review first.");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bid-review-pack.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function generate(kind: string) {
    setBusy(true);
    setNote(null);
    try {
      await api.generateArtifact(session!.token, id, kind);
      await refresh();
      setTab("artifacts");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function runBoq() {
    setBusy(true);
    setNote(null);
    try {
      await api.runBoq(session!.token, id, SAMPLE_BOQ);
      await refresh();
      setNote("BOQ checked — defects added to the register.");
    } finally {
      setBusy(false);
    }
  }

  async function freeze(source: "tender" | "award") {
    setBusy(true);
    setNote(null);
    try {
      const b = await api.freezeBaseline(session!.token, id, source);
      await refresh();
      setNote(`Baseline v${b.version} sealed (${source}) — hash ${b.content_sha256.slice(0, 12)}…`);
      setTab("handover");
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Freeze failed");
    } finally {
      setBusy(false);
    }
  }

  const riskFindings = (findings ?? []).filter((f) => f.producer !== "boq");
  const boqFindings = (findings ?? []).filter((f) => f.producer === "boq");

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

      {paywall && (
        <Paywall
          detail={paywall}
          onDismiss={() => setPaywall(null)}
          onPaid={() => {
            setPaywall(null);
            runRisk();
          }}
        />
      )}

      <div className="flex gap-1 border-b border-slate-200">
        {(["overview", "risks", "boq", "artifacts", "handover"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize ${
              tab === t ? "border-b-2 border-ink text-ink" : "text-slate-500 hover:text-ink"
            }`}
          >
            {t === "boq" ? "BOQ" : t}
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
          {gate && gate.total > 0 && (
            <div
              className={`rounded-md px-4 py-3 text-sm ${
                gate.export_allowed
                  ? "bg-emerald-50 text-emerald-800"
                  : "bg-amber-50 text-amber-800"
              }`}
            >
              {gate.export_allowed
                ? "✓ Review complete — export unlocked."
                : `Export blocked — ${gate.pending} of ${gate.total} findings still need review (accept/reject each).`}
            </div>
          )}
          {!findings ? (
            <p className="text-sm text-slate-500">
              Run the risk review to populate the register. Absence findings appear even without an
              LLM key; clause judgments need <code>ANTHROPIC_API_KEY</code> on the server.
            </p>
          ) : riskFindings.length === 0 ? (
            <p className="text-sm text-slate-500">No risk findings yet — upload the tender and run again.</p>
          ) : (
            riskFindings.map((f, i) => (
              <div key={f.id ?? i} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-2 flex items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <span className="text-xs uppercase tracking-wide text-slate-400">{categoryLabel(f.category)}</span>
                  <SourceBadge source={f.source ?? "ai_suggestion"} />
                  {f.source_page && <span className="text-xs text-slate-400">p{f.source_page}</span>}
                  {f.review_status && f.review_status !== "proposed" && (
                    <span
                      className={`ml-auto text-xs font-medium ${
                        f.review_status === "rejected" ? "text-slate-400" : "text-emerald-600"
                      }`}
                    >
                      {statusLabel(f.review_status)}
                    </span>
                  )}
                </div>
                <h4 className="font-semibold text-ink">{f.title}</h4>
                <p className="mt-1 text-sm text-slate-600">{f.detail}</p>
                {f.source_quote && (
                  <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-sm italic text-slate-500">
                    “{f.source_quote}”
                  </blockquote>
                )}
                {f.id && f.review_status === "proposed" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => review(f.id!, "accepted")}
                      className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:opacity-90"
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => review(f.id!, "rejected")}
                      className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:border-ink hover:text-ink"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {tab === "boq" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Deterministic BOQ checks — arithmetic, duplicates, blank rates, scope gaps. Zero LLM.
            </p>
            <button
              onClick={runBoq}
              disabled={busy}
              className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Checking…" : "Load sample BOQ & check"}
            </button>
          </div>
          {boqFindings.length === 0 ? (
            <p className="text-sm text-slate-500">
              No BOQ defects yet — run a check above (defects also feed the export register).
            </p>
          ) : (
            boqFindings.map((f, i) => (
              <div key={f.id ?? i} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-1 flex items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <span className="text-xs uppercase tracking-wide text-slate-400">{categoryLabel(f.category)}</span>
                  <SourceBadge source="deterministic_check" />
                </div>
                <h4 className="font-semibold text-ink">{f.title}</h4>
                <p className="mt-1 text-sm text-slate-600">{f.detail}</p>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "artifacts" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => generate("clarification_letter")}
              disabled={busy || !gate?.export_allowed}
              className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
            >
              Generate clarification letter
            </button>
            <button
              onClick={() => generate("assumptions_register")}
              disabled={busy || !gate?.export_allowed}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:opacity-40"
            >
              Generate assumptions register
            </button>
            <span className="mx-1 w-px self-stretch bg-slate-200" />
            <button
              onClick={() => downloadExport("docx")}
              disabled={!gate?.export_allowed}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:opacity-40"
            >
              Export .docx
            </button>
            <button
              onClick={() => downloadExport("xlsx")}
              disabled={!gate?.export_allowed}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:opacity-40"
            >
              Export .xlsx
            </button>
          </div>
          {!gate?.export_allowed && (
            <p className="text-xs text-amber-700">
              Accept/reject all findings on the Risks tab first — generation needs a completed review.
            </p>
          )}
          {artifacts.length === 0 ? (
            <p className="text-sm text-slate-500">No artifacts generated yet.</p>
          ) : (
            artifacts.map((a) => (
              <div key={a.id} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="font-semibold text-ink">{a.body.title}</h4>
                  <span className="text-xs text-slate-400">
                    {artifactLabel(a.kind)} · v{a.version}
                  </span>
                </div>
                {a.body.preamble && <p className="mb-3 text-sm text-slate-600">{a.body.preamble}</p>}
                <ol className="space-y-2 text-sm">
                  {a.body.items.map((item, i) => (
                    <li key={i} className="border-l-2 border-slate-200 pl-3">
                      <div className="font-medium text-slate-800">
                        {(item.heading as string) ??
                          `[${item.category as string}] ${item.assumption as string}`}
                      </div>
                      {typeof item.quote === "string" && (
                        <div className="italic text-slate-500">“{item.quote}”</div>
                      )}
                      {typeof item.ask === "string" && (
                        <div className="text-slate-600">{item.ask}</div>
                      )}
                      {typeof item.source_page === "number" && (
                        <span className="text-xs text-slate-400">p{item.source_page}</span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            ))
          )}
        </div>
      )}

      {tab === "handover" && (
        <HandoverTab
          gate={gate}
          baselines={baselines}
          notices={notices}
          noticeGaps={noticeGaps}
          noticeRegion={noticeRegion}
          pack={handoverPack}
          compare={compareData}
          busy={busy}
          onFreeze={freeze}
        />
      )}
    </div>
  );
}

function HandoverTab({
  gate,
  baselines,
  notices,
  noticeGaps,
  noticeRegion,
  pack,
  compare,
  busy,
  onFreeze,
}: {
  gate: Gate | null;
  baselines: Baseline[];
  notices: NoticeRule[];
  noticeGaps: NoticeGap[];
  noticeRegion: string | null;
  pack: HandoverPack | null;
  compare: BaselineCompare | null;
  busy: boolean;
  onFreeze: (source: "tender" | "award") => void;
}) {
  const canFreeze = !!gate?.export_allowed;
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="font-semibold text-ink">Baseline lock</h3>
        <p className="mt-1 text-sm text-slate-600">
          At award, freeze the reviewed commercial state into an immutable, hash-sealed record so
          tender knowledge survives handover. Freezing needs a completed review.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => onFreeze("tender")}
            disabled={busy || !canFreeze}
            className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            Freeze tender baseline
          </button>
          <button
            onClick={() => onFreeze("award")}
            disabled={busy || !canFreeze}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-white disabled:opacity-40"
          >
            Freeze award baseline
          </button>
        </div>
        {!canFreeze && (
          <p className="mt-2 text-xs text-amber-700">
            Accept/reject all findings on the Risks tab first — the freeze is gated on review.
          </p>
        )}
        {baselines.length > 0 && (
          <ul className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
            {baselines.map((b) => (
              <li key={b.id} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium text-ink capitalize">
                  v{b.version} · {b.source}
                </span>
                <span className="font-mono text-xs text-slate-400">
                  {b.content_sha256.slice(0, 16)}…
                </span>
                <span className="text-xs text-slate-500">
                  {b.counts.findings ?? 0} findings · {b.counts.notice_rules ?? 0} notices
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-ink">Notice-rule register</h3>
          {noticeRegion && (
            <span className="rounded-full bg-ink/5 px-2.5 py-1 text-xs font-semibold text-ink">
              standard: universal + {noticeRegion}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Contractual time windows extracted deterministically — the traps that become time-bar
          countdowns. Each carries its page citation.
        </p>
        {notices.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            No notice windows detected in the reviewed findings yet.
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {notices.map((n, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-ink px-2 py-0.5 text-xs font-bold text-white">
                    {n.days}d
                  </span>
                  <span className="uppercase tracking-wide text-xs text-slate-400">
                    {categoryLabel(n.category)}
                  </span>
                  {n.source_page && <span className="text-xs text-slate-400">p{n.source_page}</span>}
                </div>
                <p className="mt-1 text-slate-600">{n.trigger}</p>
              </li>
            ))}
          </ul>
        )}
        {noticeGaps.length > 0 && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h4 className="text-sm font-semibold text-amber-900">
              Expected notice regimes not found in this contract
            </h4>
            <p className="mt-1 text-xs text-amber-800">
              The standard expects these; the pack has no explicit window. Confirm against the
              originals — an absent regime can itself be a trap.
            </p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {noticeGaps.map((g) => (
                <li
                  key={g.key}
                  className="rounded-full bg-white px-2.5 py-1 text-xs text-amber-800 ring-1 ring-amber-200"
                  title={g.note ?? undefined}
                >
                  {g.label}
                  {g.typical_days != null && (
                    <span className="ml-1 text-amber-500">(usually {g.typical_days}d)</span>
                  )}
                  {g.origin === "org" && (
                    <span className="ml-1 rounded bg-ink px-1 text-[10px] font-bold uppercase text-white">
                      your standard
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {compare && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="font-semibold text-ink">Award vs tender</h3>
          <p className="mt-1 text-xs text-slate-500">
            Delta between the sealed tender baseline (v{compare.tender_version}) and the award
            baseline (v{compare.award_version}).
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3 text-sm">
            <DeltaCol title="Added at award" items={compare.added.map((f) => f.title)} tone="emerald" />
            <DeltaCol title="Dropped at award" items={compare.removed.map((f) => f.title)} tone="slate" />
            <DeltaCol title="Changed" items={compare.changed.map((c) => c.title)} tone="amber" />
          </div>
        </div>
      )}

      {pack && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-ink">Commercial handover pack</h3>
            <span className="font-mono text-xs text-slate-400">
              sealed {pack.sealed_hash.slice(0, 16)}…
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            v{pack.version} ({pack.source}) · {pack.counts.findings ?? 0} findings,{" "}
            {pack.counts.deadlines ?? 0} deadlines, {pack.counts.notice_rules ?? 0} notice rules.
          </p>
          <h4 className="mt-4 text-sm font-semibold text-ink">Key obligations</h4>
          {pack.key_obligations.length === 0 ? (
            <p className="text-sm text-slate-500">No critical/high obligations frozen.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {pack.key_obligations.map((f, i) => (
                <li key={i} className="border-l-2 border-slate-200 pl-3 text-sm">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={f.severity} />
                    <span className="font-medium text-slate-800">{f.title}</span>
                  </div>
                  {f.source_quote && (
                    <div className="mt-0.5 italic text-slate-500">“{f.source_quote}”</div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function DeltaCol({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  const cls =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "amber"
        ? "text-amber-700"
        : "text-slate-500";
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className={`text-xs font-semibold uppercase tracking-wide ${cls}`}>{title}</div>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-slate-400">none</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {items.map((t, i) => (
            <li key={i} className="text-slate-700">
              {t}
            </li>
          ))}
        </ul>
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
                    <span className="font-medium text-ink">{deadlineLabel(d.kind)}</span>
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
