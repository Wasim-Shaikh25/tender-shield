import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Help · TenderShield AI",
  description: "How to use TenderShield, what it checks, and what it deliberately does not do.",
};

const STEPS = [
  {
    n: 1,
    title: "Create your workspace",
    body: "Sign up with your firm name, email and a password. Everything you upload lives inside your workspace only — tender packs are never shared across firms and are never used to train models.",
  },
  {
    n: 2,
    title: "Open an opportunity",
    body: "Create one opportunity per tender (e.g. “Metro Depot — CPWD”). The board is your countdown wall: red under 3 days to submission, amber under 7.",
  },
  {
    n: 3,
    title: "Upload the full pack",
    body: "Add the NIT/RFP and — this is where most traps hide — the GCC/SCC, specifications, BOQ and every addendum. Scanned PDFs are read with offline OCR; BOQ tables are pulled from PDF/XLSX/CSV. About 60% of costly clauses live in the conditions, not the notice.",
  },
  {
    n: 4,
    title: "Confirm the deadline wall",
    body: "Submission, pre-bid meeting, clarification cut-off and EMD dates are parsed deterministically, each shown with the exact page and quote. Confirm each chip so you are trusting a checked date, not a guessed one.",
  },
  {
    n: 5,
    title: "Run the risk review",
    body: "The rule engine surfaces payment traps, uncapped liquidated damages, deleted escalation, one-sided termination and more — quoted verbatim with a page citation. Severity is scored by rule, not by opinion.",
  },
  {
    n: 6,
    title: "Run BOQ assurance",
    body: "Rate × quantity errors, grand-total carry-forward mismatches, blank rates, duplicates, unit inconsistencies and quantity outliers are found by pure arithmetic. Numbers here never come from an AI — only from deterministic code.",
  },
  {
    n: 7,
    title: "Review and accept findings",
    body: "Every finding lands in the review workbench for a human to accept, edit or reject. Nothing is treated as fact until you approve it. Actions are written to an append-only audit log.",
  },
  {
    n: 8,
    title: "Generate and export",
    body: "Produce the clarification letter, assumptions register and bid-review pack. Generated text is checked by validators (no invented quotes, no uncited clauses, no invented numbers). Export as DOCX / XLSX / PDF — only after review, and stamped with who approved it.",
  },
];

const COVERAGE: { area: string; state: "now" | "planned" | "never"; note: string }[] = [
  { area: "Pre-bid tender & contract risk review", state: "now", note: "Risk register with verbatim citations and rule-based severity." },
  { area: "Deadline / submission timeline extraction", state: "now", note: "Deterministic date parsing with page-level provenance." },
  { area: "BOQ arithmetic & consistency assurance", state: "now", note: "Rate×qty, totals, blanks, duplicates, unit and outlier checks — no LLM maths." },
  { area: "Scope-gap detection", state: "now", note: "Trade checklists cross-referenced against spec / BOQ (e.g. missing dewatering)." },
  { area: "Bid-decision artifacts", state: "now", note: "Clarification letter, assumptions register, bid-review pack — validated & gated." },
  { area: "Baseline lock & commercial handover pack", state: "planned", note: "Phase 2: freeze the accepted BOQ + contract at award so tender knowledge survives handover." },
  { area: "Change / variation inbox & notice drafts", state: "planned", note: "Phase 3: potential-variation tracking with notice drafts populated from verified facts." },
  { area: "Contractual notice / time-bar engine", state: "planned", note: "Phase 3+: 7/14/28-day windows, FIDIC 20.1 and NEC compensation-event bars." },
  { area: "Cross-tender outcome graph", state: "planned", note: "Phase 3: learn which risks actually materialised across your bids — the data moat." },
  { area: "Cost estimating & rate build-up", state: "never", note: "TenderShield reads and audits the pack; it does not price the job." },
  { area: "Drawing take-off / measurement", state: "never", note: "No CAD/BIM quantity extraction (gated in the doc until text findings are trusted)." },
  { area: "BOQ preparation / bill authoring", state: "never", note: "It audits a BOQ; it does not compile one from drawings." },
  { area: "Interim valuations & payment certificates", state: "never", note: "Post-award payment certification is not TenderShield's job." },
  { area: "BIM / clash detection, live pricing, CPM scheduling, legal opinions", state: "never", note: "Explicitly ruled out in the build doc (§0.2)." },
];

const BADGE = {
  now: { text: "Covered now", cls: "bg-emerald-100 text-emerald-700" },
  planned: { text: "On the roadmap", cls: "bg-amber-100 text-amber-700" },
  never: { text: "Not ours", cls: "bg-slate-200 text-slate-600" },
} as const;

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-14">
      <header className="space-y-3">
        <span className="inline-block rounded-full bg-ink/5 px-3 py-1 text-xs font-semibold text-ink">
          Help &amp; scope
        </span>
        <h1 className="text-3xl font-bold text-ink">How TenderShield works</h1>
        <p className="text-lg text-slate-600">
          TenderShield is a pre-bid commercial-intelligence tool. You upload a tender pack; it
          surfaces risk clauses, deadline traps and BOQ defects with exact citations, then helps you
          draft the bid-decision paperwork. Below is how to use it end to end — and, just as
          importantly, what it does <b>not</b> do.
        </p>
      </header>

      <section className="space-y-6">
        <h2 className="text-xl font-semibold text-ink">Step by step</h2>
        <ol className="space-y-4">
          {STEPS.map((s) => (
            <li key={s.n} className="flex gap-4 rounded-xl border border-slate-200 bg-white p-5">
              <span className="grid h-8 w-8 flex-none place-items-center rounded-full bg-ink text-sm font-bold text-white">
                {s.n}
              </span>
              <div>
                <h3 className="font-semibold text-ink">{s.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-ink">The rules it never breaks</h2>
        <ul className="space-y-2 text-sm text-slate-600">
          <li className="rounded-lg border border-slate-200 bg-white p-4">
            <b className="text-ink">Numbers come from code, not AI.</b> All BOQ arithmetic, date maths
            and severity scoring are deterministic. An AI never invents a figure.
          </li>
          <li className="rounded-lg border border-slate-200 bg-white p-4">
            <b className="text-ink">Every finding is cited.</b> Each carries its source page and a
            verbatim quote, and the quote is verified against the document before it is shown.
          </li>
          <li className="rounded-lg border border-slate-200 bg-white p-4">
            <b className="text-ink">A human approves before export.</b> Nothing leaves as a document
            until you have reviewed it; exports are stamped and the review is logged.
          </li>
          <li className="rounded-lg border border-slate-200 bg-white p-4">
            <b className="text-ink">Your data stays yours.</b> Tender packs are isolated per workspace
            and are never used for training.
          </li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-ink">
          Does it cover the full QS lifecycle?
        </h2>
        <p className="text-sm text-slate-600">
          Not all of it today — and not the parts other software already does well. Quantity
          surveying spans estimating, take-off and pricing, then post-award valuations, variations and
          the final account. TenderShield starts at the <b>pre-bid review</b> — deciding whether and
          how to bid, with the risks and BOQ defects laid bare — then follows the contract forward
          into <b>baseline lock</b> and <b>change / notice management</b> on the roadmap. It is not
          here to replace your estimating or measurement software; it fills the commercial-intelligence
          gap those tools leave open. The table below is honest about what runs today, what is planned,
          and what is deliberately not ours to build.
        </p>
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">QS area</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {COVERAGE.map((row) => {
                const b = BADGE[row.state];
                return (
                  <tr key={row.area} className="bg-white align-top">
                    <td className="px-4 py-3 font-medium text-ink">{row.area}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${b.cls}`}>
                        {b.text}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{row.note}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-ink">Where it goes beyond typical QS tools</h2>
        <p className="text-sm text-slate-600">
          Estimating and measurement packages are strong at quantities and rates. They rarely read
          the contract, and they never track the clock. TenderShield fills that gap:
        </p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {[
            ["Reads the contract, not just the bill", "Surfaces uncapped LDs, deleted escalation and one-sided termination — quoted verbatim with a page citation."],
            ["Tracks the clock", "Deadline wall now; contractual notice / time-bar windows (7/14/28-day, FIDIC 20.1, NEC CE) on the roadmap — the traps that cost crores when missed."],
            ["Compares against your playbook", "Flags where a tender deviates from your firm's standard acceptable terms, not just what the numbers are."],
            ["Learns across tenders", "The cross-tender outcome graph records which flagged risks actually materialised — a data moat no spreadsheet has."],
            ["Every fact is inspectable", "Provenance and a verified verbatim quote on each finding; trust by inspection, not by faith."],
            ["Numbers never come from AI", "All arithmetic and severity scoring is deterministic code — the AI drafts prose, it never invents a figure."],
          ].map(([t, d]) => (
            <li key={t} className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-ink">{t}</h3>
              <p className="mt-1 text-sm text-slate-600">{d}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="font-semibold text-amber-900">A note on judgement</h2>
        <p className="mt-2 text-sm text-amber-800">
          TenderShield helps you read a tender faster and catch what is easy to miss. It is not legal
          advice and not professional QS certification. Findings are prompts for a qualified person to
          review — the accept/reject step exists precisely so a human, not the tool, makes the call.
          Always confirm critical clauses against the original documents before you bid.
        </p>
      </section>

      <section className="flex flex-wrap gap-3">
        <Link
          href="/opportunities"
          className="rounded-md bg-ink px-5 py-2.5 font-medium text-white hover:opacity-90"
        >
          Go to the board
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-slate-300 px-5 py-2.5 font-medium text-slate-700 hover:bg-white"
        >
          Start a free review
        </Link>
      </section>
    </div>
  );
}
