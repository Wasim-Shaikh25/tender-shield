"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";

export default function HelpPage() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(0);

  const faqs = [
    {
      question: "What is TenderShield?",
      answer: "TenderShield is an AI-powered tool that helps contractors quickly and safely review tender documents (like NIT, RFP, specifications, Bill of Quantities, and contracts). It automatically finds risky clauses, missed deadlines, and BOQ errors so you don't have to read through hundreds of pages manually. Think of it as a smart assistant that catches the traps before you bid."
    },
    {
      question: "Who should use TenderShield?",
      answer: "Any contractor, civil firm, electrical/HVAC specialist, or construction company that bids on projects. Whether you're a 5-person team or a 100-person firm, TenderShield saves your team hours on every tender review and catches costly mistakes that could have been missed."
    },
    {
      question: "How does it work?",
      answer: "1. Upload your tender documents (PDFs, Excel, or ZIP files) — all your tender details, specifications, bill of quantities, and contract conditions.\n2. TenderShield instantly extracts important dates (bid deadlines, pre-bid meetings, clarification cut-offs) and finds risk clauses.\n3. Your team reviews the findings and approves them.\n4. Export a professional bid-review pack to share with your team before you decide to bid."
    },
    {
      question: "What documents can I upload?",
      answer: "You can upload: NIT (Notice Inviting Tenders), RFP (Request for Proposal), GCC (General Conditions of Contract), SCC (Special Conditions), Specifications, Bill of Quantities (BOQ in Excel or PDF), drawings, addenda, and any other tender-related documents as PDFs or Excel files."
    },
    {
      question: "What does 'Deadline Wall' mean?",
      answer: "The Deadline Wall is a quick summary of all important dates in your tender — submission deadlines, pre-bid meetings, clarification cut-offs, bid validity dates, EMD/security deposit deadlines, and milestone dates. Each date comes with a page reference so you know exactly where it came from. You can confirm each date in one click."
    },
    {
      question: "What is a 'Risk Register'?",
      answer: "A Risk Register is a list of all the risky or problematic clauses found in the tender contract. For example: payment terms that delay payment by 120 days, liquidated damages (fines) that aren't capped, or terms that let the employer cancel work anytime. Each risk shows the exact quote from the contract and rates it by severity (critical, high, medium, or low)."
    },
    {
      question: "What is 'BOQ Assurance'?",
      answer: "BOQ (Bill of Quantities) Assurance checks your Bill of Quantities for errors that humans might miss: rates that don't match quantities, carry-forward math errors, missing unit rates, duplicate items, or quantities that seem way too large or too small. It's pure mathematics — no guessing."
    },
    {
      question: "What happens after I upload documents?",
      answer: "TenderShield instantly (in under 3 minutes): 1) extracts all important deadlines, 2) checks what documents are present/missing, 3) finds risky clauses, and 4) checks the BOQ for errors. You then review each finding, approve or edit it, and export a professional Bid Review Pack."
    },
    {
      question: "Can I modify the findings?",
      answer: "Yes! TenderShield's findings are a starting point. Your experienced team can accept, edit, or reject any finding. Everything is logged so there's a clear audit trail of who reviewed what and when."
    },
    {
      question: "What is the 'Clarification Letter'?",
      answer: "A Clarification Letter is an official document your company can send to the tender issuer asking for clarifications on confusing, contradictory, or risky clauses. TenderShield drafts this letter for you with exact quotes from the contract, saving your team hours of writing."
    },
    {
      question: "What is an 'Assumptions & Exclusions Register'?",
      answer: "This document lists everything your bid is assuming about the project (e.g., 'we assume water is available on site') and everything you're excluding from your bid (e.g., 'we exclude bridge design'). It's crucial for protecting your bid later if disputes arise."
    },
    {
      question: "What is the 'Bid Review Pack'?",
      answer: "The Bid Review Pack is a professional PDF/Word document that summarizes everything: the key deadlines, top risks, BOQ issues, clarification questions, and your recommended bid decision (Bid/No-Bid). It's the document your senior team reviews before sign-off to bid."
    },
    {
      question: "Is my tender data kept private?",
      answer: "Yes. Your tender documents are stored securely and never used to train AI models. Your data stays in India (or your region) and only you and your team can see it. We follow strict data protection rules (DPDP, GDPR)."
    },
    {
      question: "Is there a free version?",
      answer: "Yes! TenderShield includes one completely free tender review (full features — no limitations). After that, you can pay per tender or choose a monthly subscription if you bid frequently."
    },
    {
      question: "How much does TenderShield cost?",
      answer: "Pricing depends on how often you bid: Pay-per-tender (₹7,500), Monthly Pro (₹24,999/month for 10 reviews), or Monthly Scale (₹74,999/month for 40 reviews). See our pricing page for details."
    },
    {
      question: "Can my whole team use it?",
      answer: "Yes! You can invite team members (estimators, commercial managers, project heads) to your workspace. Everyone sees the same tender data, and each review action is logged so you know who approved what."
    },
    {
      question: "Does TenderShield work for international tenders?",
      answer: "TenderShield launched in India. We're working on GCC (Gulf Cooperation Council: UAE, Saudi Arabia, Qatar) tenders and UK tenders. Each region gets its own risk patterns and contract rule-packs."
    },
    {
      question: "Can I export findings?",
      answer: "Yes! Export as PDF (professional review pack), Word (.docx), or Excel (.xlsx). You can also email a summary to your team in seconds — one click opens your email with the summary pre-filled."
    },
    {
      question: "What support is available?",
      answer: "You can reach our support team via email. We also have detailed help docs in the app and a live chat. Enterprise customers get priority support."
    },
    {
      question: "Can TenderShield integrate with my other software?",
      answer: "APIs and integrations with project management tools (Procore, Aconex) are coming in Phase 3. For now, you can upload/download documents and export findings."
    }
  ];

  const features = [
    {
      icon: "📅",
      title: "Deadline Extraction",
      description: "All important dates (submission, pre-bid, clarification cut-off, EMD deadline) extracted in under 3 minutes with page-level citations."
    },
    {
      icon: "⚠️",
      title: "Risk Detection",
      description: "Finds problematic clauses: payment delays, uncapped damages, termination-for-convenience, ground condition risks, and more. Each risk is quoted verbatim from the contract."
    },
    {
      icon: "📊",
      title: "BOQ Checking",
      description: "Arithmetic checks: rate×quantity errors, carry-forward mismatches, unit inconsistencies, duplicate items. Pure math, no guesswork."
    },
    {
      icon: "📝",
      title: "Letter Drafting",
      description: "Automatic clarification-question letter and assumptions register drafted with exact contract quotes."
    },
    {
      icon: "✅",
      title: "Review Workbench",
      description: "Your team accepts/edits/rejects each finding. Every action is logged for audit trail and accountability."
    },
    {
      icon: "📤",
      title: "Professional Exports",
      description: "Export as PDF, Word, or Excel. Email summaries to your team instantly. Share with senior management before bid sign-off."
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-bg-primary via-white to-bg-secondary">
      <div className="mx-auto max-w-5xl px-4 py-12 md:py-20">
        {/* Header */}
        <div className="space-y-6 mb-16">
          <div className="space-y-4">
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-text-primary">
              How to Use TenderShield
            </h1>
            <p className="text-xl text-text-secondary max-w-3xl">
              A complete guide to reviewing tenders safely, spotting risks early, and making better bid decisions.
            </p>
          </div>
        </div>

        {/* Quick Start */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary">Getting Started in 3 Steps</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                step: 1,
                title: "Upload Tender Documents",
                description: "Drag and drop (or select) your NIT, specs, BOQ, and any other tender files. Supports PDF, Excel, and ZIP files."
              },
              {
                step: 2,
                title: "Review Findings",
                description: "TenderShield extracts deadlines, finds risks, and checks the BOQ. Your team reviews each finding and approves or edits it."
              },
              {
                step: 3,
                title: "Export & Share",
                description: "Generate a professional Bid Review Pack (PDF/Word/Excel) and share with your leadership team for final bid decision."
              }
            ].map((item) => (
              <Card key={item.step} variant="outlined">
                <CardContent className="pt-6">
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-ink text-white flex items-center justify-center font-bold">
                      {item.step}
                    </div>
                    <div>
                      <h3 className="font-semibold text-text-primary mb-2">{item.title}</h3>
                      <p className="text-sm text-text-secondary">{item.description}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Features Deep Dive */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary">Key Features</h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, idx) => (
              <Card key={idx} variant="outlined" className="hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="text-3xl mb-3">{feature.icon}</div>
                  <h3 className="font-semibold text-text-primary mb-2">{feature.title}</h3>
                  <p className="text-sm text-text-secondary">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Concepts Explained */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary">Understand Key Concepts</h2>
          
          <div className="space-y-4">
            {[
              {
                term: "Deadline Wall",
                explain: "A clear list of all important dates in your tender. Submission deadline, pre-bid meeting date, clarification cut-off, EMD deadline, bid validity — everything in one place with page references. No more missed deadlines."
              },
              {
                term: "Risk Register",
                explain: "A complete list of risky or unfavorable terms in the contract. Examples: payment terms that delay payments 120+ days, liquidated damages (penalty clauses) without limits, or termination-for-convenience clauses. Each risk shows the exact quote and severity level."
              },
              {
                term: "BOQ (Bill of Quantities)",
                explain: "A detailed breakdown of every item/material/task in a construction project with quantities and rates. Example: 100 cubic meters of concrete at ₹5,000/cum = ₹5,00,000. TenderShield checks for math errors, unit mix-ups, and missing rates."
              },
              {
                term: "BOQ Defects",
                explain: "Errors or inconsistencies found in the Bill of Quantities. Examples: rate doesn't match quantity, carry-forward errors (adding up wrong), items with no rates, unrealistic quantities, or duplicate items."
              },
              {
                term: "Clarification Letter",
                explain: "An official letter to the tender issuer asking for clarifications on confusing or risky clauses. TenderShield drafts this with exact quotes so your questions are clear and professional."
              },
              {
                term: "Assumptions & Exclusions Register",
                explain: "A document listing what you're assuming about the project ('we assume water is available') and what you're NOT including in your bid ('we exclude design'). This protects you later if disputes arise."
              },
              {
                term: "Bid Review Pack",
                explain: "A professional summary document (PDF/Word) with all key findings: deadlines, top risks, BOQ issues, clarifications needed, and a final Bid/No-Bid recommendation. This goes to your senior team for final approval."
              },
              {
                term: "Review Workbench",
                explain: "Your team's workspace to review TenderShield's findings. You can accept findings, edit them, reject them, or add notes. Every action is logged for accountability and audit trails."
              }
            ].map((item, idx) => (
              <Card key={idx} variant="outlined" className="hover:bg-background-secondary transition-colors">
                <CardHeader>
                  <CardTitle className="text-lg">{item.term}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-text-secondary">{item.explain}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* FAQ Section */}
        <div className="mb-16">
          <h2 className="text-3xl font-bold mb-8 text-text-primary">Frequently Asked Questions</h2>
          
          <div className="space-y-3">
            {faqs.map((faq, idx) => (
              <Card
                key={idx}
                variant="outlined"
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => setExpandedFaq(expandedFaq === idx ? null : idx)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-4">
                    <CardTitle className="text-base">{faq.question}</CardTitle>
                    <span className="text-xl text-text-muted flex-shrink-0">
                      {expandedFaq === idx ? "−" : "+"}
                    </span>
                  </div>
                </CardHeader>
                {expandedFaq === idx && (
                  <CardContent className="pt-0 border-t border-border-default">
                    <p className="text-text-secondary whitespace-pre-line">{faq.answer}</p>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </div>

        {/* Data Privacy */}
        <div className="mb-16">
          <Card className="bg-gradient-to-br from-info-50 to-info-100 border-info-200">
            <CardHeader>
              <CardTitle className="text-lg">🔒 Your Data is Private & Safe</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-text-secondary">
              <p>• Your tender documents are NOT used to train AI models</p>
              <p>• Data is stored in encrypted format and only your team can access it</p>
              <p>• Servers are in India (or your region) for data residency compliance</p>
              <p>• We follow strict data protection rules: DPDP (India), GDPR (EU), and regional privacy laws</p>
              <p>• Audit logs track every action: who viewed what, who approved findings, when exports happened</p>
            </CardContent>
          </Card>
        </div>

        {/* CTA Section */}
        <div className="text-center space-y-6 py-12">
          <h2 className="text-3xl font-bold text-text-primary">Ready to Review Your First Tender?</h2>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Get your first tender review completely free. No credit card needed. See how TenderShield catches the risks before you bid.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
            <Link href="/login">
              <Button variant="primary" size="lg">
                Start Your Free Review
              </Button>
            </Link>
            <Link href="/pricing">
              <Button variant="outline" size="lg">
                View Pricing Plans
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
