# TenderShield — Master Roadmap Tracker (Stage 1 → Stage 5)

**Roadmap:** `docs/TenderShield_Roadmap_Stage1_to_5.md`
**Strategy:** `docs/TenderShield_Market_Strategy_2026.md`
**Founding research:** `TenderShield_AI_Architecture_and_Market_Research.pdf` (20 Jul 2026)
**Phase trackers:** `tasks/phase15_tracker.md`, `tasks/phase16_tracker.md`

**Rule: exactly one phase is `in-progress` at any time.** More than one is the scope reflex firing
(Build Doc §12.6). If a second phase needs to start, close or explicitly park the first.

---

## 1. Position at a glance

| Stage (Research Doc p2) | Revenue model | Phase | Tasks | Status |
|---|---|---|---|---|
| 1. Pre-bid assessment | Per-tender fee + team subscription | 0–15 | TS-001 – TS-194 | ✅ done |
| 1. (hardening) | — | **16** | TS-195 – TS-234 | ✅ **done** |
| 2. Baseline lock | Project activation fee | **17** | TS-235 – TS-242 | ✅ **done** |
| **3. Change & notice control** | **Per-project recurring** ★ | **18** | TS-243 – TS-256 | 🔵 **in-progress** |
| 4. Claims workspace | Premium module | 19 | TS-257 – TS-270 | ⚪ todo |
| 5. Portfolio intelligence | Enterprise annual | 20 | TS-271 – TS-280 | ⚪ todo |
| — | Channel + platform | 21 | TS-281 – TS-292 | ⚪ todo |

**Revenue reality check** (Research Doc §10.1 price bands, one mid-market GC, `assumption:` arithmetic):

| Phase | Annual value from one customer | Churn |
|---|---|---|
| Stage 1 (built) | ~₹3 L | High — cancellable monthly |
| **Stage 3 (Phase 18)** | **~₹38 L** (8 projects × ₹40k × 12) | Very low — cannot switch mid-project |

Phase 18 is worth roughly 12× Phase 1 per customer and is far stickier. Everything in Phase 16 exists
to make Phase 18 credible.

---

## 2. Unlock gates

Gates come from the Research Doc's own kill/continue criteria (§12.4). They are **decision points,
not locks** — overriding one is the founder's call, but record it in §6 below so the override is
deliberate and visible.

| Phase | Gate | Source | Met? |
|---|---|---|---|
| 16 | Phase 16 exit gates green (`tasks/phase16_tracker.md`) | Roadmap §4 | ⚠️ partial — code complete; scale gates pending |
| 17 | Phase 16 exit gates green (`tasks/phase16_tracker.md`) | Roadmap §4 | ❌ |
| **18** | **"Two projects use baseline weekly"** | Research Doc §12.4 | ❌ |
| 19 | **"Users capture contemporaneous evidence in the platform"** AND **"Document at least five real events before work completion"** | Research Doc §12.4 | ❌ |
| 20 | Phase 19 in production with ≥1 customer | Roadmap §4 | ❌ |
| 21 | **"Integration marketplaces only after workflow proof"** | Research Doc §10.2, §12.3 | ❌ |
| **All** | **"At least three contractors pay for repeated tender reviews"** | Research Doc §12.4 — the master continue gate | ❌ |

---

## 3. Phase-by-phase task tracker

### Phase 16 — Defensibility, domain-agnosticism, scale validation 🔵

Detail in `tasks/phase16_tracker.md`. Summary:

| Group | Tasks | Theme | Status |
|---|---|---|---|
| 16.A | TS-195 – TS-200 | Employer Behaviour Graph (`marketdata`) | todo (blocked on TS-197 real harvest) |
| 16.B | TS-201 – TS-207 | Pricing intelligence | **done** |
| 16.C | TS-208 – TS-214 | Express pay-per-report lane | todo |
| 16.D | TS-215 – TS-216 | Outcome capture | todo |
| 16.E | TS-217 – TS-219 | Contradictions, correction loop, reproducibility | in-progress (TS-217 **done**) |
| 16.F | TS-220 – TS-222 | Domain-agnostic pack SDK + trade ladder | **done** |
| 16.G | TS-223 | Cost instrumentation | **done** |
| 16.H | TS-224 – TS-233 | Evaluation at scale (1,000+ tenders) | in-progress (TS-224/226/230/231 **done**) |
| **16.I** | **TS-234** | **North-star metric — margin protected** | todo (blocked on TS-215) |

### Phase 17 — Baseline Lock & Handover (Stage 2) 🔵

| ID | Task | Priority | Status | Depends on |
|---|---|---|---|---|
| TS-235 | Spec: baseline completion | P0 | **done** | — |
| TS-236 | Award comparison vs tender assumptions | P0 | **done** | TS-235 |
| TS-237 | Risk → project watchlist | P0 | **done** | TS-235 |
| TS-238 | Notice-rule register (deterministic deadlines) | P0 | **done** | TS-235 |
| TS-239 | Approval matrix / authority limits | P1 | **done** | TS-235 |
| TS-240 | Cost-code model mapped to BOQ + variations | P0 | **done** | TS-235 |
| TS-241 | Commercial handover pack export | P1 | **done** | TS-237, TS-240 |
| TS-242 | Baseline adoption telemetry (measures the P18 gate) | P0 | **done** | TS-236 |

**Phase 17 exit:** two projects with a locked baseline in weekly use; notice rules configured for at
least two contract forms; cost codes mapped end-to-end.

### Phase 18 — Change & Notice Control (Stage 3) ★ ⚪

| ID | Task | Priority | Status | Depends on |
|---|---|---|---|---|
| TS-243 | Spec: `change` module | P0 | **done** | Phase 17 |
| TS-244 | `change` scaffold + migrations | P0 | **done** | TS-243 |
| TS-245 | Baseline diff engine | P0 | todo | TS-244, TS-236 |
| TS-246 | Change-signal ingestion (RFI, SI, minutes, daily reports) | P0 | todo | TS-244 |
| TS-247 | Email ingestion + prompt-injection defenses | P1 | todo | TS-246 |
| TS-248 | Potential-variation inbox | P0 | todo | TS-245, TS-246 |
| TS-249 | Impact linking → BOQ, cost codes, subcontracts | P0 | todo | TS-240, TS-248 |
| TS-250 | Site confirmation workflow | P0 | todo | TS-248 |
| TS-251 | **Deterministic notice-deadline engine** | P0 | todo | TS-238, TS-250 |
| TS-252 | Countdown, escalation, multi-channel alerts | P0 | todo | TS-251 |
| TS-253 | Notice drafting (verified facts + validators + human approval) | P0 | todo | TS-251 |
| TS-254 | Evidence attachment + chain of custody | P0 | todo | TS-250 |
| TS-255 | **Evidence-completeness scoring** | P1 | todo | TS-254 |
| TS-256 | Per-project billing lane | P0 | todo | TS-250 |

**Phase 18 exit:** five real change events documented before work completion on a live project;
notices issued on time via the platform; one customer on per-project billing.

### Phase 19 — Claims & Evidence Workspace (Stage 4) ⚪

| ID | Task | Priority | Status | Depends on |
|---|---|---|---|---|
| TS-257 | Spec: `claims` module | P0 | todo | Phase 18 gate |
| TS-258 | `claims` scaffold + migrations | P0 | todo | TS-257 |
| TS-259 | Chronology builder (every entry cited) | P0 | todo | TS-258 |
| TS-260 | Evidence checklist per claim type | P0 | todo | TS-255 |
| TS-261 | **Quantum workspace (deterministic, zero LLM)** | P0 | todo | TS-240, TS-258 |
| TS-262 | Delay-event register (no autonomous entitlement) | P1 | todo | TS-258 |
| TS-263 | Draft generators: particulars, variation proposal, EOT, claim pack | P0 | todo | TS-259, TS-261 |
| TS-264 | Issue → response → negotiation → settlement tracking | P1 | todo | TS-258 |
| TS-265 | Outcome feedback into the private learning set | P0 | todo | TS-264, TS-215 |
| TS-266 | **Chain-integrity test** (claim → notice → event → obligation → clause) | P0 | todo | TS-263 |
| TS-267 | Conflicts control (opposing parties, same project) | P1 | todo | TS-258 |
| TS-268 | Claim-cycle-time + notice-timeliness metrics | P1 | todo | TS-264 |
| TS-269 | North-star extension: recovered claim value | P0 | todo | TS-234, TS-265 |
| TS-270 | Site evidence capture (mobile, geotagged, offline) | P1 | todo | TS-254 |

**Phase 19 exit:** one claim package assembled end-to-end from platform evidence with an unbroken
chain; recovered value recorded against the north-star metric.

### Phase 20 — Commercial Control Tower (Stage 5) ⚪

| ID | Task | Priority | Status |
|---|---|---|---|
| TS-271 | Spec: `controltower` | P0 | todo |
| TS-272 | Commercial exposure model (deterministic) | P0 | todo |
| TS-273 | Deadline + evidence-health dashboard | P0 | todo |
| TS-274 | Risk-adjusted forecast at completion | P1 | todo |
| TS-275 | Client / consultant response-time analytics | P2 | todo |
| TS-276 | Portfolio clause trends + loss reasons | P1 | todo |
| TS-277 | Executive summaries with drill-down | P1 | todo |
| TS-278 | Payment control (RA bills, certification variance, ageing) | P0 | todo |
| TS-279 | Economics metrics | P1 | todo |
| TS-280 | Customer-outcome metrics | P1 | todo |

### Phase 21 — Integrations, Subcontract & Advisor ⚪

| ID | Task | Priority | Status |
|---|---|---|---|
| TS-281 | Spec: integration adapter framework | P0 | todo |
| TS-282 | SharePoint / OneDrive | P1 | todo |
| TS-283 | Procore | P1 | todo |
| TS-284 | Autodesk Construction Cloud | P2 | todo |
| TS-285 | Oracle Aconex | P2 | todo |
| TS-286 | ERP (Tally / SAP / Dynamics) | P1 | todo |
| TS-287 | Schedule import (P6 / MS Project) | P2 | todo |
| TS-288 | **Subcontract flow-down comparison + scope gaps** | P0 | todo |
| TS-289 | **Back-to-back notice calendar + pay-when-paid flags** | P0 | todo |
| TS-290 | Advisor Edition (multi-client, review queues, usage billing) | P1 | todo |
| TS-291 | White-label branded reports | P2 | todo |
| TS-292 | Public API + e-signature for notice issue | P2 | todo |

---

## 4. The evidence chain — completion tracker

The Research Doc's closing line: *"Your most valuable product is the chain of evidence from original
commercial promise to actual project change."* Track it link by link:

| Link | Task | Status |
|---|---|---|
| Tender clause (extracted, cited) | Phase 1 | ✅ |
| → Baseline obligation | TS-237, TS-238 | ⚪ |
| → Change event | TS-245, TS-248 | ⚪ |
| → Notice | TS-251, TS-253 | ⚪ |
| → Evidence (chain of custody) | TS-254, TS-255 | ⚪ |
| → Claim | TS-263 | ⚪ |
| → Outcome | TS-215, TS-265 | ⚪ |
| **Chain integrity enforced by test** | TS-266 | ⚪ |

---

## 5. Metrics coverage (Research Doc §12.2)

| Category | Instrumented by | Status |
|---|---|---|
| **North star — margin protected** | TS-234, extended by TS-269 | ⚪ |
| Adoption | existing `analytics` + TS-242 | ✅ done |
| Quality | existing `analytics` (TS-057) | 🟡 partial |
| Workflow (time to review, notice timeliness, evidence completeness, claim cycle) | TS-255, TS-268 | ⚪ |
| Economics (conversion, margin, CAC payback, retention, expansion) | TS-223, TS-279 | ⚪ |
| Customer outcome (risks priced, bad bids declined, value certified, hours saved) | TS-280 | ⚪ |

---

## 6. Gate override log

Any decision to start a phase before its gate is met is recorded here — date, gate overridden,
reason, and the risk accepted. An empty table means no gate has been overridden.

| Date | Phase | Gate overridden | Reason | Risk accepted |
|---|---|---|---|---|
| — | — | — | — | — |

---

## 7. Standing rules

- **One phase in flight.** Build Doc §12.6.
- **Numbers never from the LLM.** Notice deadlines (TS-251) and quantum (TS-261) are deterministic
  and asserted LLM-free by test — same rule as BOQ arithmetic.
- **Human approval before anything leaves the building.** Notices and claims require named approval
  (Research Doc §5.3 critical control, §11.1).
- **Every finding, event, notice and claim carries provenance.** The chain in §4 is the product.
- **Evidence is captured contemporaneously or it is not evidence.** Phase 19 depends on Phase 18
  actually being used, not merely shipped.
