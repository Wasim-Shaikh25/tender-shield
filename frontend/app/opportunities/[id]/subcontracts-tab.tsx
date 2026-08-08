"use client";

import { useEffect, useState } from "react";
import { api, type Subcontract } from "@/lib/api";

const emptySubcontract = {
  subcontractor_name: "",
  reference: "",
  contract_value_minor: "",
  currency: "INR",
  scope: "",
  notice_buffer_days: "7",
  postal_buffer_days: "2",
};

export function SubcontractsTab({ token, opportunityId, isEstimator }: { token: string; opportunityId: string; isEstimator: boolean }) {
  const [subcontracts, setSubcontracts] = useState<Subcontract[]>([]);
  const [selected, setSelected] = useState<Subcontract | null>(null);
  const [form, setForm] = useState(emptySubcontract);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [moduleStatus, setModuleStatus] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ flowdown?: { matched: { id: string; title: string }[]; missing: { id: string; title: string }[] }; scope?: { uncovered: { id: string; item_text: string; source_event_id?: string | null }[]; covered: { id: string; item_text: string }[] }; calendar?: { events: { kind: string; due_date: string; buffer_date: string; status: string }[] }; exposure?: { currency: string; total_certified_minor: number; total_paid_minor: number; pending_minor: number; pay_when_paid_exposed_minor: number; age_days_max: number } }>({});
  const [clauseForm, setClauseForm] = useState({ title: "", source_quote: "", present: false, status: "unchecked" });
  const [scopeForm, setScopeForm] = useState({ item_text: "", covered: false, source_event_id: "" });
  const [paymentForm, setPaymentForm] = useState({ kind: "invoice", due_date: "", amount_minor: "", certified_amount_minor: "", currency: "INR", status: "pending" });

  const load = () => {
    api.listSubcontracts(token, opportunityId)
      .then((r) => setSubcontracts(r.subcontracts))
      .catch(() => setSubcontracts([]));
  };

  useEffect(() => {
    load();
    api.getSubcontractStatus(token)
      .then((s) => setModuleStatus(s.status))
      .catch(() => setModuleStatus(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, opportunityId]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEstimator) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      await api.createSubcontract(token, opportunityId, {
        subcontractor_name: form.subcontractor_name,
        reference: form.reference || undefined,
        contract_value_minor: form.contract_value_minor ? Number(form.contract_value_minor) * 100 : undefined,
        currency: form.currency,
        scope: form.scope || undefined,
        notice_buffer_days: Number(form.notice_buffer_days),
        postal_buffer_days: Number(form.postal_buffer_days),
      });
      setForm(emptySubcontract);
      setMessage("Subcontract created.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create subcontract");
    } finally {
      setLoading(false);
    }
  };

  const select = async (s: Subcontract) => {
    setSelected(s);
    setDetail({});
    try {
      const [flowdown, scope, calendar, exposure] = await Promise.all([
        api.flowdownCheck(token, s.id),
        api.scopeGaps(token, s.id),
        api.noticeCalendar(token, s.id),
        api.paymentExposure(token, s.id),
      ]);
      setDetail({ flowdown, scope, calendar, exposure });
    } catch {
      setError("Failed to load subcontract details.");
    }
  };

  const addClause = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !isEstimator) return;
    setLoading(true);
    try {
      await api.addSubcontractClause(token, selected.id, clauseForm);
      setClauseForm({ title: "", source_quote: "", present: false, status: "unchecked" });
      if (selected) select(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add clause");
    } finally {
      setLoading(false);
    }
  };

  const addScope = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !isEstimator) return;
    setLoading(true);
    try {
      await api.addSubcontractScopeItem(token, selected.id, {
        item_text: scopeForm.item_text,
        covered: scopeForm.covered,
        source_event_id: scopeForm.source_event_id || undefined,
      });
      setScopeForm({ item_text: "", covered: false, source_event_id: "" });
      if (selected) select(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add scope item");
    } finally {
      setLoading(false);
    }
  };

  const addPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected || !isEstimator) return;
    setLoading(true);
    try {
      await api.addSubcontractPaymentEvent(token, selected.id, {
        kind: paymentForm.kind,
        due_date: paymentForm.due_date,
        amount_minor: Number(paymentForm.amount_minor) * 100,
        certified_amount_minor: paymentForm.certified_amount_minor ? Number(paymentForm.certified_amount_minor) * 100 : undefined,
        currency: paymentForm.currency,
        status: paymentForm.status,
      });
      setPaymentForm({ ...paymentForm, amount_minor: "", certified_amount_minor: "" });
      if (selected) select(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add payment event");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</div>}
      {moduleStatus && <div className="text-xs text-slate-500">Subcontract module: {moduleStatus}</div>}

      {isEstimator && (
        <form onSubmit={create} className="rounded-xl border border-slate-200 bg-white p-4 grid gap-3 md:grid-cols-2">
          <input placeholder="Subcontractor name" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.subcontractor_name} onChange={(e) => setForm({ ...form, subcontractor_name: e.target.value })} disabled={loading} />
          <input placeholder="Reference" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} disabled={loading} />
          <input type="number" placeholder="Contract value (INR)" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.contract_value_minor} onChange={(e) => setForm({ ...form, contract_value_minor: e.target.value })} disabled={loading} />
          <input placeholder="Currency" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} disabled={loading} />
          <input type="number" placeholder="Notice buffer days" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.notice_buffer_days} onChange={(e) => setForm({ ...form, notice_buffer_days: e.target.value })} disabled={loading} />
          <input type="number" placeholder="Postal buffer days" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.postal_buffer_days} onChange={(e) => setForm({ ...form, postal_buffer_days: e.target.value })} disabled={loading} />
          <textarea placeholder="Scope" className="md:col-span-2 rounded-md border border-slate-300 px-3 py-2 text-sm" rows={3} value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} disabled={loading} />
          <button type="submit" disabled={loading} className="md:col-span-2 rounded-md bg-ink px-4 py-2 text-sm text-white w-fit">Create subcontract</button>
        </form>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-ink">Subcontracts</h3>
        {subcontracts.length === 0 ? (
          <p className="text-sm text-slate-500">No subcontracts yet.</p>
        ) : (
          <ul className="space-y-2">
            {subcontracts.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => select(s)}
                  className={`w-full rounded-md border p-3 text-left ${selected?.id === s.id ? "border-indigo-500 bg-indigo-50" : "border-slate-200 bg-slate-50"}`}
                >
                  <p className="font-medium text-ink">{s.subcontractor_name}</p>
                  <p className="text-sm text-slate-500">{s.reference || "No reference"} · {s.status}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selected && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
          <h3 className="font-semibold text-ink">{selected.subcontractor_name}</h3>

          {detail.exposure && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div className="rounded-md bg-slate-50 p-2"><p className="text-slate-500">Certified</p><p className="font-medium">{detail.exposure.currency} {(detail.exposure.total_certified_minor / 100).toLocaleString()}</p></div>
              <div className="rounded-md bg-slate-50 p-2"><p className="text-slate-500">Paid</p><p className="font-medium">{detail.exposure.currency} {(detail.exposure.total_paid_minor / 100).toLocaleString()}</p></div>
              <div className="rounded-md bg-slate-50 p-2"><p className="text-slate-500">Pending</p><p className="font-medium">{detail.exposure.currency} {(detail.exposure.pending_minor / 100).toLocaleString()}</p></div>
              <div className="rounded-md bg-slate-50 p-2"><p className="text-slate-500">Pay-when-paid exposure</p><p className="font-medium">{detail.exposure.currency} {(detail.exposure.pay_when_paid_exposed_minor / 100).toLocaleString()}</p></div>
            </div>
          )}

          {isEstimator && (
            <>
              <form onSubmit={addClause} className="grid gap-2 md:grid-cols-4">
                <input placeholder="Clause title" className="rounded-md border border-slate-300 px-3 py-2 text-sm md:col-span-2" value={clauseForm.title} onChange={(e) => setClauseForm({ ...clauseForm, title: e.target.value })} disabled={loading} />
                <input placeholder="Source quote" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={clauseForm.source_quote} onChange={(e) => setClauseForm({ ...clauseForm, source_quote: e.target.value })} disabled={loading} />
                <button type="submit" disabled={loading} className="rounded-md bg-indigo-600 px-3 py-2 text-sm text-white">Add clause</button>
              </form>

              <form onSubmit={addScope} className="grid gap-2 md:grid-cols-4">
                <input placeholder="Scope item" className="rounded-md border border-slate-300 px-3 py-2 text-sm md:col-span-2" value={scopeForm.item_text} onChange={(e) => setScopeForm({ ...scopeForm, item_text: e.target.value })} disabled={loading} />
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={scopeForm.covered} onChange={(e) => setScopeForm({ ...scopeForm, covered: e.target.checked })} /> Covered</label>
                <button type="submit" disabled={loading} className="rounded-md bg-indigo-600 px-3 py-2 text-sm text-white">Add scope item</button>
              </form>

              <form onSubmit={addPayment} className="grid gap-2 md:grid-cols-6">
                <input placeholder="Kind" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={paymentForm.kind} onChange={(e) => setPaymentForm({ ...paymentForm, kind: e.target.value })} disabled={loading} />
                <input type="date" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={paymentForm.due_date} onChange={(e) => setPaymentForm({ ...paymentForm, due_date: e.target.value })} disabled={loading} />
                <input type="number" placeholder="Amount" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={paymentForm.amount_minor} onChange={(e) => setPaymentForm({ ...paymentForm, amount_minor: e.target.value })} disabled={loading} />
                <input type="number" placeholder="Certified" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={paymentForm.certified_amount_minor} onChange={(e) => setPaymentForm({ ...paymentForm, certified_amount_minor: e.target.value })} disabled={loading} />
                <input placeholder="Status" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={paymentForm.status} onChange={(e) => setPaymentForm({ ...paymentForm, status: e.target.value })} disabled={loading} />
                <button type="submit" disabled={loading} className="rounded-md bg-green-600 px-3 py-2 text-sm text-white">Add payment</button>
              </form>
            </>
          )}

          {detail.flowdown && (
            <div>
              <h4 className="text-sm font-semibold text-slate-700">Flow-down check</h4>
              <p className="text-sm text-slate-500">Matched: {detail.flowdown.matched.length} · Missing: {detail.flowdown.missing.length}</p>
            </div>
          )}

          {detail.scope && (
            <div>
              <h4 className="text-sm font-semibold text-slate-700">Scope gaps ({detail.scope.uncovered.length} uncovered)</h4>
              <ul className="mt-1 space-y-1">
                {detail.scope.uncovered.map((u) => (
                  <li key={u.id} className="text-sm text-red-700">{u.item_text}</li>
                ))}
                {detail.scope.covered.map((c) => (
                  <li key={c.id} className="text-sm text-green-700">{c.item_text}</li>
                ))}
              </ul>
            </div>
          )}

          {detail.calendar && (
            <div>
              <h4 className="text-sm font-semibold text-slate-700">Notice calendar</h4>
              <ul className="mt-1 space-y-1">
                {detail.calendar.events.map((e, i) => (
                  <li key={i} className="text-sm text-slate-600">{e.kind} · due {new Date(e.due_date).toLocaleDateString()} · buffer {new Date(e.buffer_date).toLocaleDateString()} · {e.status}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
