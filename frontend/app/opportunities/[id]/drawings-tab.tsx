"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Drawing, type DrawingBoqLink, type DrawingComparison } from "@/lib/api";

export function DrawingsTab({
  token,
  opportunityId,
}: {
  token: string;
  opportunityId: string;
}) {
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [compareResult, setCompareResult] = useState<DrawingComparison | null>(null);
  const [selected, setSelected] = useState<Drawing | null>(null);
  const [symbolResult, setSymbolResult] = useState<Record<string, unknown> | null>(null);
  const [heatmap, setHeatmap] = useState<Record<string, unknown> | null>(null);
  const [boqLinks, setBoqLinks] = useState<DrawingBoqLink[]>([]);
  const [form, setForm] = useState({
    filename: "",
    drawing_number: "",
    title: "",
    revision: "",
    revision_date: "",
    discipline: "",
    supersedes_id: "",
  });
  const [linkForm, setLinkForm] = useState({
    page: "",
    region: "",
    source_quote: "",
    item_code: "",
    description: "",
    unit: "",
    qty: "",
    rate_minor: "",
    currency: "INR",
  });
  const [ifcResult, setIfcResult] = useState<{
    boq_candidates: { description: string; classification: string; unit: string; quantity: number; count: number; confidence: string; verify_manually: boolean }[];
    activity_candidates: { source_native_id: string; name: string; classification: string }[];
    element_count: number;
    note?: string;
  } | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await api.listDrawings(token, opportunityId);
      setDrawings(d.drawings);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to load drawings");
    }
  }, [token, opportunityId]);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      const body: Record<string, unknown> = { filename: form.filename };
      if (form.drawing_number) body.drawing_number = form.drawing_number;
      if (form.title) body.title = form.title;
      if (form.revision) body.revision = form.revision;
      if (form.revision_date) body.revision_date = form.revision_date;
      if (form.discipline) body.discipline = form.discipline;
      if (form.supersedes_id) body.supersedes_id = form.supersedes_id;
      await api.createDrawing(token, opportunityId, body as Parameters<typeof api.createDrawing>[2]);
      setForm({ filename: "", drawing_number: "", title: "", revision: "", revision_date: "", discipline: "", supersedes_id: "" });
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(drawingId: string, file: File) {
    setBusy(true);
    setNote(null);
    try {
      await api.uploadDrawingFile(token, opportunityId, drawingId, file);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function supersede(currentId: string, previousId: string) {
    setBusy(true);
    setNote(null);
    try {
      await api.supersedeDrawing(token, opportunityId, currentId, previousId);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Supersede failed");
    } finally {
      setBusy(false);
    }
  }

  async function compare(currentId: string, previousId: string) {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.compareDrawings(token, opportunityId, currentId, previousId);
      setCompareResult(r);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Compare failed");
    } finally {
      setBusy(false);
    }
  }

  async function runSymbolAssist(drawingId: string) {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.runSymbolAssist(token, opportunityId, drawingId);
      setSymbolResult(r as Record<string, unknown>);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Symbol assist failed");
    } finally {
      setBusy(false);
    }
  }

  async function runHeatmap(drawingId: string) {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.getDrawingHeatmap(token, opportunityId, drawingId);
      setHeatmap(r as Record<string, unknown>);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Heatmap failed");
    } finally {
      setBusy(false);
    }
  }

  async function loadBoqLinks(drawingId: string) {
    try {
      const r = await api.listDrawingBoqLinks(token, opportunityId, drawingId);
      setBoqLinks(r.links);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "Failed to load BOQ links");
    }
  }

  async function importIfc(drawingId: string, file: File) {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.importIfcQuantities(token, opportunityId, drawingId, file);
      setIfcResult(r);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "IFC import failed");
    } finally {
      setBusy(false);
    }
  }

  async function linkBoq(drawingId: string, e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote(null);
    try {
      await api.linkDrawingBoq(token, opportunityId, drawingId, {
        page: linkForm.page ? parseInt(linkForm.page, 10) : undefined,
        region: linkForm.region || undefined,
        source_quote: linkForm.source_quote || undefined,
        item_code: linkForm.item_code || undefined,
        description: linkForm.description,
        unit: linkForm.unit,
        qty: linkForm.qty ? parseFloat(linkForm.qty) : undefined,
        rate_minor: linkForm.rate_minor ? parseInt(linkForm.rate_minor, 10) : undefined,
        currency: linkForm.currency,
      });
      setLinkForm({ page: "", region: "", source_quote: "", item_code: "", description: "", unit: "", qty: "", rate_minor: "", currency: "INR" });
      await loadBoqLinks(drawingId);
    } catch (err) {
      setNote(err instanceof Error ? err.message : "BOQ link failed");
    } finally {
      setBusy(false);
    }
  }

  function select(d: Drawing) {
    setSelected(d);
    setSymbolResult(null);
    setHeatmap(null);
    setIfcResult(null);
    loadBoqLinks(d.id).catch(() => {});
  }

  const pages = (symbolResult?.pages ?? []) as { page: number; symbols: { symbol: string; count: number; confidence: string; verify_manually: boolean }[] }[];
  const totals = (symbolResult?.totals ?? {}) as Record<string, number>;
  const heatmapPages = (heatmap?.pages ?? []) as { page: number; confidence: number; cannot_determine: boolean; regions: Record<string, { start_line: number; end_line: number; confidence: number }> }[];

  return (
    <div className="space-y-4">
      {note && <p className="rounded bg-rose-50 px-3 py-2 text-sm text-rose-700">{note}</p>}
      <form onSubmit={create} className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold">Add drawing record</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <input required placeholder="Filename" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.filename} onChange={(e) => setForm({ ...form, filename: e.target.value })} />
          <input placeholder="Drawing number" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.drawing_number} onChange={(e) => setForm({ ...form, drawing_number: e.target.value })} />
          <input placeholder="Title" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input placeholder="Revision" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.revision} onChange={(e) => setForm({ ...form, revision: e.target.value })} />
          <input placeholder="Revision date" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.revision_date} onChange={(e) => setForm({ ...form, revision_date: e.target.value })} />
          <input placeholder="Discipline" className="rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.discipline} onChange={(e) => setForm({ ...form, discipline: e.target.value })} />
        </div>
        <button type="submit" disabled={busy} className="mt-3 rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Add drawing</button>
      </form>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold">Drawing register</p>
        <table className="mt-2 w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-700">
            <tr>
              <th className="px-2 py-1">Number</th>
              <th className="px-2 py-1">Title</th>
              <th className="px-2 py-1">Revision</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Upload / Actions</th>
            </tr>
          </thead>
          <tbody>
            {drawings.map((d) => (
              <tr key={d.id} className={`border-b border-slate-100 ${selected?.id === d.id ? "bg-slate-50" : ""}`}>
                <td className="px-2 py-1">{d.drawing_number || "—"}</td>
                <td className="px-2 py-1 cursor-pointer hover:underline" onClick={() => select(d)}>{d.title || d.filename}</td>
                <td className="px-2 py-1">{d.revision || "—"} {d.revision_date ? `(${d.revision_date})` : ""}</td>
                <td className="px-2 py-1"><span className={`rounded px-2 py-0.5 text-xs ${d.status === "current" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{d.status}</span></td>
                <td className="px-2 py-1">
                  <div className="flex flex-wrap gap-2">
                    <label className="cursor-pointer rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200">
                      Upload PDF
                      <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && uploadFile(d.id, e.target.files[0])} />
                    </label>
                    <button className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200" onClick={() => {
                      const prev = window.prompt("Previous drawing ID to supersede");
                      if (prev) supersede(d.id, prev);
                    }}>Supersede</button>
                    <button className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200" onClick={() => {
                      const prev = window.prompt("Previous drawing ID to compare");
                      if (prev) compare(d.id, prev);
                    }}>Compare</button>
                    <button className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200" onClick={() => select(d)}>Select</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">Selected: {selected.title || selected.filename}</p>
            <div className="flex gap-2">
              <button className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium hover:bg-slate-200" disabled={busy} onClick={() => runSymbolAssist(selected.id)}>Symbol assist</button>
              <button className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium hover:bg-slate-200" disabled={busy} onClick={() => runHeatmap(selected.id)}>Heatmap</button>
              <label className="cursor-pointer rounded-md bg-slate-100 px-3 py-1 text-xs font-medium hover:bg-slate-200">
                IFC import
                <input type="file" accept=".ifc" className="hidden" onChange={(e) => e.target.files?.[0] && importIfc(selected.id, e.target.files[0])} />
              </label>
            </div>
          </div>

          {symbolResult && (
            <div>
              <p className="text-sm font-semibold">Symbol suggestions</p>
              <p className="text-xs text-slate-500">{(symbolResult.note as string) || ""}</p>
              {Object.keys(totals).length > 0 && <p className="mt-1 text-xs text-slate-600">Totals: {Object.entries(totals).map(([k, v]) => `${k}: ${v}`).join(", ")}</p>}
              {pages.map((p) => (
                <div key={p.page} className="mt-2 text-xs">
                  <p className="font-medium">Page {p.page}</p>
                  {p.symbols.length === 0 ? <p className="text-slate-500">No symbols detected</p> : (
                    <ul className="list-disc pl-4 text-slate-600">
                      {p.symbols.map((s, i) => <li key={i}>{s.symbol}: {s.count} (confidence {s.confidence})</li>)}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}

          {heatmap && (
            <div>
              <p className="text-sm font-semibold">Confidence heatmap</p>
              <p className="text-xs text-slate-500">{(heatmap.note as string) || ""}</p>
              <p className="text-xs text-slate-600">Overall: {Number(heatmap.overall_confidence).toFixed(2)}</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {heatmapPages.map((p) => (
                  <div key={p.page} className="rounded border border-slate-200 p-2 text-xs">
                    <p className="font-medium">Page {p.page} — {p.cannot_determine ? "cannot determine" : `confidence ${p.confidence}`}</p>
                    <div className="mt-1 flex gap-1">
                      {Object.entries(p.regions).map(([name, r]) => (
                        <div key={name} className="flex-1 rounded p-1 text-center" style={{ background: `rgba(59, 130, 246, ${r.confidence})` }}>
                          <span className="font-medium">{name}</span>
                          <span className="block text-[10px]">{r.confidence}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {ifcResult && (
            <div>
              <p className="text-sm font-semibold">IFC quantities</p>
              <p className="text-xs text-slate-500">{ifcResult.note} Elements: {ifcResult.element_count}</p>
              {ifcResult.boq_candidates.length > 0 && (
                <table className="mt-2 w-full text-sm">
                  <thead className="bg-slate-50 text-left text-slate-700">
                    <tr><th className="px-2 py-1">Description</th><th className="px-2 py-1">Qty</th><th className="px-2 py-1">Unit</th><th className="px-2 py-1">Count</th></tr>
                  </thead>
                  <tbody>
                    {ifcResult.boq_candidates.map((c, i) => (
                      <tr key={i} className="border-b border-slate-100">
                        <td className="px-2 py-1">{c.description}</td>
                        <td className="px-2 py-1">{c.quantity}</td>
                        <td className="px-2 py-1">{c.unit}</td>
                        <td className="px-2 py-1">{c.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <div>
            <p className="text-sm font-semibold">Link BOQ item</p>
            <form onSubmit={(e) => linkBoq(selected.id, e)} className="mt-2 grid gap-2 sm:grid-cols-4">
              <input placeholder="Page" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.page} onChange={(e) => setLinkForm({ ...linkForm, page: e.target.value })} />
              <input placeholder="Region" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.region} onChange={(e) => setLinkForm({ ...linkForm, region: e.target.value })} />
              <input placeholder="Item code" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.item_code} onChange={(e) => setLinkForm({ ...linkForm, item_code: e.target.value })} />
              <input required placeholder="Description" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.description} onChange={(e) => setLinkForm({ ...linkForm, description: e.target.value })} />
              <input required placeholder="Unit" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.unit} onChange={(e) => setLinkForm({ ...linkForm, unit: e.target.value })} />
              <input placeholder="Qty" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.qty} onChange={(e) => setLinkForm({ ...linkForm, qty: e.target.value })} />
              <input placeholder="Rate (minor)" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.rate_minor} onChange={(e) => setLinkForm({ ...linkForm, rate_minor: e.target.value })} />
              <input placeholder="Currency" className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={linkForm.currency} onChange={(e) => setLinkForm({ ...linkForm, currency: e.target.value })} />
              <input placeholder="Source quote" className="rounded-md border border-slate-300 px-2 py-1 text-sm sm:col-span-3" value={linkForm.source_quote} onChange={(e) => setLinkForm({ ...linkForm, source_quote: e.target.value })} />
              <button type="submit" disabled={busy} className="rounded-md bg-ink px-3 py-1 text-sm font-medium text-white disabled:opacity-40">Link</button>
            </form>
            {boqLinks.length > 0 && (
              <table className="mt-3 w-full text-sm">
                <thead className="bg-slate-50 text-left text-slate-700">
                  <tr><th className="px-2 py-1">Item</th><th className="px-2 py-1">Page/Region</th><th className="px-2 py-1">Qty</th><th className="px-2 py-1">Rate</th></tr>
                </thead>
                <tbody>
                  {boqLinks.map((l) => (
                    <tr key={l.id} className="border-b border-slate-100">
                      <td className="px-2 py-1">{l.description} {l.item_code ? `(${l.item_code})` : ""}</td>
                      <td className="px-2 py-1">{l.page ? `p${l.page}` : ""} {l.region || ""}</td>
                      <td className="px-2 py-1">{l.qty ?? "—"} {l.unit}</td>
                      <td className="px-2 py-1">{l.rate_minor ?? "—"} {l.currency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {compareResult && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold">Comparison result</p>
          <p className="text-sm text-slate-600">{compareResult.summary}</p>
          <p className="mt-2 text-xs text-slate-500">Changed pages: {compareResult.changed_pages.join(", ") || "none"}</p>
          {compareResult.changed_regions.length > 0 && (
            <table className="mt-2 w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-700">
                <tr><th className="px-2 py-1">Page</th><th className="px-2 py-1">Region</th><th className="px-2 py-1">Added</th><th className="px-2 py-1">Removed</th></tr>
              </thead>
              <tbody>
                {compareResult.changed_regions.map((r, i) => (
                  <tr key={i} className="border-b border-slate-100"><td className="px-2 py-1">{r.page}</td><td className="px-2 py-1">{r.region}</td><td className="px-2 py-1">{r.lines_added}</td><td className="px-2 py-1">{r.lines_removed}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
