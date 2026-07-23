import type { Finding } from "@/lib/api";

// Countdown wall colours (Doc §9): red < 3 days, amber < 7, else neutral.
export function CountdownBadge({ due }: { due?: string | null }) {
  if (!due) {
    return (
      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500">
        deadline pending
      </span>
    );
  }
  const days = Math.ceil((new Date(due).getTime() - Date.now()) / 86_400_000);
  const tone =
    days < 3 ? "bg-red-100 text-red-700" : days < 7 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-700";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      {days < 0 ? "overdue" : `${days}d to submission`}
    </span>
  );
}

const SEV: Record<Finding["severity"], string> = {
  critical: "bg-red-600 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-amber-400 text-slate-900",
  low: "bg-slate-300 text-slate-800",
  info: "bg-slate-200 text-slate-700",
};

export function SeverityBadge({ severity }: { severity: Finding["severity"] }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${SEV[severity]}`}>
      {severity}
    </span>
  );
}

// Tri-state provenance label — a design-system component, not copy (Doc §11.4).
const SOURCE: Record<string, { label: string; cls: string }> = {
  extracted_fact: { label: "extracted fact", cls: "bg-sky-100 text-sky-800 border-sky-200" },
  deterministic_check: { label: "deterministic check", cls: "bg-violet-100 text-violet-800 border-violet-200" },
  ai_suggestion: { label: "AI suggestion", cls: "bg-fuchsia-100 text-fuchsia-800 border-fuchsia-200" },
};

export function SourceBadge({ source }: { source: string }) {
  const s = SOURCE[source] ?? SOURCE.ai_suggestion;
  return <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${s.cls}`}>{s.label}</span>;
}
