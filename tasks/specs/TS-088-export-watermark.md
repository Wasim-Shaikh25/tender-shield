# TS-088 — Apply the free-tier watermark in all three export renderers

**Status:** done
**Requirement:** [R-004 §B](../../specs/requirements/R-004-paywall-enforcement.md)
**Spec(s) updated:** `specs/modules/export.md`, `specs/modules/billing.md`
**Module(s):** `export`, `billing`
**Severity / Gate:** P0 · Gate 1

## What this builds

Closes the second half of the paywall gap: `Grant(kind="free_review_first",
watermark=True)` was computed but nothing in `export/render.py` ever
consumed it — the free review produced a clean, unwatermarked, fully
sellable Bid Review Pack. Since the product's GTM deliberately makes the
free review *complete* ("crippled trials die in contractor WhatsApp
groups"), the watermark is the only thing separating free from paid output.

## Implementation

```python
# backend/app/modules/billing/service.py
def export_entitlement(self, workspace_id) -> dict:
    """Free plan → watermarked forever, including re-exports of the one free
    review. Any paid plan → clean."""
    workspace = self._workspaces().get(workspace_id)
    return {"watermark": bool(workspace and workspace.plan == "free")}
```

```python
# backend/app/modules/export/service.py
def export(self, workspace_id, opportunity_id, fmt: str) -> tuple[str, str, bytes]:
    ...
    meta = {..., "watermark": self._watermark(workspace_id)}   # server decides, not the client

def _watermark(self, workspace_id) -> bool:
    ent = self._billing_entitlement   # registry capability, may be absent
    return bool(ent(self.s, workspace_id).get("watermark")) if ent else False
```

```python
# backend/app/modules/export/render.py — stamp_line already existed (TS-023);
# this task makes it load-bearing and adds a hard-to-delete visible mark per format
WATERMARK_TEXT = "FREE REVIEW — TenderShield · not for external issue"

def stamp_line(meta: dict) -> str:
    base = f"Prepared with TenderShield · reviewed and approved on {meta.get('date','')} ..."
    return f"{WATERMARK_TEXT} · {base}" if meta.get("watermark") else base

# XLSX: repeated in a frozen header row + page header of every sheet
# DOCX: diagonal WordArt-style watermark in the section header
# PDF: diagonal grey "FREE REVIEW" text on every page via onPage callback
```

Watermark marks the *document*, never the *content* — findings, quotes,
page citations, and severities are identical between free and paid output
(degrading content would violate the quote-verification invariant,
CLAUDE.md §4, and defeat the GTM's "complete free trial" strategy).

## Files touched

- `backend/app/modules/billing/service.py`
- `backend/app/modules/export/{service,render}.py`

## Tests

- `backend/tests/modules/export/test_render.py::test_watermark_all_three_formats`
- `backend/tests/modules/billing/test_service.py::test_export_entitlement`

## Acceptance criteria (R-004 §B, A6, A7)

- [x] A free-plan workspace's export carries a visible watermark in all
      three formats (XLSX, DOCX, PDF), not just the stamp line.
- [x] Findings/quotes/citations are byte-identical between watermarked and
      clean exports of the same review.
- [x] Watermark decision is computed server-side from workspace plan, never
      accepted from client input.

## Commit

Predates commit-granular history (PR #10 bulk import).
