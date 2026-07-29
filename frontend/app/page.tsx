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
            No card for the free review · Data never used for training
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">How it works</h3>
          <ol className="list-inside list-decimal space-y-2 text-sm text-slate-600">
            <li>Upload NIT, GCC/SCC, specs, BOQ and addenda.</li>
            <li>Review extracted deadlines, risk findings and BOQ defects.</li>
            <li>Accept or reject each finding, then export the bid-review pack.</li>
          </ol>
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
