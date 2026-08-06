import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const FEATURES = [
  {
    title: "Deadline wall in < 3 minutes",
    description: "Submission, pre-bid, clarification cut-off and EMD dates — each with a page-level citation and a confirm chip.",
  },
  {
    title: "Risk register with exact citations",
    description: "Payment traps, uncapped LDs, deleted escalation, one-sided termination — quoted verbatim, severity scored by rule, not vibes.",
  },
  {
    title: "Deterministic BOQ assurance",
    description: "Rate×qty errors, carry-forward mismatches, unit chaos and scope gaps — pure arithmetic, never an AI opinion.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-bg-primary via-white to-bg-secondary">
      <div className="mx-auto max-w-5xl px-4 py-12 md:py-20 lg:py-24">
        {/* Hero Section */}
        <div className="space-y-12">
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="inline-block">
                <Badge variant="info">
                  India-first · CPWD / NHAI / state PWD
                </Badge>
              </div>

              <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-text-primary">
                Catch the trap
                <br />
                before you bid.
              </h1>

              <p className="text-lg text-text-secondary max-w-2xl leading-relaxed">
                Upload the tender pack. TenderShield surfaces risk clauses, deadline traps and BOQ
                defects with exact citations — then drafts the clarification letter and bid-review pack.
              </p>
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 pt-2">
              <Link href="/login">
                <Button variant="primary" size="lg">
                  Start free tender review
                </Button>
              </Link>
              <Link href="/opportunities">
                <Button variant="outline" size="lg">
                  See the board
                </Button>
              </Link>
            </div>

            <p className="text-sm text-text-muted">
              No card for the free review · Data never used for training
            </p>
          </div>

          {/* How It Works Card */}
          <Card className="max-w-lg">
            <CardContent className="pt-6">
              <h3 className="font-semibold text-text-primary mb-4">How it works</h3>
              <ol className="space-y-3">
                {[
                  "Upload NIT, GCC/SCC, specs, BOQ and addenda.",
                  "Review extracted deadlines, risk findings and BOQ defects.",
                  "Accept or reject each finding, then export the bid-review pack.",
                ].map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-ink text-white text-xs font-semibold">
                      {i + 1}
                    </span>
                    <span className="text-text-secondary">{step}</span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>

        {/* Features Grid */}
        <div className="mt-20 grid gap-6 md:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title} variant="outlined" className="hover:shadow-md transition-shadow">
              <CardContent className="pt-6">
                <h3 className="font-semibold text-text-primary mb-2 text-base">
                  {feature.title}
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {feature.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-20 text-center text-sm text-text-muted border-t border-border-default pt-8">
          <p>Built by the team. For India.</p>
        </div>
      </div>
    </div>
  );
}
