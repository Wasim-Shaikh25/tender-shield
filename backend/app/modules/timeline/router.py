from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.timeline.service import TimelineService

router = APIRouter()


def _service(request: Request, session: Session) -> TimelineService:
    reg = request.app.state.ctx.registry
    return TimelineService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
    )


def _event_json(e) -> dict:
    return {
        "kind": e.kind,
        "label": e.label,
        "due_at": e.due_at.isoformat() if e.due_at else None,
        "description": e.description,
        "source_page": e.source_page,
        "source_quote": e.source_quote,
        "confirmed": e.confirmed,
        "source": e.source,
    }


@router.get("/opportunities/{opportunity_id}/timeline")
def get_timeline(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    events = _service(request, session).build(principal.org_id, opportunity_id)
    if not events and not _service(request, session)._ingestion():
        raise HTTPException(503, "ingestion_unavailable")
    return {"events": [_event_json(e) for e in events]}


@router.get("/opportunities/{opportunity_id}/timeline.ics", response_class=PlainTextResponse)
def export_ics(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    events = _service(request, session).build(principal.org_id, opportunity_id)
    if not events:
        raise HTTPException(404, "no_timeline_events")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TenderShield//Tender Timeline//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for e in events:
        if e.due_at is None:
            continue
        dt = e.due_at.strftime("%Y%m%dT%H%M%SZ")
        uid = f"{opportunity_id}-{e.kind}@tendershield.local"
        summary = e.label
        desc = e.description
        if e.source_quote:
            desc += f" Source: {e.source_quote[:150]}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART:{dt}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(desc)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return PlainTextResponse("\r\n".join(lines), media_type="text/calendar")


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
