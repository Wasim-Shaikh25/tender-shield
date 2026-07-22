# Evals — in-works pack (Doc §11.5)

Golden sets that gate every rule-pack and prompt change. CI runs the full eval
on any change under `rulepacks/` or extraction prompts; a >2pt F1 drop on
deadlines or any critical pattern blocks merge.

| Folder | Golden set | Seeded by |
|---|---|---|
| `classification/` | file → expected doc-type label | Phase-0 real tenders |
| `deadlines/` | tender → expected deadline rows (kind, due_at, page, quote) | Phase-0 gold annotations |
| `risk_patterns/<pattern_id>/` | tender → expected findings for that pattern | Week-2 gold answers (§19), then production corrections |
| `boq/` | workbook → expected defects | fixture workbooks + pilot BOQs |
| `drafting/` | accepted findings → acceptable letters | Phase-1 QS-graded outputs |

Case format: one folder per case containing `input/` (document fixture or
reference to it) and `expected.yaml`. Real tender documents are competitively
sensitive — store only with the owner's permission, and never commit documents
from paying customers.

`scorecard.md` here is the Week-2 accuracy scorecard (Doc §19) whose gold
answers become the first entries in `risk_patterns/` and `deadlines/`.
