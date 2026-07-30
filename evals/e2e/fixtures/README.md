# End-to-End Test Fixtures

This folder contains raw tender documents used by the scenarios in
`evals/e2e/scenarios.md`. The files are intentionally small so tests run quickly,
but they cover the major formats the ingestion pipeline accepts:
Markdown/TXT, CSV, XLSX, DOCX, and PDF.

## Files

| File | Source | Purpose |
|---|---|---|
| `sample_public_wb_tender.pdf` | World Bank, *Procurement of Works – Sample Bidding Documents* (first 10 pages, public document) | Real-world multi-page PDF with clauses for risk extraction, OCR, and page-citation tests. |
| `sample_nit.md` | Synthetic | Notice Inviting Tender (NIT) used for deadline and basic project-info extraction. |
| `sample_gcc.md` | Synthetic | General Conditions of Contract with payment terms, escalation, liquidated damages, defect liability, and termination-for-convenience clauses for risk pattern tests. |
| `sample_pre_bid_qa.md` | Synthetic | Pre-bid queries and answers for Q&A / assistant tests. |
| `sample_addendum.md` | Synthetic | Tender addendum used for version-comparison and delta tests. |
| `sample_boq.csv` / `sample_boq.xlsx` | Synthetic | Bill of quantities for BOQ arithmetic and scope-gap tests. |
| `sample_tender_pack.docx` / `sample_tender_pack.pdf` | Synthetic | Combined NIT + GCC + SCC in a single Word/PDF document for combined ingestion tests. |

## Regenerating synthetic files

```bash
cd /home/ubuntu/repos/tender-shield/backend
source .venv/bin/activate
python ../evals/e2e/fixtures/generate.py
```

The generator needs `python-docx`, `openpyxl`, and `reportlab` (already in the dev venv).

## Notes

- `sample_public_wb_tender.pdf` is a trimmed, 10-page excerpt from a public World Bank
  sample bidding document and is used only for test/audit purposes.
- The synthetic documents contain deliberately placed risk clauses (payment terms,
  price escalation, liquidated damages, defect liability, termination-for-convenience)
  so the automated risk-review scenarios can assert deterministic findings.
- The `sample_boq.xlsx` includes a second worksheet (`WRONG_TOTAL`) with intentionally
  incorrect totals for BOQ arithmetic-defect tests.
