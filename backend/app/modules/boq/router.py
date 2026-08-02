import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.storage import BOQ_MAX_UPLOAD_SIZE, StorageError, ValidationError, validate_and_store
from app.modules.boq.service import BoqRunner

router = APIRouter()


@router.get("")
def boq_status(request: Request) -> dict:
    engine = request.app.state.ctx.registry.get("boq.engine")
    return {
        "engine": "deterministic (zero LLM)",
        "available_checklists": engine.available_checklists() if engine else [],
    }


class RunBody(BaseModel):
    csv: str = Field(..., max_length=10_000_000)


def _runner(request: Request, session: Session) -> BoqRunner:
    reg = request.app.state.ctx.registry
    engine = reg.get("boq.engine")
    if engine is None:
        raise HTTPException(503, "boq_unavailable")
    return BoqRunner(
        session,
        engine=engine,
        store_factory=reg.get("findings.store_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        integrations_factory=reg.get("integrations.service_factory"),
        outcomes_factory=reg.get("outcomes.service_factory"),
    )


@router.post("/opportunities/{opportunity_id}/run")
def run_boq(
    opportunity_id: str,
    body: RunBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        findings = _runner(request, session).run_csv(
            principal.workspace_id, opportunity_id, body.csv
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, f"bad_boq: {exc}") from exc
    return _findings_json(findings)


@router.post("/opportunities/{opportunity_id}/upload")
async def upload_boq(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Upload a BOQ as PDF / XLSX / CSV; tables are read out (pdfplumber for PDF)
    and the deterministic checks run — no AWS."""
    reg = request.app.state.ctx.registry
    to_csv = reg.get("ingestion.file_to_boq_csv")
    if to_csv is None:
        raise HTTPException(503, "ingestion_unavailable")
    data = await file.read(BOQ_MAX_UPLOAD_SIZE + 1)
    if len(data) > BOQ_MAX_UPLOAD_SIZE:
        raise HTTPException(413, "upload_too_large")
    try:
        await validate_and_store(
            request.app.state.ctx.settings,
            file.filename,
            file.content_type,
            data,
            max_size=BOQ_MAX_UPLOAD_SIZE,
            workspace_id=str(principal.workspace_id),
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(500, str(exc)) from exc
    csv_text = await asyncio.to_thread(to_csv, file.filename, data)
    # Digital tables failed on a PDF → fall back to offline scanned-table OCR
    # (rapid-table) if enabled. Still no cloud.
    if not csv_text and file.filename.lower().endswith(".pdf"):
        scanned = reg.get("ingestion.scanned_boq_csv")
        if scanned is not None:
            csv_text = await asyncio.to_thread(scanned, data)
    if not csv_text:
        raise HTTPException(422, "no_boq_table_found")
    try:
        findings = _runner(request, session).run_csv(
            principal.workspace_id, opportunity_id, csv_text
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, f"bad_boq: {exc}") from exc
    return _findings_json(findings)


def _findings_json(findings) -> dict:
    return {
        "count": len(findings),
        "findings": [
            {
                "category": f.category,
                "severity": f.severity.value,
                "kind": f.kind.value,
                "title": f.title,
                "detail": f.detail,
            }
            for f in findings
        ],
    }
