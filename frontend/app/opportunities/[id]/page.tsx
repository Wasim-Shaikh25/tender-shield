"use client";

import { use, useCallback, useEffect, useState } from "react";
import {
  api,
  API_BASE,
  type Artifact,
  type Baseline,
  type BaselineCompare,
  type ChangeEvent,
  type Claim,
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { ChangesTab } from "./changes-tab";
import { ClaimsTab } from "./claims-tab";
import { PricingTab } from "./pricing-tab";
import { DrawingsTab } from "./drawings-tab";
import { SubcontractsTab } from "./subcontracts-tab";
import { RulepackSelector } from "./rulepack-selector";
import { ExportMenu } from "@/components/ui/export-menu";

export default function OpportunityDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { session } = useSession();
  const [tab, setTab] = useState<
    "overview" | "risks" | "boq" | "artifacts" | "handover" | "audit" | "changes" | "claims" | "pricing" | "drawings" | "subcontracts"
  >("overview");
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
  const [boqCsv, setBoqCsv] = useState("");
  const [auditLog, setAuditLog] = useState<{ id: string; action: string; actor_email: string | null; created_at: string; meta: Record<string, unknown> }[]>([]);
  const [events, setEvents] = useState<ChangeEvent[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);

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
    api.auditTrail(session.token, id).then((d) => setAuditLog(d.audit)).catch(() => setAuditLog([]));
    api.listChangeInbox(session.token, id).then((d) => setEvents(d.events)).catch(() => setEvents([]));
    api.listClaims(session.token, id).then((d) => setClaims(d.claims)).catch(() => setClaims([]));
  }, [session, id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  if (!session) return <p className="text-sm text-slate-500">Sign in to view this opportunity.</p>;

  async function uploadFile(file: File) {
    setBusy(true);
    setNote(null);
    try {
      const doc = await api.uploadDocument(session!.token, id, file);
      await refresh();
      setNote(`Uploaded ${doc.filename} (${doc.chars} chars, OCR ${doc.ocr_status}).`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Upload failed");
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
    } finally {
      setBusy(false);
    }
  }

  async function confirm(deadlineId: string) {
    await api.confirmDeadline(session!.token, id, deadlineId);
    refresh();
  }

  async function review(findingId: string, decision: string) {
    await api.reviewFinding(session!.token, id, findingId, decision);
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
      await api.runBoq(session!.token, id, boqCsv);
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-heading-lg text-text-primary">{title}</h1>
          <p className="text-sm text-text-muted mt-1">Review this tender opportunity</p>
        </div>
        <div className="flex items-center gap-3">
          {session && <RulepackSelector token={session.token} opportunityId={id} />}
          <label className="cursor-pointer">
            <input
              type="file"
              className="hidden"
              accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.tiff,.tif,.zip"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadFile(file);
              }}
              disabled={busy}
            />
            <Button variant="secondary" size="md" disabled={busy} onClick={(e) => {
              (e.currentTarget.previousElementSibling as HTMLInputElement)?.click();
            }}>
              Upload file
            </Button>
          </label>
          {session && gate?.export_allowed && (
            <ExportMenu
              opportunityId={id}
              opportunityTitle={title}
              token={session.token}
              disabled={busy}
            />
          )}
          <Button
            variant="primary"
            size="md"
            onClick={runRisk}
            disabled={busy}
          >
            {busy ? "Working…" : "Run risk review"}
          </Button>
        </div>
      </div>

      {/* Status Messages */}
      {note && (
        <Alert variant="success" title="Success">
          {note}
        </Alert>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b border-border-default overflow-x-auto">
        {(["overview", "risks", "boq", "artifacts", "handover", "audit", "changes", "claims", "pricing", "drawings", "subcontracts"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium capitalize whitespace-nowrap transition-colors duration-base",
              tab === t
                ? "border-b-2 border-ink text-text-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            {t === "boq" ? "BOQ" : t}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-6">
          <DeadlineWall deadlines={deadlines} onConfirm={confirm} />
          <Card>
            <CardHeader>
              <CardTitle>Document Checklist</CardTitle>
              <CardDescription>Verify all required documents are present</CardDescription>
            </CardHeader>
            <CardContent>
              {missing ? (
                <div className="flex flex-wrap gap-2">
                  {missing.expected.map((k) => {
                    const present = missing.present.includes(k);
                    return (
                      <Badge
                        key={k}
                        variant={present ? "success" : "warning"}
                        size="sm"
                      >
                        {present ? "✓" : "!"} {k.toUpperCase()}
                      </Badge>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-text-muted">Loading checklist...</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "risks" && (
        <div className="space-y-4">
          {gate && gate.total > 0 && (
            <Alert
              variant={gate.export_allowed ? "success" : "warning"}
              title={gate.export_allowed ? "Review Complete" : "Action Required"}
            >
              {gate.export_allowed
                ? "All findings reviewed - export unlocked."
                : `${gate.pending} of ${gate.total} findings still need review (accept/reject each).`}
            </Alert>
          )}
          {!findings ? (
            <Alert variant="info" title="Run Risk Review">
              Upload the tender pack and run the risk review to see findings.
            </Alert>
          ) : riskFindings.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-text-secondary">No risk findings yet — upload the tender and run again.</p>
              </CardContent>
            </Card>
          ) : (
            riskFindings.map((f, i) => (
              <Card key={f.id ?? i}>
                <CardContent className="pt-6">
                  <div className="mb-3 flex items-start justify-between">
                    <div className="flex items-center gap-2 flex-wrap">
                      <SeverityBadge severity={f.severity} />
                      <Badge variant="secondary" size="sm">
                        {categoryLabel(f.category)}
                      </Badge>
                      <SourceBadge source={f.source ?? "ai_suggestion"} />
                      {f.source_page && (
                        <span className="text-xs text-text-muted">p{f.source_page}</span>
                      )}
                    </div>
                    {f.review_status && f.review_status !== "proposed" && (
                      <Badge
                        variant={f.review_status === "rejected" ? "secondary" : "success"}
                        size="sm"
                      >
                        {statusLabel(f.review_status)}
                      </Badge>
                    )}
                  </div>
                  <h4 className="font-semibold text-text-primary text-base">{f.title}</h4>
                  <p className="mt-2 text-sm text-text-secondary">{f.detail}</p>
                  {f.source_quote && (
                    <blockquote className="mt-3 border-l-2 border-border-default pl-3 text-sm italic text-text-tertiary">
                      {`"${f.source_quote}"`}
                    </blockquote>
                  )}
                  {f.id && f.review_status === "proposed" && (
                    <div className="mt-4 flex gap-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => review(f.id!, "accepted")}
                      >
                        Accept
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => review(f.id!, "rejected")}
                      >
                        Reject
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {tab === "boq" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>BOQ Checker</CardTitle>
              <CardDescription>Verify Bill of Quantities for arithmetic, duplicates, and scope gaps</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label htmlFor="boq-csv" className="block text-sm font-medium text-text-primary mb-2">
                  CSV Format
                </label>
                <p className="text-sm text-text-secondary mb-3">
                  Columns: src_sheet, src_row, item_code, description, unit_raw, qty, rate, amount
                </p>
                <textarea
                  id="boq-csv"
                  value={boqCsv}
                  onChange={(e) => setBoqCsv(e.target.value)}
                  rows={6}
                  placeholder="src_sheet,src_row,item_code,description,unit_raw,qty,rate,amount"
                  className="w-full rounded-md border border-border-default px-3 py-2 text-sm font-mono outline-none focus:border-ink focus:ring-1 focus:ring-ink"
                />
              </div>
              <Button
                variant="primary"
                size="md"
                onClick={runBoq}
                disabled={busy || !boqCsv.trim()}
              >
                {busy ? "Checking…" : "Check BOQ"}
              </Button>
            </CardContent>
          </Card>

          {boqFindings.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-text-secondary">No BOQ defects yet — paste a CSV and run a check.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {boqFindings.map((f, i) => (
                <Card key={f.id ?? i}>
                  <CardContent className="pt-6">
                    <div className="flex items-center gap-2 mb-2">
                      <SeverityBadge severity={f.severity} />
                      <Badge variant="secondary" size="sm">
                        {categoryLabel(f.category)}
                      </Badge>
                      <SourceBadge source="deterministic_check" />
                    </div>
                    <h4 className="font-semibold text-text-primary">{f.title}</h4>
                    <p className="mt-1 text-sm text-text-secondary">{f.detail}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "artifacts" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Generate & Export</CardTitle>
              <CardDescription>Create artifacts and export your bid review</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => generate("clarification_letter")}
                  disabled={busy || !gate?.export_allowed}
                >
                  Generate clarification letter
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  onClick={() => generate("assumptions_register")}
                  disabled={busy || !gate?.export_allowed}
                >
                  Generate assumptions register
                </Button>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => downloadExport("docx")}
                  disabled={!gate?.export_allowed}
                >
                  Export .docx
                </Button>
                <Button
                  variant="outline"
                  size="md"
                  onClick={() => downloadExport("xlsx")}
                  disabled={!gate?.export_allowed}
                >
                  Export .xlsx
                </Button>
              </div>
              {!gate?.export_allowed && (
                <Alert variant="warning" title="Complete Review First">
                  Accept/reject all findings on the Risks tab to unlock generation and export.
                </Alert>
              )}
            </CardContent>
          </Card>

          {artifacts.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-text-secondary">No artifacts generated yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {artifacts.map((a) => (
                <Card key={a.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle>{a.body.title}</CardTitle>
                      <Badge variant="secondary" size="sm">
                        {artifactLabel(a.kind)} v{a.version}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {a.body.preamble && (
                      <p className="text-sm text-text-secondary">{a.body.preamble}</p>
                    )}
                    <ol className="space-y-2 text-sm">
                      {a.body.items.map((item, i) => (
                        <li key={i} className="border-l-2 border-border-default pl-3">
                          <div className="font-medium text-text-primary">
                            {(item.heading as string) ??
                              `[${item.category as string}] ${item.assumption as string}`}
                          </div>
                          {typeof item.quote === "string" && (
                            <div className="italic text-text-muted text-sm">{`"${item.quote}"`}</div>
                          )}
                          {typeof item.ask === "string" && (
                            <div className="text-text-secondary text-sm">{item.ask}</div>
                          )}
                          {typeof item.source_page === "number" && (
                            <span className="text-xs text-text-muted">p{item.source_page}</span>
                          )}
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              ))}
            </div>
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

      {tab === "audit" && (
        <div className="space-y-3">
          {auditLog.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-text-secondary">No audit entries yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {auditLog.map((a) => (
                <Card key={a.id}>
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium capitalize text-text-primary">
                        {a.action.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-text-muted">
                        {new Date(a.created_at).toLocaleString()}
                      </span>
                    </div>
                    {a.actor_email && (
                      <p className="text-sm text-text-secondary">by {a.actor_email}</p>
                    )}
                    {Object.keys(a.meta).length > 0 && (
                      <pre className="mt-2 rounded bg-bg-secondary p-2 text-xs text-text-secondary font-mono">
                        {JSON.stringify(a.meta, null, 2)}
                      </pre>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "changes" && session && (
        <ChangesTab token={session.token} opportunityId={id} events={events} onRefresh={refresh} />
      )}

      {tab === "claims" && session && (
        <ClaimsTab token={session.token} opportunityId={id} claims={claims} onRefresh={refresh} />
      )}

      {tab === "pricing" && session && (
        <PricingTab token={session.token} opportunityId={id} boqCsv={boqCsv} gate={gate} />
      )}

      {tab === "drawings" && session && (
        <DrawingsTab token={session.token} opportunityId={id} />
      )}

      {tab === "subcontracts" && session && (
        <SubcontractsTab token={session.token} opportunityId={id} isEstimator={["estimator", "admin", "owner", "superadmin"].includes(session.role)} />
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
      <Card>
        <CardHeader>
          <CardTitle>Baseline Lock</CardTitle>
          <CardDescription>
            Freeze the reviewed commercial state into an immutable, hash-sealed record
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              size="md"
              onClick={() => onFreeze("tender")}
              disabled={busy || !canFreeze}
            >
              Freeze tender baseline
            </Button>
            <Button
              variant="secondary"
              size="md"
              onClick={() => onFreeze("award")}
              disabled={busy || !canFreeze}
            >
              Freeze award baseline
            </Button>
          </div>
          {!canFreeze && (
            <Alert variant="warning" title="Complete Review First">
              Accept/reject all findings on the Risks tab to enable freezing.
            </Alert>
          )}
          {baselines.length > 0 && (
            <div className="space-y-2 border-t border-border-default pt-4">
              <p className="text-sm font-medium text-text-primary">Sealed Baselines</p>
              {baselines.map((b) => (
                <div
                  key={b.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border-default"
                >
                  <span className="font-medium text-text-primary capitalize">
                    v{b.version} · {b.source}
                  </span>
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-xs text-text-muted">
                      {b.content_sha256.slice(0, 16)}…
                    </span>
                    <span className="text-xs text-text-secondary">
                      {b.counts.findings ?? 0} findings · {b.counts.notice_rules ?? 0} notices
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Notice-Rule Register</CardTitle>
              <CardDescription>Contractual time windows and deadline triggers</CardDescription>
            </div>
            {noticeRegion && (
              <Badge variant="secondary" size="sm">
                {noticeRegion}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {notices.length === 0 ? (
            <p className="text-sm text-text-secondary">
              No notice windows detected in the reviewed findings yet.
            </p>
          ) : (
            <div className="space-y-2">
              {notices.map((n, i) => (
                <div key={i} className="rounded-lg border border-border-default p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="primary" size="sm">
                      {n.days}d
                    </Badge>
                    <Badge variant="secondary" size="sm">
                      {categoryLabel(n.category)}
                    </Badge>
                    {n.source_page && (
                      <span className="text-xs text-text-muted">p{n.source_page}</span>
                    )}
                  </div>
                  <p className="text-sm text-text-secondary">{n.trigger}</p>
                </div>
              ))}
            </div>
          )}
          {noticeGaps.length > 0 && (
            <Alert variant="warning" title="Missing Notice Regimes">
              <div className="text-sm space-y-2">
                <p>
                  The standard expects these windows, but the contract has no explicit language.
                  Confirm against the originals — absence can itself be a trap.
                </p>
                <div className="flex flex-wrap gap-2">
                  {noticeGaps.map((g) => (
                    <Badge
                      key={g.key}
                      variant="warning"
                      size="sm"
                      title={g.note ?? undefined}
                    >
                      {g.label}
                      {g.typical_days != null && ` (${g.typical_days}d)`}
                    </Badge>
                  ))}
                </div>
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>

      {compare && (
        <Card>
          <CardHeader>
            <CardTitle>Award vs Tender Comparison</CardTitle>
            <CardDescription>
              Delta between sealed tender v{compare.tender_version} and award v{compare.award_version}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-3">
              <DeltaCol title="Added at award" items={compare.added.map((f) => f.title)} variant="success" />
              <DeltaCol title="Dropped at award" items={compare.removed.map((f) => f.title)} variant="secondary" />
              <DeltaCol title="Changed" items={compare.changed.map((c) => c.title)} variant="warning" />
            </div>
          </CardContent>
        </Card>
      )}

      {pack && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle>Commercial Handover Pack</CardTitle>
                <CardDescription>
                  v{pack.version} ({pack.source}) · {pack.counts.findings ?? 0} findings,{" "}
                  {pack.counts.deadlines ?? 0} deadlines, {pack.counts.notice_rules ?? 0} notice rules
                </CardDescription>
              </div>
              <span className="font-mono text-xs text-text-muted">
                {pack.sealed_hash.slice(0, 16)}…
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-text-primary mb-3">Key Obligations</h4>
              {pack.key_obligations.length === 0 ? (
                <p className="text-sm text-text-secondary">No critical/high obligations frozen.</p>
              ) : (
                <div className="space-y-2">
                  {pack.key_obligations.map((f, i) => (
                    <div key={i} className="border-l-2 border-border-default pl-3">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={f.severity} />
                        <span className="font-medium text-text-primary">{f.title}</span>
                      </div>
                      {f.source_quote && (
                        <div className="mt-1 italic text-text-muted text-sm">
                          {`"${f.source_quote}"`}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DeltaCol({ title, items, variant }: { title: string; items: string[]; variant: "success" | "warning" | "secondary" }) {
  const colorClass = {
    success: "text-success",
    warning: "text-warning",
    secondary: "text-text-secondary",
  }[variant];

  return (
    <div className="rounded-lg border border-border-default p-3">
      <div className={`text-xs font-semibold uppercase tracking-wide ${colorClass}`}>
        {title}
      </div>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-text-muted">none</p>
      ) : (
        <ul className="mt-2 space-y-1">
          {items.map((t, i) => (
            <li key={i} className="text-sm text-text-primary">
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
    <Card>
      <CardHeader>
        <CardTitle>Deadline Wall</CardTitle>
        <CardDescription>Key deadlines extracted from the tender pack</CardDescription>
      </CardHeader>
      <CardContent>
        {deadlines.length === 0 ? (
          <p className="text-sm text-text-secondary">
            No deadlines yet — upload the tender to extract dates automatically.
          </p>
        ) : (
          <div className="space-y-2">
            {deadlines.map((d) => {
              const days = d.due_at
                ? Math.ceil((new Date(d.due_at).getTime() - Date.now()) / 86_400_000)
                : null;
              const urgencyVariant: "error" | "warning" | "info" =
                days === null ? "info" : days < 3 ? "error" : days < 7 ? "warning" : "info";

              return (
                <div
                  key={d.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-border-default hover:bg-bg-secondary transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-text-primary">
                        {deadlineLabel(d.kind)}
                      </span>
                      {d.source_page && (
                        <span className="text-xs text-text-muted">p{d.source_page}</span>
                      )}
                    </div>
                    <div className="text-sm text-text-secondary mt-1">
                      {d.due_at ? new Date(d.due_at).toLocaleDateString("en-IN") : "date not parsed"}
                      {days !== null && (
                        <span className="ml-2 font-semibold">({days}d)</span>
                      )}
                    </div>
                  </div>
                  {d.confirmed ? (
                    <Badge variant="success" size="sm">
                      ✓ confirmed
                    </Badge>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onConfirm(d.id)}
                    >
                      Confirm
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
