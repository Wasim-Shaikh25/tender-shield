# Export Enhancement Specification

**Status**: In Development  
**Task ID**: TS-EXPORT-ENHANCE  
**Phase**: Post-Phase 7 (Business Critical Feature)  
**Priority**: HIGH (customer retention + workflow lock-in)

---

## Executive Summary

Enhance TenderShield's export functionality to become integral to contractor workflows. Current exports (DOCX, XLSX) support basic archival. New exports support collaboration, stakeholder communication, and AI-generated asset distribution.

**Business Impact**: 
- Increases product stickiness (contractors embed exports in deliverables)
- Enables audit trail (proof of risk review → liability protection)
- Creates workflow lock-in (custom formats/integrations)

---

## Current State

### Existing Exports
- ✅ DOCX: Bid review pack document
- ✅ XLSX: Spreadsheet format
- **Issue**: No PDF support, no stakeholder summaries, no dynamic content export

### Opportunities Detail Page
- Generates: Clarification letters, assumptions registers
- Exports to: DOCX, XLSX
- Blocked until: All findings reviewed (gate: export_allowed)

---

## Requirements

### 1. PDF Export (All Pages/Artifacts)

#### 1.1 Bid Review Pack PDF
**Trigger**: Click "Export PDF" button on opportunities detail page  
**Contents**:
- Cover page (opportunity name, date, analysis summary)
- Executive summary (high-risk findings, deadline alerts, BOQ defects)
- Risk findings (categorized: red/amber/green, with quotes and sources)
- Assumptions register (if generated)
- Clarification letter (if generated)
- Metadata (analysis date, analyst name, software version)

**User Story**: "As a contractor, I want to export my risk analysis as a professional PDF so I can email it to my team and archive it with the bid."

**Acceptance Criteria**:
- [ ] PDF renders correctly with all findings
- [ ] Source quotes are included with page citations
- [ ] Professional formatting (branded header, consistent fonts)
- [ ] Paginated correctly (no cut-off text)
- [ ] File downloads as `bid-review-[opportunityId]-[date].pdf`

---

#### 1.2 Dynamic Dashboard PDF Export
**Trigger**: Dashboard/analytics page + "Export PDF" button  
**Contents**:
- Dashboard title + analysis date
- Key metrics (snapshot: total opportunities, high-risk count, avg deadline days)
- Charts/visualizations as images
- Summary of top risks across portfolio
- Recommendation section

**User Story**: "As a manager, I want to export my portfolio dashboard as a PDF so I can share risk overview in status meetings."

**Acceptance Criteria**:
- [ ] All dashboard widgets render as images in PDF
- [ ] Charts are readable (high DPI)
- [ ] Metadata included (date, user, workspace)
- [ ] File downloads as `dashboard-[workspaceId]-[date].pdf`

---

#### 1.3 Knowledge Graph PDF Export
**Trigger**: Knowledge graph/risk network view + "Export PDF" button  
**Contents**:
- Graph visualization as high-res image
- Legend (node types, edge meanings)
- Node details table (risk items, connections, severity)
- Insights summary (clusters, hotspots)

**User Story**: "As an analyst, I want to export the risk network diagram as a PDF so I can present it to stakeholders and document the risk topology."

**Acceptance Criteria**:
- [ ] Graph renders clearly in PDF (SVG→PNG conversion)
- [ ] Node labels readable (auto-sizing if needed)
- [ ] Legend explains all node/edge types
- [ ] Insights bullet points included
- [ ] File downloads as `risk-network-[opportunityId]-[date].pdf`

---

### 2. Email-Ready Summary Export

#### 2.1 One-Click Email Summary
**Trigger**: "Email this to team" button on opportunities detail  
**Flow**:
1. Pre-fill email template with findings summary
2. Attach PDF export
3. Open email client (mailto:) OR show copy-paste template if no email client
4. User adds recipients + customization

**Template Contents**:
```
Subject: Risk Review Complete — [Opportunity Name]

Hi Team,

I've completed the risk analysis for [Opportunity]. Here's the summary:

🔴 HIGH RISK ITEMS: [count]
- [Risk 1]: [brief description] (Page [X])
- [Risk 2]: [brief description] (Page [X])

🟡 WARNINGS: [count]
- [Warning 1]: [brief description]

📅 DEADLINE: [date] ([X] days away)
💰 BOQ ISSUES: [count] identified

RECOMMENDATION: [Accept/Reject/Renegotiate based on severity]

Full analysis attached (PDF). See TenderShield for detailed findings.

---
Analyzed: [date]
By: [user email]
Tool: TenderShield AI Risk Review
```

**User Story**: "As a bid manager, I want to email a risk summary to my team without manually copying findings."

**Acceptance Criteria**:
- [ ] Summary template auto-populates with real data
- [ ] Markdown formatting renders correctly in email
- [ ] PDF attachment included
- [ ] Works in Gmail, Outlook, Apple Mail
- [ ] User can customize before sending

---

### 3. Comparison Export (Version History)

#### 3.1 Before/After Export
**Trigger**: Compare two analysis versions + "Export Comparison" button  
**Contents**:
- Version 1 date | Version 2 date
- Changes identified:
  - New risks in V2
  - Resolved risks (V1 → V2)
  - Risk severity changes (red → amber, etc.)
- Side-by-side finding comparison
- Summary: "3 new risks identified, 2 resolved, 1 escalated"

**Format**: DOCX, XLSX, PDF

**User Story**: "As an analyst, I want to export what changed between my first and second risk review so I can track if the contractor addressed concerns."

**Acceptance Criteria**:
- [ ] Clearly shows new/removed/changed findings
- [ ] Color-coded changes (green=resolved, red=new, yellow=escalated)
- [ ] Side-by-side view readable in all formats
- [ ] File names include both version dates

---

### 4. Stakeholder Report (Executive Summary)

#### 4.1 C-Suite/Executive Summary Export
**Trigger**: "Generate stakeholder report" on opportunities detail  
**Contents**:
- 1-page executive summary (no technical jargon)
- Risk rating (GO / CAUTION / NO-GO)
- Key findings (max 5 bullets, plain English)
- Recommended action (Accept/Renegotiate/Decline)
- Financial impact estimate (if available)
- Next steps

**Format**: PDF (professional single-page layout)

**User Story**: "As a VP of Business Development, I want a one-page risk summary I can share with executives before bid approval."

**Acceptance Criteria**:
- [ ] Fits on 1-2 pages maximum
- [ ] Uses plain language (no technical jargon)
- [ ] Professional branding
- [ ] Recommendation is clear + actionable
- [ ] File downloads as `executive-summary-[opportunityId].pdf`

---

### 5. AI Dashboard/Knowledge Graph Artifacts

#### 5.1 Dynamic Dashboard Export
**When**: AI creates interactive dashboard or portfolio analytics  
**Export Options**:
- PDF (static snapshot)
- SVG (for further editing)
- JSON (raw data + chart config, for importing to other tools)

**Use Case**: Contractor runs "Portfolio Risk Analysis" → AI generates interactive dashboard → exports as PDF for weekly status meeting

**Acceptance Criteria**:
- [ ] Charts render as high-quality images in PDF
- [ ] Metadata (analysis date, filters applied) included
- [ ] JSON export includes raw chart data
- [ ] SVG exports allow further design editing

---

#### 5.2 Knowledge Graph/Risk Network Export
**When**: AI generates risk relationship graph or network visualization  
**Export Options**:
- PDF (rendered graph + legend)
- PNG/SVG (graph image only, for presentations)
- JSON-LD (linked data format, for semantic analysis tools)
- GML (Graph Modeling Language, for network analysis tools)

**Use Case**: Contractor runs "Risk Topology Analysis" → AI builds node-link graph of interconnected risks → exports as PDF + PNG for presentation

**Acceptance Criteria**:
- [ ] Graph visual exports clearly (no overlapping nodes)
- [ ] Legend explains node types (risk, finding, recommendation, etc.)
- [ ] JSON-LD export includes all node/edge metadata
- [ ] GML export compatible with Gephi, Cytoscape
- [ ] File downloads as `risk-network-[opportunityId]-[timestamp].[ext]`

---

## Technical Implementation

### Export Pipeline Architecture

```
Export Request
    ↓
1. Data Fetch (findings, artifacts, metadata)
    ↓
2. Format Selector (PDF / DOCX / XLSX / JSON / SVG / GML)
    ↓
3. Template Engine (render content for format)
    ↓
4. Document Generator (PDF: puppeteer/pdfkit, DOCX: docx, etc.)
    ↓
5. File Response (download / stream)
```

### Libraries Required

| Format | Library | Purpose |
|--------|---------|---------|
| PDF | `pdfkit` or `puppeteer` | Generate PDF from templates |
| DOCX | `docx` | Generate Word documents |
| XLSX | `exceljs` | Generate spreadsheets |
| Email | `nodemailer` or system mailto | Send/draft emails |
| SVG | Native | Render graphs as SVG |
| PNG | `sharp` | Convert charts to PNG for PDFs |
| JSON-LD | Native JSON | Linked data export |
| GML | Custom template | Graph Modeling Language |

### Backend Routes

```typescript
// Existing
POST /api/export/opportunities/{id}?format=docx|xlsx

// New
POST /api/export/opportunities/{id}/pdf
  - Response: PDF file
  
POST /api/export/opportunities/{id}/email-summary
  - Body: { to?: string[], subject?: string, customMessage?: string }
  - Response: { mailto_url: string } (for client-side email)

POST /api/export/opportunities/{id}/comparison
  - Body: { versionId1: string, versionId2: string, format: 'pdf'|'docx'|'xlsx' }
  - Response: File

POST /api/export/opportunities/{id}/stakeholder-report
  - Response: PDF file

POST /api/dashboards/{id}/export
  - Body: { format: 'pdf'|'svg'|'json' }
  - Response: File or JSON

POST /api/knowledge-graphs/{id}/export
  - Body: { format: 'pdf'|'svg'|'png'|'json-ld'|'gml' }
  - Response: File or JSON
```

### Frontend Changes

**Add export buttons to**:
1. Opportunities detail page (new PDF, email, comparison buttons)
2. Dashboard page (PDF, SVG, JSON exports)
3. Knowledge graph page (PDF, SVG, PNG, JSON-LD, GML exports)

**New UI Components**:
- `ExportMenu` dropdown (select format)
- `EmailDialog` (pre-fill + send email)
- `ComparisonSelector` (pick two versions to compare)

---

## Data Requirements

### For PDF/Email Exports
- ✅ Finding data (title, description, severity, source)
- ✅ Source quotes (verbatim text + page number)
- ✅ Risk scores (numeric values for severity)
- ✅ Metadata (analysis date, analyst, opportunity name)
- ⏳ Estimated financial impact (if available)

### For Dynamic Dashboard/Graph Exports
- ✅ Chart definitions (type, data, labels)
- ✅ Graph nodes/edges (IDs, labels, connections)
- ✅ Rendering metadata (colors, layout algorithm)
- ⏳ Timestamp and filter context

---

## Success Metrics

### Adoption
- [ ] Export used by 50%+ of contractors within 3 months
- [ ] Average contractor exports PDF per opportunity

### Retention
- [ ] Contractors who export have 30% higher retention
- [ ] Export feature correlates with contract renewal (+20% upsell)

### Efficiency
- [ ] Email summary reduces manual summary writing by 80%
- [ ] Knowledge graph export shortens analysis handoff by 50%

---

## Out of Scope (Phase 2)

- Custom branding per workspace (logo upload)
- Multi-language exports
- Scheduled email exports (automation)
- Direct Slack/Teams integration
- Print-to-printer optimization

---

## Timeline

**Phase 1 (Immediate)**: PDF + Email Summary + Comparison
- Effort: 40 hours
- Deliverable: 3 new export formats + email integration

**Phase 2 (Optional)**: Stakeholder Report + Dashboard/Graph Exports
- Effort: 30 hours
- Deliverable: Executive summaries + AI artifact export support

**Total**: 70 hours (~2 weeks for 1 engineer)

---

## Acceptance Criteria (Feature Complete)

- [x] Requirements documented (this spec)
- [ ] Backend routes implemented (5 new endpoints)
- [ ] PDF generation working (all formats)
- [ ] Email integration working (mailto + template)
- [ ] Comparison export working (version diff)
- [ ] Dashboard export working (charts → PDF)
- [ ] Knowledge graph export working (graph → PDF/SVG/GML)
- [ ] UI buttons added to all relevant pages
- [ ] Testing: E2E tests for each export format
- [ ] Documentation: User guide for export features
- [ ] Performance: Exports complete < 5 seconds for large analyses

---

## Business Rationale

**Why invest in this?**

1. **Revenue retention**: Contractors who export are stickier
2. **Workflow integration**: Your tool becomes part of bid deliverables
3. **Competitive advantage**: Competitors focus on analysis, you focus on workflows
4. **Upsell potential**: "Custom dashboard exports" → premium tier
5. **Data collection**: Export usage tells you what contractors care about

**Conservative estimate**: 15% retention lift = $20-30K ARR at 100 customers
