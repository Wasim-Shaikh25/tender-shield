"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Drawing, type DrawingComparison } from "@/lib/api";

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
  const [form, setForm] = useState({
    filename: "",
    drawing_number: "",
    title: "",
    revision: "",
    revision_date: "",
    discipline: "",
    supersedes_id: "",
  });

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
              <tr key={d.id} className="border-b border-slate-100">
                <td className="px-2 py-1">{d.drawing_number || "—"}</td>
                <td className="px-2 py-1">{d.title || d.filename}</td>
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
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
