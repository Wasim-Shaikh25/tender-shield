"use client";

import { useEffect, useState } from "react";
import {
  api,
  type Claim,
  type ClaimChronologyEntry,
  type ClaimChecklistItem,
  type ClaimDraft,
  type ClaimLineItem,
  type ClaimNegotiation,
  type ClaimQuantum,
  type ClaimResponse,
  type ClaimSettlement,
} from "@/lib/api";

const CLAIM_TYPES = ["variation", "extension_of_time", "loss_and_expense", "disruption", "defect", "payment", "other"];
const RESPONSE_KINDS = ["acknowledgement", "rejection", "request_for_information", "counter_offer", "approval", "silence"];
const DRAFT_KINDS = ["particulars", "full_pack", "eot", "variation_proposal"];

function statusClass(status: string) {
  switch (status) {
    case "settled":
      return "bg-emerald-50 text-emerald-700";
    case "submitted":
    case "under_review":
      return "bg-blue-50 text-blue-700";
    case "negotiating":
      return "bg-amber-50 text-amber-700";
    case "rejected":
    case "withdrawn":
      return "bg-slate-100 text-slate-600";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

function formatMinor(amount?: number | null, currency = "INR") {
  if (amount === undefined || amount === null) return "—";
  return `${(amount / 100).toLocaleString()} ${currency}`;
}

export function ClaimsTab({
  token,
  opportunityId,
  claims,
  onRefresh,
}: {
  token: string;
  opportunityId: string;
  claims: Claim[];
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [selected, setSelected] = useState<Claim | null>(null);
  const [subTab, setSubTab] = useState<"overview" | "chronology" | "checklist" | "quantum" | "negotiations" | "drafts">("overview");

  const [claimDetail, setClaimDetail] = useState<Claim | null>(null);
  const [chronology, setChronology] = useState<ClaimChronologyEntry[]>([]);
  const [checklist, setChecklist] = useState<ClaimChecklistItem[]>([]);
  const [quantum, setQuantum] = useState<ClaimQuantum | null>(null);
  const [responses, setResponses] = useState<ClaimResponse[]>([]);
  const [negotiations, setNegotiations] = useState<ClaimNegotiation[]>([]);
  const [settlement, setSettlement] = useState<ClaimSettlement | null>(null);
  const [drafts, setDrafts] = useState<ClaimDraft[]>([]);
  const [chain, setChain] = useState<{ status: string; missing_link?: string } | null>(null);

  const [newClaim, setNewClaim] = useState({
    claim_type: "variation",
    title: "",
    change_event_id: "",
    claim_amount_minor: "",
    currency: "INR",
  });

  useEffect(() => {
    if (!selected) return;
    setNote(null);
    api.getClaim(token, selected.id).then((c) => setClaimDetail(c)).catch(() => {});
    api.getClaimChronology(token, selected.id).then((d) => setChronology(d.entries)).catch(() => setChronology([]));
    api.getClaimChecklist(token, selected.id).then((d) => setChecklist(d.items)).catch(() => setChecklist([]));
    api.getClaimQuantum(token, selected.id).then((d) => setQuantum(d)).catch(() => setQuantum(null));
    api.listClaimDrafts(token, selected.id).then((d) => setDrafts(d.drafts)).catch(() => setDrafts([]));
    api.getClaimChainIntegrity(token, selected.id).then((d) => setChain(d)).catch(() => setChain(null));
    // Responses, negotiations, settlement are not exposed by a list endpoint; we infer from claim detail or draft body
    setResponses([]);
    setNegotiations([]);
    setSettlement(null);
  }, [token, selected]);

  async function handleCreateClaim(e: React.FormEvent) {
    e.preventDefault();
    if (!newClaim.title.trim() || !newClaim.claim_type) return;
    setBusy(true);
    setNote(null);
    try {
      await api.createClaim(token, opportunityId, {
        claim_type: newClaim.claim_type,
        title: newClaim.title,
        change_event_id: newClaim.change_event_id || undefined,
        claim_amount_minor: newClaim.claim_amount_minor ? parseInt(newClaim.claim_amount_minor, 10) : undefined,
        currency: newClaim.currency,
      });
      setNote("Claim created");
      setNewClaim({ claim_type: "variation", title: "", change_event_id: "", claim_amount_minor: "", currency: "INR" });
      onRefresh();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to create claim");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitClaim(claimId: string) {
    setBusy(true);
    setNote(null);
    try {
      await api.submitClaim(token, claimId);
      setNote("Claim submitted");
      onRefresh();
      api.getClaim(token, claimId).then((c) => { setClaimDetail(c); setSelected(c); }).catch(() => {});
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerateDraft(kind: string) {
    if (!selected) return;
    setBusy(true);
    setNote(null);
    try {
      const d = await api.generateClaimDraft(token, selected.id, kind);
      setNote(`Draft ${d.draft_kind} v${d.version} created`);
      api.listClaimDrafts(token, selected.id).then((r) => setDrafts(r.drafts)).catch(() => {});
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Draft failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold text-ink">Claims workspace</h3>
        <p className="text-sm text-slate-600">
          Build defensible claim packages: chronology, checklist, quantum, responses, negotiations, settlement.
        </p>
      </div>

      {note && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{note}</p>}

      <form onSubmit={handleCreateClaim} className="rounded-xl border border-slate-200 bg-white p-5">
        <h4 className="mb-3 text-sm font-semibold text-ink">New claim</h4>
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1">
            <label htmlFor="claim-type" className="text-sm font-medium text-slate-700">Type</label>
            <select
              id="claim-type"
              value={newClaim.claim_type}
              onChange={(e) => setNewClaim({ ...newClaim, claim_type: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {CLAIM_TYPES.map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <label htmlFor="claim-title" className="text-sm font-medium text-slate-700">Title</label>
            <input
              id="claim-title"
              value={newClaim.title}
              onChange={(e) => setNewClaim({ ...newClaim, title: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="claim-amount" className="text-sm font-medium text-slate-700">Claim amount (minor)</label>
            <input
              id="claim-amount"
              type="number"
              value={newClaim.claim_amount_minor}
              onChange={(e) => setNewClaim({ ...newClaim, claim_amount_minor: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor="claim-change-event" className="text-sm font-medium text-slate-700">Change event id</label>
            <input
              id="claim-change-event"
              value={newClaim.change_event_id}
              onChange={(e) => setNewClaim({ ...newClaim, change_event_id: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="optional UUID"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="claim-currency" className="text-sm font-medium text-slate-700">Currency</label>
            <input
              id="claim-currency"
              value={newClaim.currency}
              onChange={(e) => setNewClaim({ ...newClaim, currency: e.target.value })}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={busy}
          className="mt-4 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Create claim
        </button>
      </form>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h4 className="mb-3 text-sm font-semibold text-ink">Claim list</h4>
        {claims.length === 0 ? (
          <p className="text-sm text-slate-500">No claims yet.</p>
        ) : (
          <ul className="space-y-2">
            {claims.map((claim) => (
              <li key={claim.id}>
                <button
                  onClick={() => { setSelected(claim); setSubTab("overview"); }}
                  className={`w-full rounded-md border px-4 py-3 text-left ${selected?.id === claim.id ? "border-ink bg-ink/5" : "border-slate-200 hover:bg-slate-50"}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-ink">{claim.title}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusClass(claim.status)}`}>{claim.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {claim.claim_type.replace(/_/g, " ")} · {formatMinor(claim.claim_amount_minor, claim.currency)} · {claim.created_at ? new Date(claim.created_at).toLocaleDateString() : ""}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && claimDetail && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-ink">{claimDetail.title}</h3>
            <div className="flex items-center gap-2">
              {claimDetail.status === "draft" && (
                <button
                  onClick={() => handleSubmitClaim(claimDetail.id)}
                  disabled={busy}
                  className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
                >
                  Submit claim
                </button>
              )}
            </div>
          </div>

          {chain && (
            <div className={`rounded-md p-2 text-sm ${chain.status === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
              Chain integrity: {chain.status}{chain.missing_link ? ` · missing ${chain.missing_link}` : ""}
            </div>
          )}

          <div className="flex gap-1 border-b border-slate-200">
            {(["overview", "chronology", "checklist", "quantum", "negotiations", "drafts"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setSubTab(t)}
                className={`px-3 py-1.5 text-sm font-medium capitalize ${subTab === t ? "border-b-2 border-ink text-ink" : "text-slate-500 hover:text-ink"}`}
              >
                {t.replace(/_/g, " ")}
              </button>
            ))}
          </div>

          {subTab === "overview" && <OverviewPanel claim={claimDetail} settlement={settlement} />}
          {subTab === "chronology" && <ChronologyPanel chronology={chronology} />}
          {subTab === "checklist" && <ChecklistPanel token={token} claimId={claimDetail.id} items={checklist} onRefresh={() => api.getClaimChecklist(token, claimDetail.id).then((d) => setChecklist(d.items)).catch(() => {})} />}
          {subTab === "quantum" && <QuantumPanel token={token} claimId={claimDetail.id} quantum={quantum} onRefresh={() => api.getClaimQuantum(token, claimDetail.id).then((d) => setQuantum(d)).catch(() => {})} />}
          {subTab === "negotiations" && <NegotiationsPanel token={token} claimId={claimDetail.id} negotiations={negotiations} responses={responses} settlement={settlement} onRefresh={refreshNegotiations} />}
          {subTab === "drafts" && <DraftsPanel drafts={drafts} onGenerate={handleGenerateDraft} />}
        </div>
      )}
    </div>
  );

  async function refreshNegotiations() {
    if (!selected) return;
    // No dedicated list endpoints; refetch claim detail and rely on future API additions
    api.getClaim(token, selected.id).then((c) => setClaimDetail(c)).catch(() => {});
  }
}

function OverviewPanel({ claim, settlement }: { claim: Claim; settlement: ClaimSettlement | null }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-2 text-sm">
      <p><span className="font-medium text-slate-700">Type:</span> {claim.claim_type.replace(/_/g, " ")}</p>
      <p><span className="font-medium text-slate-700">Status:</span> {claim.status}</p>
      <p><span className="font-medium text-slate-700">Claim amount:</span> {formatMinor(claim.claim_amount_minor, claim.currency)}</p>
      {claim.recovered_amount_minor !== undefined && claim.recovered_amount_minor !== null && (
        <p><span className="font-medium text-slate-700">Recovered:</span> {formatMinor(claim.recovered_amount_minor, claim.currency)}</p>
      )}
      {claim.completeness_score !== undefined && claim.completeness_score !== null && (
        <p><span className="font-medium text-slate-700">Completeness:</span> {claim.completeness_score}%</p>
      )}
      {settlement && (
        <p><span className="font-medium text-slate-700">Settlement:</span> {settlement.outcome} · {formatMinor(settlement.settled_amount_minor, settlement.currency)}</p>
      )}
      {claim.description && <p className="text-slate-600">{claim.description}</p>}
    </div>
  );
}

function ChronologyPanel({ chronology }: { chronology: ClaimChronologyEntry[] }) {
  if (chronology.length === 0) return <p className="text-sm text-slate-500">No chronology entries yet.</p>;
  return (
    <ul className="space-y-2">
      {chronology.map((entry) => (
        <li key={entry.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink">{entry.title}</span>
            <span className="text-xs text-slate-400">{new Date(entry.occurred_at).toLocaleString()}</span>
          </div>
          <div className="text-xs text-slate-500 capitalize">{entry.entry_type.replace(/_/g, " ")}{entry.source_kind ? ` · ${entry.source_kind}` : ""}</div>
          {entry.source_quote && <p className="mt-2 text-sm italic text-slate-600">“{entry.source_quote}”</p>}
        </li>
      ))}
    </ul>
  );
}

function ChecklistPanel({ token, claimId, items, onRefresh }: { token: string; claimId: string; items: ClaimChecklistItem[]; onRefresh: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  async function override(itemId: string) {
    if (!note.trim()) return;
    setBusy(true);
    try {
      await api.overrideChecklistItem(token, claimId, itemId, note);
      setNote("");
      setSelected(null);
      onRefresh();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Override failed");
    } finally {
      setBusy(false);
    }
  }

  if (items.length === 0) return <p className="text-sm text-slate-500">No checklist items yet.</p>;
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink capitalize">{item.item_type.replace(/_/g, " ")}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs ${item.present ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
              {item.present ? "present" : "missing"}
            </span>
          </div>
          {item.required && <p className="text-xs text-slate-500">required</p>}
          {item.override_note && <p className="text-xs text-slate-600">Override: {item.override_note}</p>}
          {!item.present && (
            <div className="mt-2 flex gap-2">
              {selected === item.id ? (
                <>
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
                    placeholder="override reason"
                  />
                  <button onClick={() => override(item.id)} disabled={busy} className="rounded-md bg-ink px-2 py-1 text-xs text-white">Save</button>
                  <button onClick={() => setSelected(null)} className="rounded-md border border-slate-300 px-2 py-1 text-xs">Cancel</button>
                </>
              ) : (
                <button onClick={() => { setSelected(item.id); setNote(""); }} className="text-xs text-slate-600 hover:text-ink">Override…</button>
              )}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function QuantumPanel({ token, claimId, quantum, onRefresh }: { token: string; claimId: string; quantum: ClaimQuantum | null; onRefresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ description: "", quantity: "", unit: "", rate_minor: "", daywork_days: "", daywork_rate_minor: "", currency: "" });

  async function addLineItem(e: React.FormEvent) {
    e.preventDefault();
    if (!form.description.trim() || !form.quantity || !form.unit || !form.rate_minor) return;
    setBusy(true);
    try {
      await api.addClaimLineItem(token, claimId, {
        description: form.description,
        quantity: form.quantity,
        unit: form.unit,
        rate_minor: parseInt(form.rate_minor, 10),
        daywork_days: form.daywork_days ? parseInt(form.daywork_days, 10) : undefined,
        daywork_rate_minor: form.daywork_rate_minor ? parseInt(form.daywork_rate_minor, 10) : undefined,
        currency: form.currency || undefined,
      });
      setForm({ description: "", quantity: "", unit: "", rate_minor: "", daywork_days: "", daywork_rate_minor: "", currency: "" });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add line item");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {quantum && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-medium text-ink">Total</span>
            <span className="font-semibold">{formatMinor(quantum.total_minor, quantum.currency)}</span>
          </div>
          <p className="text-xs text-slate-500">Measured: {formatMinor(quantum.measured_total_minor, quantum.currency)} · Daywork: {formatMinor(quantum.daywork_total_minor, quantum.currency)}</p>
          {quantum.line_items.length > 0 && (
            <ul className="mt-3 space-y-2">
              {quantum.line_items.map((item) => (
                <li key={item.id} className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
                  <span>{item.description} · {item.quantity} {item.unit} @ {formatMinor(item.rate_minor, item.currency)}</span>
                  <span className="font-medium">{formatMinor(item.total_minor, item.currency)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <form onSubmit={addLineItem} className="rounded-xl border border-slate-200 bg-white p-4">
        <h5 className="mb-2 text-sm font-semibold text-ink">Add line item</h5>
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="space-y-1 sm:col-span-2">
            <label htmlFor="li-desc" className="text-sm font-medium text-slate-700">Description</label>
            <input id="li-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-qty" className="text-sm font-medium text-slate-700">Qty</label>
            <input id="li-qty" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-unit" className="text-sm font-medium text-slate-700">Unit</label>
            <input id="li-unit" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-rate" className="text-sm font-medium text-slate-700">Rate (minor)</label>
            <input id="li-rate" type="number" value={form.rate_minor} onChange={(e) => setForm({ ...form, rate_minor: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-dw-days" className="text-sm font-medium text-slate-700">Daywork days</label>
            <input id="li-dw-days" type="number" value={form.daywork_days} onChange={(e) => setForm({ ...form, daywork_days: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-dw-rate" className="text-sm font-medium text-slate-700">Daywork rate</label>
            <input id="li-dw-rate" type="number" value={form.daywork_rate_minor} onChange={(e) => setForm({ ...form, daywork_rate_minor: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" />
          </div>
          <div className="space-y-1">
            <label htmlFor="li-currency" className="text-sm font-medium text-slate-700">Currency</label>
            <input id="li-currency" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm" />
          </div>
        </div>
        <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40">
          Add line item
        </button>
      </form>
    </div>
  );
}

function NegotiationsPanel({
  token,
  claimId,
  negotiations,
  responses,
  settlement,
  onRefresh,
}: {
  token: string;
  claimId: string;
  negotiations: ClaimNegotiation[];
  responses: ClaimResponse[];
  settlement: ClaimSettlement | null;
  onRefresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [responseForm, setResponseForm] = useState({ response_kind: "", received_at: "", responder: "", due_at: "", notes: "" });
  const [negotiationForm, setNegotiationForm] = useState({ offered_amount_minor: "", counter_amount_minor: "", status: "open" });
  const [settlementForm, setSettlementForm] = useState({ outcome: "", settled_amount_minor: "", notes: "" });

  async function addResponse(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.recordClaimResponse(token, claimId, {
        response_kind: responseForm.response_kind,
        received_at: responseForm.received_at,
        responder: responseForm.responder,
        due_at: responseForm.due_at || undefined,
        notes: responseForm.notes,
      });
      setResponseForm({ response_kind: "", received_at: "", responder: "", due_at: "", notes: "" });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to record response");
    } finally {
      setBusy(false);
    }
  }

  async function addNegotiation(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.recordClaimNegotiation(token, claimId, {
        offered_amount_minor: parseInt(negotiationForm.offered_amount_minor, 10),
        counter_amount_minor: negotiationForm.counter_amount_minor ? parseInt(negotiationForm.counter_amount_minor, 10) : undefined,
        status: negotiationForm.status,
      });
      setNegotiationForm({ offered_amount_minor: "", counter_amount_minor: "", status: "open" });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to record negotiation");
    } finally {
      setBusy(false);
    }
  }

  async function addSettlement(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.recordClaimSettlement(token, claimId, {
        outcome: settlementForm.outcome,
        settled_amount_minor: parseInt(settlementForm.settled_amount_minor, 10),
        notes: settlementForm.notes,
      });
      setSettlementForm({ outcome: "", settled_amount_minor: "", notes: "" });
      onRefresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to record settlement");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      {settlement && (
        <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">
          <p className="font-medium">Settlement recorded</p>
          <p>{settlement.outcome} · {formatMinor(settlement.settled_amount_minor, settlement.currency)}</p>
          {settlement.notes && <p className="text-xs">{settlement.notes}</p>}
        </div>
      )}

      {responses.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h5 className="text-sm font-semibold text-ink">Responses</h5>
          <ul className="mt-2 space-y-2 text-sm">
            {responses.map((r) => (
              <li key={r.id} className="flex items-center justify-between">
                <span>{r.response_kind.replace(/_/g, " ")} from {r.responder}</span>
                <span className="text-xs text-slate-400">{new Date(r.received_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {negotiations.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h5 className="text-sm font-semibold text-ink">Negotiations</h5>
          <ul className="mt-2 space-y-2 text-sm">
            {negotiations.map((n) => (
              <li key={n.id} className="flex items-center justify-between">
                <span>Round {n.round}: offered {formatMinor(n.offered_amount_minor, "INR")}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs ${n.status === "accepted" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{n.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={addResponse} className="rounded-xl border border-slate-200 bg-white p-4">
        <h5 className="mb-2 text-sm font-semibold text-ink">Record response</h5>
        <div className="grid gap-3 sm:grid-cols-3">
          <select id="resp-kind" aria-label="Response kind" value={responseForm.response_kind} onChange={(e) => setResponseForm({ ...responseForm, response_kind: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" required>
            <option value="">Kind…</option>
            {RESPONSE_KINDS.map((k) => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
          </select>
          <input id="resp-responder" aria-label="Responder" value={responseForm.responder} onChange={(e) => setResponseForm({ ...responseForm, responder: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Responder" required />
          <input id="resp-received" aria-label="Received at" type="date" value={responseForm.received_at} onChange={(e) => setResponseForm({ ...responseForm, received_at: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" required />
          <input id="resp-due" aria-label="Due at" type="date" value={responseForm.due_at} onChange={(e) => setResponseForm({ ...responseForm, due_at: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Due" />
          <input id="resp-notes" aria-label="Response notes" value={responseForm.notes} onChange={(e) => setResponseForm({ ...responseForm, notes: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm sm:col-span-2" placeholder="Notes" />
        </div>
        <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Add response</button>
      </form>

      <form onSubmit={addNegotiation} className="rounded-xl border border-slate-200 bg-white p-4">
        <h5 className="mb-2 text-sm font-semibold text-ink">Record negotiation</h5>
        <div className="grid gap-3 sm:grid-cols-4">
          <input id="neg-offered" aria-label="Offered amount" type="number" value={negotiationForm.offered_amount_minor} onChange={(e) => setNegotiationForm({ ...negotiationForm, offered_amount_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Offered (minor)" required />
          <input id="neg-counter" aria-label="Counter amount" type="number" value={negotiationForm.counter_amount_minor} onChange={(e) => setNegotiationForm({ ...negotiationForm, counter_amount_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Counter (minor)" />
          <select id="neg-status" aria-label="Negotiation status" value={negotiationForm.status} onChange={(e) => setNegotiationForm({ ...negotiationForm, status: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
            {["open", "accepted", "rejected", "countered"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Record</button>
      </form>

      <form onSubmit={addSettlement} className="rounded-xl border border-slate-200 bg-white p-4">
        <h5 className="mb-2 text-sm font-semibold text-ink">Record settlement</h5>
        <div className="grid gap-3 sm:grid-cols-3">
          <input id="settle-outcome" aria-label="Settlement outcome" value={settlementForm.outcome} onChange={(e) => setSettlementForm({ ...settlementForm, outcome: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Outcome" required />
          <input id="settle-amount" aria-label="Settled amount" type="number" value={settlementForm.settled_amount_minor} onChange={(e) => setSettlementForm({ ...settlementForm, settled_amount_minor: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Settled amount (minor)" required />
          <input id="settle-notes" aria-label="Settlement notes" value={settlementForm.notes} onChange={(e) => setSettlementForm({ ...settlementForm, notes: e.target.value })} className="rounded-md border border-slate-300 px-2 py-1 text-sm" placeholder="Notes" />
        </div>
        <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Record settlement</button>
      </form>
    </div>
  );
}

function DraftsPanel({ drafts, onGenerate }: { drafts: ClaimDraft[]; onGenerate: (kind: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {DRAFT_KINDS.map((kind) => (
          <button
            key={kind}
            onClick={() => onGenerate(kind)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Generate {kind.replace(/_/g, " ")}
          </button>
        ))}
      </div>
      {drafts.length === 0 ? (
        <p className="text-sm text-slate-500">No drafts yet.</p>
      ) : (
        <ul className="space-y-2">
          {drafts.map((d) => (
            <li key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink capitalize">{d.draft_kind.replace(/_/g, " ")}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">v{d.version} · {d.status}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
