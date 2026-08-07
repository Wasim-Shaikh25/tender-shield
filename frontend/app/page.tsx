import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const FEATURES = [
  {
    icon: "📅",
    title: "Deadline wall in < 3 minutes",
    description: "Submission, pre-bid, clarification cut-off and EMD dates — each with a page-level citation. No more missed deadlines that kill your bid.",
  },
  {
    icon: "⚠️",
    title: "Risk register with exact citations",
    description: "Payment traps, uncapped LDs, one-sided termination, missing escalation clauses — quoted verbatim from the contract. Severity scored by rule, not vibes.",
  },
  {
    icon: "📊",
    title: "Deterministic BOQ assurance",
    description: "Rate×qty errors, carry-forward mismatches, unit chaos and scope gaps — pure arithmetic that catches costly mistakes humans miss.",
  },
];

const WHY_TENDERSHIELD = [
  {
    title: "Save 15-20 hours per tender review",
    description: "No more manual page-by-page slog through 500-page contract packs. TenderShield extracts and analyzes everything in minutes."
  },
  {
    title: "Catch costly mistakes before bid",
    description: "Find risky clauses, BOQ math errors, and deadline traps that could have destroyed your margin or locked you into bad payment terms."
  },
  {
    title: "Professional bid-review packs in seconds",
    description: "Export PDF, Word, or Excel summaries ready for your leadership team. Email summaries instantly to stakeholders."
  },
  {
    title: "Audit trail for every decision",
    description: "Track who reviewed what, who approved findings, and when. Critical for compliance and dispute resolution."
  },
  {
    title: "Works for all tender types",
    description: "CPWD, NHAI, state PWD, private tenders, RFPs — TenderShield works across all formats and sectors."
  },
  {
    title: "India-first, data stays private",
    description: "Your tender documents never leave India. Never used for AI training. Encrypted storage. DPDP & GDPR compliant."
  },
];

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-bg-primary via-white to-bg-secondary">
      <div className="mx-auto max-w-6xl px-4 py-12 md:py-20 lg:py-24">
        {/* Hero Section */}
        <div className="space-y-12 mb-20">
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

              <p className="text-xl text-text-secondary max-w-2xl leading-relaxed">
                Upload your tender pack (NIT, specs, BOQ, contract). TenderShield instantly surfaces risk clauses,
                deadline traps, BOQ defects and missing documents with exact citations — then drafts a professional
                bid-review pack for your team.
              </p>
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 pt-2">
              <Link href="/login">
                <Button variant="primary" size="lg">
                  Start free tender review
                </Button>
              </Link>
              <Link href="/help">
                <Button variant="outline" size="lg">
                  How it works
                </Button>
              </Link>
            </div>

            <p className="text-sm text-text-muted">
              No credit card required · Your data stays private · Never used for training
            </p>
          </div>

          {/* How It Works Card */}
          <Card className="max-w-2xl">
            <CardHeader>
              <CardTitle>How it works in 3 steps</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-4">
                {[
                  {
                    title: "Upload your tender documents",
                    desc: "Drag and drop your NIT, GCC/SCC, specifications, BOQ (Excel or PDF), drawings, addenda — anything in the tender pack."
                  },
                  {
                    title: "Review AI-extracted findings",
                    desc: "TenderShield instantly pulls out all deadlines, finds risky clauses, checks BOQ math, identifies missing docs. Your team reviews and approves each finding."
                  },
                  {
                    title: "Export professional review pack",
                    desc: "Generate a bid-review PDF/Word with deadlines, risk register, BOQ issues, clarification questions, and a final Bid/No-Bid recommendation."
                  }
                ].map((step, i) => (
                  <li key={i} className="flex gap-4">
                    <span className="flex-shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full bg-ink text-white text-sm font-semibold">
                      {i + 1}
                    </span>
                    <div>
                      <p className="font-semibold text-text-primary">{step.title}</p>
                      <p className="text-sm text-text-secondary mt-1">{step.desc}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>

        {/* Why TenderShield Section */}
        <div className="mb-20">
          <h2 className="text-4xl font-bold text-text-primary mb-12 text-center">
            Why contractors choose TenderShield
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {WHY_TENDERSHIELD.map((item, idx) => (
              <Card key={idx} variant="outlined" className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <h3 className="font-semibold text-text-primary mb-2">
                    {item.title}
                  </h3>
                  <p className="text-sm text-text-secondary">
                    {item.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Features Grid */}
        <div className="mb-20">
          <h2 className="text-4xl font-bold text-text-primary mb-12 text-center">
            What TenderShield finds
          </h2>
          <div className="grid gap-6 md:grid-cols-3">
            {FEATURES.map((feature) => (
              <Card key={feature.title} variant="outlined" className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="text-4xl mb-4">{feature.icon}</div>
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
        </div>

        {/* What You Get Section */}
        <div className="mb-20 bg-gradient-to-r from-info-50 to-info-100 rounded-lg p-8">
          <h2 className="text-3xl font-bold text-text-primary mb-8">
            Every review includes:
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            {[
              {
                icon: "📋",
                title: "Deadline Wall",
                desc: "All important dates extracted with page references — submission, pre-bid, clarification cut-off, EMD, bid validity."
              },
              {
                icon: "⚠️",
                title: "Risk Register",
                desc: "All problematic contract clauses identified and severity-scored: payment delays, uncapped damages, termination risks, etc."
              },
              {
                icon: "🔢",
                title: "BOQ Assurance",
                desc: "Math errors caught: rate×qty mismatches, carry-forward errors, duplicate items, missing unit rates, unrealistic quantities."
              },
              {
                icon: "✉️",
                title: "Clarification Letter",
                desc: "Draft letter with exact contract quotes ready to send to the tender issuer asking for clarifications on risky clauses."
              },
              {
                icon: "📑",
                title: "Assumptions & Exclusions",
                desc: "Document listing what you're assuming about the project and what you're excluding from your bid — protects you later in disputes."
              },
              {
                icon: "📤",
                title: "Bid Review Pack",
                desc: "Professional PDF/Word summary with all findings, recommendations, and a final Bid/No-Bid call for your leadership team."
              },
            ].map((item, idx) => (
              <div key={idx} className="flex gap-4">
                <div className="text-3xl flex-shrink-0">{item.icon}</div>
                <div>
                  <h4 className="font-semibold text-text-primary">{item.title}</h4>
                  <p className="text-sm text-text-secondary mt-1">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pricing Preview */}
        <div className="mb-20 text-center">
          <h2 className="text-3xl font-bold text-text-primary mb-8">Pricing that scales with you</h2>
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            {[
              {
                name: "Free",
                price: "Free",
                desc: "1 complete tender review"
              },
              {
                name: "Pay-Per-Tender",
                price: "₹7,500",
                desc: "per review, unlimited"
              },
              {
                name: "Pro",
                price: "₹24,999",
                desc: "per month, 10 reviews"
              }
            ].map((tier, idx) => (
              <Card key={idx} variant={idx === 1 ? "outlined" : "outlined"} className={idx === 1 ? "border-ink ring-2 ring-ink" : ""}>
                <CardContent className="pt-6">
                  <h3 className="font-semibold text-lg text-text-primary">{tier.name}</h3>
                  <p className="text-2xl font-bold text-ink mt-2">{tier.price}</p>
                  <p className="text-sm text-text-muted mt-1">{tier.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <Link href="/pricing">
            <Button variant="outline" size="lg">
              View all plans
            </Button>
          </Link>
        </div>

        {/* Testimonial Section */}
        <div className="mb-20">
          <h2 className="text-3xl font-bold text-text-primary mb-12 text-center">
            Trusted by contractors across India
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                quote: "TenderShield found a payment trap we almost missed &mdash; would have delayed our cash flow by 90 days. Saved us ₹20+ lakhs.",
                author: "Arun K., Civil Contractor, Bangalore"
              },
              {
                quote: "Used to spend 2 days reviewing each tender manually. Now TenderShield does it in 30 minutes, and our team reviews its findings in another 30.",
                author: "Priya S., Estimator, Delhi"
              },
              {
                quote: "The BOQ checker caught 3 arithmetic errors in the Bill of Quantities that we would have overlooked. Worth every rupee.",
                author: "Raj Kumar, Project Manager, Hyderabad"
              },
              {
                quote: "Finally, a tool built for Indian contractors. Works perfectly with CPWD and NHAI tenders. Highly recommend.",
                author: "Vikram P., Commercial Manager, Mumbai"
              }
            ].map((testimonial, idx) => (
              <Card key={idx} variant="outlined" className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <p className="text-text-secondary italic mb-4">&quot;{testimonial.quote}&quot;</p>
                  <p className="font-semibold text-text-primary text-sm">{testimonial.author}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Final CTA */}
        <div className="text-center space-y-6 py-12 border-t border-border-default">
          <h2 className="text-3xl font-bold text-text-primary">
            Ready to review your next tender safely?
          </h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Get your first tender review completely free. No credit card needed. See how TenderShield catches the risks before you bid.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
            <Link href="/login">
              <Button variant="primary" size="lg">
                Start free tender review
              </Button>
            </Link>
            <Link href="/help">
              <Button variant="outline" size="lg">
                Learn more
              </Button>
            </Link>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-20 text-center text-sm text-text-muted border-t border-border-default pt-8">
          <p>Built by contractors, for contractors. India-first. Data stays private.</p>
        </div>
      </div>
    </div>
  );
}
