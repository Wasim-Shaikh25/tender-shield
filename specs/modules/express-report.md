# `express` — Pay-Per-Report (No Subscription) — Spec

**Status:** teaser renderer implemented (TS-210); checkout/activation pending TS-211–TS-214
**Requirement refs:** `docs/TenderShield_Market_Strategy_2026.md` §F.2; Build Doc §7, §15, §11.4
**Task refs:** TS-208 – TS-214

## Purpose

Let a stranger arrive, upload a tender, see a real partial result, pay once, receive the full report,
and leave — with no subscription and minimal account friction.

The existing `paygo` plan still assumes signup → workspace → project → upload; that funnel is built
for a customer. This lane is built for a **visitor**, and visitors are the entire top of funnel that
does not currently exist (there is no `/pricing` page in `frontend/app/`).

## Public interface

**Capabilities published**
- `express.session` — anonymous analysis session lifecycle

**Capabilities consumed (soft)**
- `ingestion.upload`, `risk.analyze`, `boq.run`, `export.render`, `billing.checkout`,
  `notifications.send`

**Events emitted**
- `express.session_created`, `express.teaser_ready`, `express.purchased`, `express.converted`

**API routes** (public, unauthenticated except where noted)
- `POST /api/express/sessions` — create session (email + acknowledgment)
- `POST /api/express/sessions/{token}/documents` — upload
- `GET  /api/express/sessions/{token}/teaser`
- `POST /api/express/sessions/{token}/checkout` — returns provider checkout
- `GET  /api/express/sessions/{token}/report` — full report, **only** after webhook activation
- `POST /api/express/sessions/{token}/claim` — magic-link conversion into a workspace

## Data owned

- `ex_sessions` — token (opaque, high-entropy), email, tier, state, acknowledgment record
  (text version, timestamp, IP), expiry
- `ex_purchases` — provider, order/payment id, amount (minor units) + currency, webhook activation
  timestamp
- `ex_documents` — uploaded documents, `sha256`, retention deadline

Express sessions are backed by an **ephemeral internal workspace** so all existing workspace-scoped
isolation applies unchanged. No new isolation path is introduced.

## Behavior

### Flow
1. **Create session** — email + explicit acknowledgment (below). No password, no workspace.
2. **Upload** — one or many documents; size and rate limits enforced before buffering
   (audit TS-I01 applies).
3. **Teaser** — deliberately generous, because trust is the conversion event:
   - Deadline wall **in full** with citations (cheap to compute, highest perceived value)
   - Missing-document checklist in full
   - Finding **counts** by severity and category
   - BOQ defect **count** and total value affected
   - **Two complete findings** with verbatim quotes and page citations
4. **Checkout** — Razorpay [Payment Link / guest checkout](https://razorpay.com/us/payment-links/)
   for India, Stripe for GCC/UK. No account required.
5. **Activation** — **the verified webhook is the only thing that unlocks a report** (Build Doc §15).
   Client redirects never activate anything.
6. **Delivery** — full report in-app plus emailed PDF.
7. **Claim** — magic link converts the session into a real workspace, carrying documents and findings.

### Tiers (`assumption:` — validate against the first 100 transactions)

| Tier | Contents | Indicative price |
|---|---|---|
| `snapshot` | Single document: deadlines, EMD, eligibility, missing-doc checklist | ₹1,499 |
| `risk` | Full pack: risk register + BOQ defects + contradictions | ₹4,999 |
| `bidpack` | Adds clarification letter + assumptions register | ₹9,999 |

Prices are **server-owned** per currency (audit TS-B01). The client never sends an amount.

### Professional-liability handling — the §11.4 conflict

Build Doc §11.4 gates export on reviewer approval. An Express buyer has no reviewer. The *intent* of
§11.4 is that nobody relies on unreviewed output unknowingly, so:

1. Express exports are a distinct **`unreviewed`** variant, watermarked
   **"INDICATIVE — NOT REVIEWED BY A QUALIFIED PROFESSIONAL"** on every page of every format.
2. An explicit click-through acknowledgment is required **before payment**, and the acknowledgment
   text version, timestamp and IP are recorded in the audit log.
3. **Risk-to-price loadings and cashflow output are excluded from all Express tiers**
   (`specs/modules/pricing-intel.md`) — the highest-liability outputs require a reviewer.
4. The disclaimer appears in the emailed PDF, not only in the web view.
5. The report states plainly that findings are machine-generated and require professional review.

### Anti-abuse

- Rate limits per email, per IP, and per `document_hash`
- Identical `document_hash` does not generate a second free teaser
- Daily teaser cap per IP
- Email verification required before teaser render if the abuse rate exceeds a configured threshold
- Express sessions do **not** consume the org free-tier review allowance, and vice versa

### Retention

Express documents and findings are deleted after a configured window (`assumption:` 90 days) unless
the session is claimed into a workspace. Stated in-product before upload. Tender documents are
competitively sensitive (Build Doc §1.3) — retention is a promise, not a default.

## Acceptance criteria

1. A session can be created, documents uploaded, and a teaser rendered with **no** authentication.
2. The full report is unreachable until a verified webhook marks the purchase active — proven by a
   test that calls the report endpoint after a client redirect but before the webhook.
3. Prices are server-owned; a client-supplied amount is rejected.
4. Every Express export is watermarked `unreviewed` in DOCX, PDF and XLSX.
5. The acknowledgment is recorded with text version, timestamp and IP, and is queryable in the audit log.
6. Pricing-intel outputs never appear in any Express tier — asserted by test.
7. Session tokens are high-entropy, expiring, and not enumerable.
8. An Express session cannot read any other session's or workspace's data.
9. Claiming a session migrates documents and findings into a real workspace without data loss.
10. Express usage does not decrement the free-tier allowance of any org.
11. Retention deletion runs and is verified by test.

## Out of scope

- Recurring billing in this lane (that is Pro/Scale)
- Reviewer workflow inside Express — an Express buyer is by definition unreviewed
- Storing card data (handled entirely by the provider)
- Anonymous access without any email (delivery and receipt require it)
