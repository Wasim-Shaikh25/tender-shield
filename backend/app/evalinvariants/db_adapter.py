"""Build a `PipelineBundle` from a live opportunity (TS-226 / for TS-230).

This is the one place in `evalinvariants` that knows about SQLAlchemy models. It
lives outside `app/modules/` (like `evalcorpus`), so it is free to import
`app.modules.ingestion` and `app.modules.findings` directly — those imports would
be a hard cross-module dependency violation from inside a module
(`tests/test_architecture.py`), but this package is evaluation infrastructure,
not a module, and nothing in the request path imports it back.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evalinvariants.bundle import DocPage, PipelineBundle
from app.modules.findings.models import FindingRow
from app.modules.ingestion.models import DocChunk


def _finding_row_to_dict(row: FindingRow) -> dict:
    return {
        "kind": row.kind,
        "category": row.category,
        "severity": row.severity,
        "title": row.title,
        "detail": row.detail,
        "source": row.source,
        "source_page": row.source_page,
        "source_quote": row.source_quote,
        "amount_exposure": row.amount_exposure,
        "explanation": row.explanation,
        "pattern_id": row.pattern_id,
    }


def bundle_from_opportunity(
    session: Session,
    workspace_id: str,
    opportunity_id: str,
    *,
    token_count: int = 0,
    token_ceiling: int = 400_000,
    wall_seconds: float = 0.0,
    pipeline_error: str | None = None,
) -> PipelineBundle:
    """Assemble a bundle from the findings and document chunks already persisted
    for this opportunity. Read-only; every query is workspace-scoped, so a bundle
    can never contain another tenant's data — this is what the tenant-isolation
    test below actually exercises, as opposed to the bundle-internal consistency
    check in `checks.py`."""
    ws = uuid.UUID(str(workspace_id))
    opp = uuid.UUID(str(opportunity_id))

    findings = [
        _finding_row_to_dict(r)
        for r in session.scalars(
            select(FindingRow).where(
                FindingRow.workspace_id == ws, FindingRow.opportunity_id == opp
            )
        )
    ]
    pages = [
        DocPage(document_id=str(c.document_id), page=c.page, text=c.text)
        for c in session.scalars(
            select(DocChunk).where(
                DocChunk.workspace_id == ws, DocChunk.opportunity_id == opp
            )
        )
    ]

    return PipelineBundle(
        opportunity_id=str(opportunity_id),
        workspace_id=str(workspace_id),
        pages=pages,
        findings=findings,
        token_count=token_count,
        token_ceiling=token_ceiling,
        wall_seconds=wall_seconds,
        pipeline_error=pipeline_error,
    )
