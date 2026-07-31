"""The M1 evidence bundle (TS-226).

`PipelineBundle` is the minimal shape the M1 invariant checks need: the source
text a tender's findings were extracted from, the findings themselves, any
generated artifacts, and enough run metadata (tokens, wall time, crash state) to
assert budget and no-crash. It is deliberately independent of SQLAlchemy models so
the checks are pure and testable with synthetic fixtures — `db_adapter.py` is the
one place that knows how to build a bundle from a live opportunity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocPage:
    """One page (or spreadsheet sheet) of extracted document text."""

    document_id: str
    page: int
    text: str


@dataclass(frozen=True)
class Artifact:
    """A generated artifact and the facts it was supposed to be grounded in.

    `facts` is whatever `app.modules.drafting.validators.FactTable` needs, or an
    equivalent object exposing `has_quote`/`has_amount` — passed through rather
    than imported here so this package never depends on a module.
    """

    name: str
    prose: str
    facts: Any


@dataclass
class PipelineBundle:
    """Everything M1 needs to grade one tender's pipeline run.

    `findings` are plain dicts (not the pydantic `Finding` model) so a bundle can
    be assembled from ORM rows, pydantic models, or synthetic test fixtures
    without a conversion step. Expected keys mirror `Finding`: `kind`, `category`,
    `severity`, `title`, `detail`, `source`, `source_page`, `source_quote`,
    `amount_exposure`, `explanation`.
    """

    opportunity_id: str
    workspace_id: str
    pages: list[DocPage] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    # BOQ ground truth for the arithmetic-closure check: one dict per row with at
    # least `src_row`, `amount`, `amount_calc`, and the tolerance in force.
    boq_rows: list[dict] = field(default_factory=list)
    boq_tolerance: float = 1.0

    # A second, independent findings list from re-running the deterministic
    # stages on the same input. None means the check is not exercised for this
    # bundle rather than failed — determinism needs an actual rerun to assert.
    rerun_findings: list[dict] | None = None

    # Documents/pages the pipeline could not read, and what it said about them.
    # Graceful degradation requires the second to be non-empty whenever the
    # first is: silence about an unreadable page is the violation, not the
    # unreadability itself (Build Doc §12.4).
    unreadable_pages: set[tuple[str, int]] = field(default_factory=set)
    degradation_notes: list[str] = field(default_factory=list)

    # Budget (Strategy §G.3 — cost must scale with pattern count, not document
    # length; this is the same ceiling costmeter.py enforces at runtime).
    token_count: int = 0
    token_ceiling: int = 400_000
    wall_seconds: float = 0.0
    wall_ceiling: float | None = None

    # None = the pipeline completed. A non-empty string = it failed with a
    # classified, actionable error. An unset bundle with no error is the only
    # "success" state the no-crash check accepts.
    pipeline_error: str | None = None

    def pages_at(self, page: int) -> list[DocPage]:
        return [p for p in self.pages if p.page == page]
