# Example third-party pack (TS-220)

This is a deliberately minimal, self-contained rule-pack that a QS consultancy
or trade specialist could author, proving the pack SDK's acceptance gate:
**a third party can author and validate a pack end to end**, without touching
TenderShield's own `rulepacks/in-works/` or product tests.

It is not a real pack — it exists purely to be validated and tested. See
`docs/TenderShield_Market_Strategy_2026.md` §D.4 and `specs/modules/rulepacks.md`.

## Validate it

```bash
python scripts/pack_validate.py --pack-dir evals/pack-sdk-example
```

## Run its deterministic tests

```bash
python scripts/pack_test.py --pack-dir evals/pack-sdk-example
```

## What's here

- `pack.yaml` — pack metadata
- `risk_patterns/waterproofing_warranty.yaml` — one minimal, valid risk pattern
- `boq/canonical_schema.yaml` — unit normalization map
- `boq/trade_checklists/waterproofing.yaml` — one trade checklist
- `tests/scope_gaps/basement_waterproofing.yaml` — a deterministic test case
  proving the checklist fires (and does not false-positive) against a sample
  BOQ + spec text, entirely offline, no LLM/API key required
