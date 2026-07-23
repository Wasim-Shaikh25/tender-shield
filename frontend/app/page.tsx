import Link from "next/link";

const FEATURES = [
  {
    title: "Deadline wall in < 3 minutes",
    body: "Submission, pre-bid, clarification cut-off and EMD dates — each with a page-level citation and a confirm chip.",
  },
  {
    title: "Risk register with exact citations",
    body: "Payment traps, uncapped LDs, deleted escalation, one-sided termination — quoted verbatim, severity scored by rule, not vibes.",
  },
  {
    title: "Deterministic BOQ assurance",
    body: "Rate×qty errors, carry-forward mismatches, unit chaos and scope gaps — pure arithmetic, never an AI opinion.",
  },
];

export default function Landing() {
  return (
    <div className="space-y-16">
      <section className="grid gap-8 pt-6 md:grid-cols-2 md:items-center">
        <div className="space-y-6">
          <span className="inline-block rounded-full bg-ink/5 px-3 py-1 text-xs font-semibold text-ink">
            India-first · CPWD / NHAI / state PWD
          </span>
          <h1 className="text-4xl font-bold leading-tight text-ink md:text-5xl">
            Catch the trap before you bid.
          </h1>
          <p className="max-w-md text-lg text-slate-600">
            Upload the tender pack. TenderShield surfaces risk clauses, deadline traps and BOQ
            defects with exact citations — then drafts the clarification letter and bid-review pack.
          </p>
          <div className="flex gap-3">
            <Link href="/login" className="rounded-md bg-ink px-5 py-2.5 font-medium text-white hover:opacity-90">
              Start free tender review
            </Link>
            <Link href="/opportunities" className="rounded-md border border-slate-300 px-5 py-2.5 font-medium text-slate-700 hover:bg-white">
              See the board
            </Link>
          </div>
          <p className="text-xs text-slate-500">
            No card for the free review · Data never used for training · Hosted in India (ap-south-1)
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-700">Metro Depot — CPWD</span>
            <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-semibold text-red-700">2d to submission</span>
          </div>
          <ul className="space-y-3 text-sm">
            <li className="flex items-start gap-2">
              <span className="rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">critical</span>
              <span className="text-slate-700">LD @ 1%/week with <b>no cap</b> — GCC 33, p4</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">critical</span>
              <span className="text-slate-700">Escalation <b>barred</b> on a 30-month work — SCC 14, p2</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="rounded bg-orange-500 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">high</span>
              <span className="text-slate-700">No dewatering item despite basement excavation</span>
            </li>
          </ul>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-6">
            <h3 className="mb-2 font-semibold text-ink">{f.title}</h3>
            <p className="text-sm text-slate-600">{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
