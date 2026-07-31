"""Per-tender evaluation pipeline (TS-230).

Runs one corpus tender through the same pure functions the real ingestion/risk/
BOQ pipeline uses — `extract_upload`, `extract_pages`, `segment_clauses`,
`run_patterns`, `normalize`/`run_checks` — then grades the result with M1
(`app.evalinvariants`). Nothing here is a re-implementation of the product
pipeline; it is the product pipeline's pure core, called directly.

Deliberately **no per-tender database session.** Tenant isolation is already
exercised for real by `evalinvariants.db_adapter`'s own tests
(`test_db_adapter_is_workspace_scoped`); re-proving it on every one of 1,000
tenders would cost a SQLite session per tender for no new evidence. This
runner's bundles use in-memory ids and skip persistence entirely, which is what
makes a 1,000-tender pass affordable.

BOQ checking is **best-effort and honest about it**: the deterministic engine
requires an exact canonical schema (`src_row, description, unit_raw, qty, rate,
amount`) that real-world procurement spreadsheets essentially never have as-is —
this matches the product's actual current behavior (`boq/router.py`'s
`RunBody.csv` has the same expectation). A harvested spreadsheet that doesn't
match is reported `boq_status="not_applicable"`, never coerced into a fabricated
result.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.costmeter import review_cost_scope
from app.evalcorpus.store import CorpusStore
from app.evalinvariants import DocPage, PipelineBundle, run_m1
from app.evalmetadata import extract_metadata_from_text, score_m2
from app.evalmetamorphic import run_m4
from app.modules.boq.engine import normalize, run_checks
from app.modules.ingestion.doc_text import extract_pages
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.segment import segment_clauses
from app.modules.risk.classifier import NullClassifier
from app.modules.risk.engine import run_patterns

logger = logging.getLogger(__name__)

# Matches specs/eval-at-scale.md §3.1 "every failure is tagged".
FAILURE_REASONS = frozenset(
    {"ocr_failed", "parse_failed", "timeout", "llm_error", "invariant_violation", "unknown_error"}
)


class ClassifiedError(Exception):
    """Raised internally to carry a failure tag through to `TenderResult`."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        assert reason in FAILURE_REASONS, f"unknown failure reason {reason!r}"
        self.reason = reason
        self.detail = detail


@dataclass
class TenderResult:
    ocid: str
    document_set_hash: str = ""
    status: str = "ok"                    # ok | failed
    failure_reason: str | None = None
    error_detail: str | None = None
    m1_ok: bool | None = None
    m1_violation_count: int = 0
    m1_summary: dict[str, Any] = field(default_factory=dict)
    m2_summary: dict[str, Any] = field(default_factory=dict)
    m4_summary: dict[str, Any] = field(default_factory=dict)
    findings_count: int = 0
    boq_status: str = "not_applicable"    # not_applicable | checked
    documents_processed: int = 0
    pages_extracted: int = 0
    token_count: int = 0
    cost_minor: int | None = None
    fully_priced: bool = True
    wall_seconds: float = 0.0
    rulepack_version: str = ""
    model_id: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_tabular(filename: str, data: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(StringIO(data.decode("utf-8", errors="replace")))
    return pd.read_excel(BytesIO(data))


def _try_boq(filename: str, data: bytes, pack) -> list[dict] | None:
    """Returns findings if the document parses as a canonical BOQ, else None.

    None (not an empty list) means "not applicable" — distinguishing "checked,
    zero defects" from "could not be checked" matters for the scorecard.
    """
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        return None
    try:
        df = _read_tabular(filename, data)
        normalized = normalize(df, pack.unit_canon)
    except Exception:
        return None  # expected for the vast majority of harvested spreadsheets
    findings = run_checks(
        normalized,
        tolerance=pack.boq_checks.arithmetic_tolerance,
        outlier_quantile=pack.boq_checks.qty_outlier_quantile,
        outlier_multiplier=pack.boq_checks.qty_outlier_multiplier,
    )
    return [f.model_dump() for f in findings]


def _ordered_documents(
    record: dict,
    *,
    document_order: list[int] | None = None,
    duplicate_first: bool = False,
) -> list[dict]:
    docs = [d for d in (record.get("documents") or []) if d.get("sha256")]
    if duplicate_first and docs:
        docs = [docs[0], *docs]
    if document_order is not None:
        ordered = []
        for idx in document_order:
            if 0 <= idx < len(docs):
                ordered.append(docs[idx])
        return ordered or docs
    return docs


def _pipeline_pass(
    documents: list[dict],
    store: CorpusStore,
    *,
    pack,
    classifier,
    ocr,
) -> tuple[list[DocPage], list[dict], list[dict], str, str]:
    """Extract pages/clauses/findings from a document list. Returns combined text."""
    pages: list[DocPage] = []
    clauses: list[dict] = []
    findings: list[dict] = []
    boq_status = "not_applicable"
    text_parts: list[str] = []

    for doc in documents:
        sha = doc.get("sha256")
        if not sha:
            continue
        data = store.read_blob(sha)
        if data is None:
            continue

        filename = doc.get("title") or doc.get("url") or "document"
        document_ref = doc.get("url") or filename

        try:
            text, _ocr_status = extract_upload(filename, data, ocr=ocr)
        except Exception as exc:
            raise ClassifiedError("parse_failed", f"{filename}: {exc}") from exc
        text_parts.append(text)
        doc_pages = extract_pages(text)
        pages.extend(
            DocPage(document_id=document_ref, page=p.page, text=p.text) for p in doc_pages
        )

        clauses.extend(
            {
                "id": f"{document_ref}:{seg.page_from}:{i}",
                "clause_ref": seg.clause_ref,
                "text": seg.text,
                "page_from": seg.page_from,
            }
            for i, seg in enumerate(segment_clauses(text))
        )

        if boq_status == "not_applicable":
            boq_findings = _try_boq(filename, data, pack)
            if boq_findings is not None:
                findings.extend(boq_findings)
                boq_status = "checked"

    try:
        risk_findings = run_patterns(list(pack.patterns.values()), clauses, classifier, {})
    except Exception as exc:
        reason = "timeout" if "timeout" in type(exc).__name__.lower() else "llm_error"
        raise ClassifiedError(reason, str(exc)) from exc
    findings.extend(f.model_dump() for f in risk_findings)
    return pages, findings, clauses, "\n".join(text_parts), boq_status


def run_tender(
    record: dict,
    store: CorpusStore,
    *,
    pack,
    classifier: Any | None = None,
    model_id: str = "none",
    ocr: Any | None = None,
    settings: Settings | None = None,
    wall_ceiling: float | None = None,
    run_m4_checks: bool = False,
) -> TenderResult:
    """Run the full eval pipeline for one manifest record and grade it with M1.

    Never raises: every failure mode is caught, classified, and returned as
    part of the result — a single bad tender must not abort a 1,000-tender run
    (`specs/eval-at-scale.md` §3.1).
    """
    settings = settings or Settings()
    classifier = classifier or NullClassifier()
    ocid = record.get("ocid", "")
    started = time.monotonic()
    result = TenderResult(
        ocid=ocid,
        document_set_hash=record.get("document_set_hash", ""),
        rulepack_version=pack.meta.version,
        model_id=model_id,
        started_at=datetime.now(UTC).isoformat(),
    )

    try:
        with review_cost_scope(
            opportunity_id=ocid, rulepack_version=pack.meta.version
        ) as cost_scope:
            docs = _ordered_documents(record)
            pages, findings, _clauses, combined_text, boq_status = _pipeline_pass(
                docs, store, pack=pack, classifier=classifier, ocr=ocr
            )
            result.documents_processed = len(docs)
            result.pages_extracted = len(pages)
            result.boq_status = boq_status
            result.findings_count = len(findings)

            extracted = extract_metadata_from_text(combined_text, ocid=ocid)
            result.m2_summary = score_m2(record, extracted).summary()

            bundle = PipelineBundle(
                opportunity_id=ocid,
                workspace_id="eval",
                pages=pages,
                findings=findings,
                token_count=cost_scope.total_tokens,
                token_ceiling=settings.max_tokens_per_review,
                wall_seconds=time.monotonic() - started,
                wall_ceiling=wall_ceiling,
            )
            m1 = run_m1(bundle)
            result.m1_ok = m1.ok
            result.m1_violation_count = len(m1.violations)
            result.m1_summary = m1.summary()
            result.token_count = cost_scope.total_tokens
            result.fully_priced = cost_scope.fully_priced
            result.cost_minor = cost_scope.llm_cost_minor if cost_scope.fully_priced else None

            if not m1.ok:
                result.status = "failed"
                result.failure_reason = "invariant_violation"

            if run_m4_checks and result.status == "ok" and docs:
                variants: dict[str, list[dict]] = {}
                if len(docs) > 1:
                    shuffled_order = list(reversed(range(len(docs))))
                    _, shuffled_findings, _, _, _ = _pipeline_pass(
                        _ordered_documents(record, document_order=shuffled_order),
                        store,
                        pack=pack,
                        classifier=classifier,
                        ocr=ocr,
                    )
                    variants["shuffled"] = shuffled_findings
                _, redundant_findings, _, _, _ = _pipeline_pass(
                    _ordered_documents(record, duplicate_first=True),
                    store,
                    pack=pack,
                    classifier=classifier,
                    ocr=ocr,
                )
                variants["redundant"] = redundant_findings
                result.m4_summary = run_m4(findings, variants).summary()

    except ClassifiedError as exc:
        result.status = "failed"
        result.failure_reason = exc.reason
        result.error_detail = exc.detail
        logger.warning("tender %s failed (%s): %s", ocid, exc.reason, exc.detail)
    except Exception as exc:  # a bug in this pipeline, not in the tender
        result.status = "failed"
        result.failure_reason = "unknown_error"
        result.error_detail = f"{type(exc).__name__}: {exc}"
        logger.exception("tender %s failed with an unclassified error", ocid)
    finally:
        result.wall_seconds = time.monotonic() - started
        result.finished_at = datetime.now(UTC).isoformat()

    return result
