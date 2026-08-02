"use client";

import { useState } from "react";
import { api, type ChangeEvent } from "@/lib/api";

const CONFIRM_OUTCOMES = [
  { value: "changed", label: "Changed (claimable)" },
  { value: "not_changed", label: "Not changed" },
  { value: "clarification_only", label: "Clarification only" },
  { value: "contractor_risk", label: "Contractor risk" },
  { value: "client_risk", label: "Client risk" },
  { value: "unknown", label: "Unknown" },
];

const REASONS = ["scope_change", "price_adjustment", "time_extension", "drawing_revision", "instruction", "other"];
const CONFIDENCE = ["low", "medium", "high"];
const NOTICE_TYPES = ["", "variation", "extension_of_time", "delay", "defect", "payment"];

function statusClass(status: string) {
  switch (status) {
    case "confirmed":
      return "bg-emerald-50 text-emerald-700";
    case "candidate":
      return "bg-amber-50 text-amber-700";
    case "triaged":
      return "bg-blue-50 text-blue-700";
    case "rejected":
    case "closed":
      return "bg-slate-100 text-slate-600";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export function ChangesTab({
  token,
  opportunityId,
  events,
  onRefresh,
}: {
  token: string;
  opportunityId: string;
  events: ChangeEvent[];
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [selectedOutcome, setSelectedOutcome] = useState<Record<string, string>>({});
  const [deadlines, setDeadlines] = useState<Record<string, { notice_deadline?: string; deadline_days?: number; required_content?: string[]; deadline_unknown?: boolean }>>({});
  const [drafts, setDrafts] = useState<Record<string, { artifact_id: string; status: string }>>({});

  const [form, setForm] = useState({
    title: "",
    reason: "other",
    affected_scope: "",
    confidence_band: "medium",
    notice_type: "",
    trigger_date: "",
    source_quote: "",
    source_page: "",
    document_id: "",
  });

  async function handleConfirm(eventId: string) {
    const outcome = selectedOutcome[eventId];
    if (!outcome) return;
    setBusy(true);
    setNote(null);
    try {
      await api.confirmChangeEvent(token, eventId, outcome);
      setNote(`Confirmed as ${outcome}`);
      onRefresh();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Confirmation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleTriage(eventId: string, decision: string) {
    setBusy(true);
    setNote(null);
    try {
      await api.triageChangeEvent(token, eventId, decision);
      setNote(`Triaged as ${decision}`);
      onRefresh();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Triage failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleNoticeDeadline(eventId: string) {
    setBusy(true);
    setNote(null);
    try {
      const d = await api.getNoticeDeadline(token, eventId);
      setDeadlines((prev) => ({ ...prev, [eventId]: d }));
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Deadline lookup failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDraftNotice(eventId: string) {
    setBusy(true);
    setNote(null);
    try {
      const d = await api.requestNoticeDraft(token, eventId);
      setDrafts((prev) => ({ ...prev, [eventId]: d }));
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Draft request failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.source_quote.trim()) return;
    setBusy(true);
    setNote(null);
    try {
      await api.createChangeEvent(token, opportunityId, {
        title: form.title,
        reason: form.reason,
        affected_scope: form.affected_scope || undefined,
        confidence_band: form.confidence_band,
        notice_type: form.notice_type || undefined,
        trigger_date: form.trigger_date || undefined,
        sources: [
          {
            source_kind: "manual",
            source_quote: form.source_quote,
            source_page: form.source_page ? parseInt(form.source_page, 10) : null,
            document_id: form.document_id || null,
          },
        ],
      });
      setNote("Manual event created");
      setShowForm(false);
      setForm({ title: "", reason: "other", affected_scope: "", confidence_band: "medium", notice_type: "", trigger_date: "", source_quote: "", source_page: "", document_id: "" });
      onRefresh();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to create event");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-ink">Variation inbox</h3>
          <p className="text-sm text-slate-600">
            Triage and confirm candidate change events. Draft notices only become available after an event is confirmed.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          disabled={busy}
          className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          {showForm ? "Cancel" : "Add manual event"}
        </button>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      {showForm && (
        <form onSubmit={handleCreate} className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label htmlFor="change-title" className="text-sm font-medium text-slate-700">Title</label>
              <input
                id="change-title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="change-reason" className="text-sm font-medium text-slate-700">Reason</label>
              <select
                id="change-reason"
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {REASONS.map((r) => (
                  <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="change-confidence" className="text-sm font-medium text-slate-700">Confidence</label>
              <select
                id="change-confidence"
                value={form.confidence_band}
                onChange={(e) => setForm({ ...form, confidence_band: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {CONFIDENCE.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="change-notice-type" className="text-sm font-medium text-slate-700">Notice type</label>
              <select
                id="change-notice-type"
                value={form.notice_type}
                onChange={(e) => setForm({ ...form, notice_type: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {NOTICE_TYPES.map((n) => (
                  <option key={n || "none"} value={n}>{n ? n.replace(/_/g, " ") : "—"}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="change-trigger-date" className="text-sm font-medium text-slate-700">Trigger date</label>
              <input
                id="change-trigger-date"
                type="date"
                value={form.trigger_date}
                onChange={(e) => setForm({ ...form, trigger_date: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="change-source-page" className="text-sm font-medium text-slate-700">Source page</label>
              <input
                id="change-source-page"
                type="number"
                value={form.source_page}
                onChange={(e) => setForm({ ...form, source_page: e.target.value })}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="space-y-1">
            <label htmlFor="change-scope" className="text-sm font-medium text-slate-700">Affected scope</label>
            <input
              id="change-scope"
              value={form.affected_scope}
              onChange={(e) => setForm({ ...form, affected_scope: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="change-source-quote" className="text-sm font-medium text-slate-700">Source quote *</label>
            <textarea
              id="change-source-quote"
              value={form.source_quote}
              onChange={(e) => setForm({ ...form, source_quote: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              rows={3}
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="change-document-id" className="text-sm font-medium text-slate-700">Document id</label>
            <input
              id="change-document-id"
              value={form.document_id}
              onChange={(e) => setForm({ ...form, document_id: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="optional UUID"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
          >
            Create event
          </button>
        </form>
      )}

      {events.length === 0 ? (
        <p className="text-sm text-slate-500">No change events yet. Add a manual event or run a baseline diff.</p>
      ) : (
        <ul className="space-y-4">
          {events.map((event) => (
            <li key={event.id} className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-ink">{event.title}</h4>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className={`rounded-full px-2 py-0.5 font-medium ${statusClass(event.status)}`}>{event.status}</span>
                    <span className="capitalize">{event.reason.replace(/_/g, " ")}</span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5">{event.confidence_band} confidence</span>
                    {event.trigger_date && <span>trigger {event.trigger_date}</span>}
                    {event.notice_deadline && <span>deadline {event.notice_deadline}</span>}
                  </div>
                </div>
                {event.latest_confirmation && (
                  <span className="text-xs text-slate-500">
                    latest: {event.latest_confirmation.outcome.replace(/_/g, " ")}
                  </span>
                )}
              </div>

              {event.affected_scope && (
                <p className="text-sm text-slate-600"><span className="font-medium">Scope:</span> {event.affected_scope}</p>
              )}

              {event.sources && event.sources.length > 0 && (
                <div className="rounded-md bg-slate-50 p-3 text-sm">
                  <p className="font-medium text-slate-700">Source</p>
                  {event.sources.map((s, i) => (
                    <div key={i} className="mt-1 text-slate-600">
                      {s.source_quote && <p className="italic">“{s.source_quote}”</p>}
                      <p className="text-xs text-slate-400">
                        {s.source_kind}{s.source_page ? ` · page ${s.source_page}` : ""}{s.external_ref ? ` · ${s.external_ref}` : ""}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={selectedOutcome[event.id] || ""}
                  onChange={(e) => setSelectedOutcome((prev) => ({ ...prev, [event.id]: e.target.value }))}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                >
                  <option value="">Confirm outcome…</option>
                  {CONFIRM_OUTCOMES.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <button
                  onClick={() => handleConfirm(event.id)}
                  disabled={busy || !selectedOutcome[event.id]}
                  className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
                >
                  Confirm
                </button>
                <button
                  onClick={() => handleTriage(event.id, "rejected")}
                  disabled={busy}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Reject
                </button>
                {event.status === "confirmed" && (
                  <>
                    <button
                      onClick={() => handleNoticeDeadline(event.id)}
                      disabled={busy}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                    >
                      Notice deadline
                    </button>
                    <button
                      onClick={() => handleDraftNotice(event.id)}
                      disabled={busy}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                    >
                      Draft notice
                    </button>
                  </>
                )}
              </div>

              {(() => {
                const dl = deadlines[event.id];
                if (!dl) return null;
                return (
                  <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-800">
                    <p className="font-medium">Notice deadline</p>
                    {dl.deadline_unknown ? (
                      <p>Unknown — no matching notice rule found.</p>
                    ) : (
                      <>
                        <p>Deadline: {dl.notice_deadline} ({dl.deadline_days} days)</p>
                        {dl.required_content && (
                          <ul className="mt-1 list-disc pl-4 text-xs">
                            {dl.required_content.map((c, i) => (
                              <li key={i}>{c}</li>
                            ))}
                          </ul>
                        )}
                      </>
                    )}
                  </div>
                );
              })()}

              {(() => {
                const draft = drafts[event.id];
                if (!draft) return null;
                return (
                  <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">
                    <p className="font-medium">Draft created</p>
                    <p>Artifact {draft.artifact_id} · {draft.status}</p>
                  </div>
                );
              })()}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
