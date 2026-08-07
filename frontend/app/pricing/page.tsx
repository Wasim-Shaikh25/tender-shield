"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");

  const plans = [
    {
      name: "Free",
      description: "Get started with one complete review",
      price: 0,
      period: "once",
      features: [
        "1 tender review (full features)",
        "Deadline extraction with citations",
        "Risk register with severity scoring",
        "BOQ checking and error detection",
        "Clarification letter drafting",
        "Review workbench with audit logs",
        "PDF export",
        "Email summaries",
        "1 team member",
      ],
      cta: "Start Free Review",
      ctaLink: "/login",
      highlight: false,
    },
    {
      name: "Pay-Per-Tender",
      description: "Pay only for what you use",
      price: 7500,
      period: "per review",
      features: [
        "All Free tier features",
        "Unlimited tender reviews",
        "Professional bid review pack",
        "Word & Excel exports",
        "Version comparison reports",
        "Up to 3 team members",
        "Priority support",
        "Audit logs & compliance reports",
        "No lock-in contract",
      ],
      cta: "Get Started",
      ctaLink: "/login",
      highlight: false,
    },
    {
      name: "Pro",
      description: "Most popular for growing firms",
      price: billingCycle === "annual" ? 249999 : 24999,
      period: billingCycle === "annual" ? "per year" : "per month",
      annualPrice: 249999,
      features: [
        "All Pay-Per-Tender features",
        "10 reviews per month",
        "Up to 10 team members",
        "Advanced analytics dashboard",
        "Custom rule-pack support",
        "Team workflows & approvals",
        "Bulk upload & batch processing",
        "Dedicated support channel",
        "SLA: 24-hour response time",
      ],
      cta: "Start Free Trial",
      ctaLink: "/login",
      highlight: true,
    },
    {
      name: "Scale",
      description: "For large enterprises",
      price: billingCycle === "annual" ? 749999 : 74999,
      period: billingCycle === "annual" ? "per year" : "per month",
      annualPrice: 749999,
      features: [
        "All Pro features",
        "40 reviews per month",
        "Unlimited team members",
        "REST API access",
        "Custom integrations",
        "White-label options",
        "SSO & advanced security",
        "Dedicated account manager",
        "SLA: 4-hour response time",
        "Custom rule-pack development",
      ],
      cta: "Contact Sales",
      ctaLink: "#contact",
      highlight: false,
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-bg-primary via-white to-bg-secondary">
      <div className="mx-auto max-w-6xl px-4 py-12 md:py-20">
        {/* Header */}
        <div className="text-center space-y-6 mb-16">
          <div className="space-y-4">
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-text-primary">
              Simple, Transparent Pricing
            </h1>
            <p className="text-xl text-text-secondary max-w-2xl mx-auto">
              Choose the plan that fits your bidding frequency. All plans include full access to TenderShield&apos;s core features.
            </p>
          </div>

          {/* Billing Toggle */}
          <div className="flex justify-center gap-4 pt-4">
            <div className="inline-flex rounded-lg border border-border-default p-1">
              <button
                onClick={() => setBillingCycle("monthly")}
                className={`px-6 py-2 rounded font-medium transition-colors ${
                  billingCycle === "monthly"
                    ? "bg-ink text-white"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle("annual")}
                className={`px-6 py-2 rounded font-medium transition-colors ${
                  billingCycle === "annual"
                    ? "bg-ink text-white"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                Annual <span className="text-xs ml-1">(Save 20%)</span>
              </button>
            </div>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {plans.map((plan, idx) => (
            <Card
              key={idx}
              className={`flex flex-col ${
                plan.highlight
                  ? "border-ink ring-2 ring-ink transform scale-105 shadow-lg"
                  : "hover:shadow-md transition-shadow"
              }`}
            >
              {plan.highlight && (
                <div className="bg-ink text-white px-4 py-2 text-center text-sm font-semibold rounded-t">
                  Most Popular
                </div>
              )}
              <CardHeader>
                <CardTitle className="text-2xl">{plan.name}</CardTitle>
                <p className="text-sm text-text-secondary mt-2">{plan.description}</p>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col gap-6">
                <div>
                  <div className="text-4xl font-bold text-text-primary">
                    {plan.price === 0 ? (
                      "Free"
                    ) : (
                      <>
                        ₹{(plan.price / 100).toLocaleString("en-IN")}
                      </>
                    )}
                  </div>
                  <p className="text-sm text-text-muted mt-1">{plan.period}</p>
                  {plan.annualPrice && billingCycle === "annual" && (
                    <p className="text-xs text-success mt-2">
                      Save ₹{((plan.annualPrice * 0.2) / 100).toLocaleString("en-IN")} with annual billing
                    </p>
                  )}
                </div>

                <Link href={plan.ctaLink} className="w-full">
                  <Button
                    variant={plan.highlight ? "primary" : "outline"}
                    size="md"
                    className="w-full"
                  >
                    {plan.cta}
                  </Button>
                </Link>

                <div className="space-y-3">
                  {plan.features.map((feature, fidx) => (
                    <div key={fidx} className="flex gap-3 text-sm">
                      <svg className="w-4 h-4 text-success flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className="text-text-secondary">{feature}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Comparison Table */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary text-center">Detailed Feature Comparison</h2>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-default">
                  <th className="text-left py-4 px-4 font-semibold text-text-primary">Feature</th>
                  <th className="text-center py-4 px-4 font-semibold text-text-primary">Free</th>
                  <th className="text-center py-4 px-4 font-semibold text-text-primary">Pay-Per-Tender</th>
                  <th className="text-center py-4 px-4 font-semibold text-text-primary">Pro</th>
                  <th className="text-center py-4 px-4 font-semibold text-text-primary">Scale</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { feature: "Tender Reviews", free: "1", payper: "Unlimited", pro: "10/month", scale: "40/month" },
                  { feature: "Deadline Extraction", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Risk Detection", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "BOQ Checking", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Letter Drafting", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Review Workbench", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "PDF Export", free: "✓", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Word/Excel Export", free: "—", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Email Summaries", free: "—", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Version Comparison", free: "—", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Team Members", free: "1", payper: "3", pro: "10", scale: "Unlimited" },
                  { feature: "Analytics Dashboard", free: "—", payper: "—", pro: "✓", scale: "✓" },
                  { feature: "API Access", free: "—", payper: "—", pro: "—", scale: "✓" },
                  { feature: "Priority Support", free: "—", payper: "✓", pro: "✓", scale: "✓" },
                  { feature: "Dedicated Support", free: "—", payper: "—", pro: "✓", scale: "✓" },
                  { feature: "SLA Response Time", free: "—", payper: "—", pro: "24 hours", scale: "4 hours" },
                ].map((row, idx) => (
                  <tr key={idx} className={idx % 2 === 0 ? "bg-white" : "bg-bg-secondary"}>
                    <td className="py-3 px-4 font-medium text-text-primary">{row.feature}</td>
                    <td className="text-center py-3 px-4 text-text-secondary">{row.free}</td>
                    <td className="text-center py-3 px-4 text-text-secondary">{row.payper}</td>
                    <td className="text-center py-3 px-4 text-text-secondary">{row.pro}</td>
                    <td className="text-center py-3 px-4 text-text-secondary">{row.scale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary text-center">Billing Questions</h2>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {[
              {
                q: "Can I switch plans anytime?",
                a: "Yes. Upgrade or downgrade your plan at any time. Changes take effect on your next billing cycle."
              },
              {
                q: "Is there a contract lock-in?",
                a: "No lock-in on monthly plans. Annual plans offer a 20% discount and can be canceled after the year ends."
              },
              {
                q: "Do you offer discounts for annual billing?",
                a: "Yes! Annual billing saves you 20% compared to monthly pricing. We also offer volume discounts for enterprise clients."
              },
              {
                q: "What payment methods do you accept?",
                a: "We accept all major credit/debit cards, UPI, net banking, and EMI options (0% interest for eligible purchases)."
              },
              {
                q: "Can I get an invoice for GST compliance?",
                a: "Yes. We provide GST-compliant invoices for all purchases. You can download them from your billing dashboard."
              },
              {
                q: "What happens if I go over my monthly limit?",
                a: "Pro and Scale plans include monthly review allowances. Additional reviews can be purchased at the Pay-Per-Tender rate."
              },
              {
                q: "Is there a free trial?",
                a: "Yes! Start with 1 free tender review. Pro and Scale plans include a 14-day free trial (no card required)."
              },
              {
                q: "How do I contact sales for enterprise pricing?",
                a: "Email us at sales@tendershield.ai or use the contact form. Our team will discuss custom pricing for your needs."
              },
            ].map((faq, idx) => (
              <div key={idx} className="space-y-2">
                <h3 className="font-semibold text-text-primary">{faq.q}</h3>
                <p className="text-sm text-text-secondary">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>

        {/* CTA Section */}
        <div className="text-center space-y-6 py-12 border-t border-border-default">
          <h2 className="text-3xl font-bold text-text-primary">Ready to Reduce Bid Review Time?</h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Start with your first tender review free. No credit card required. Upgrade whenever you&apos;re ready.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
            <Link href="/login">
              <Button variant="primary" size="lg">
                Start Free Tender Review
              </Button>
            </Link>
            <Link href="/help">
              <Button variant="outline" size="lg">
                Learn More
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
