from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.standards.service import (
    OrgCommercialStandardsService,
    OrgStandardsService,
    PolicyBody,
    StandardsError,
)

router = APIRouter()

_ERROR_STATUS = {
    "bad_mode": 400,
    "bad_categories": 422,
    "duplicate_keys": 409,
    "bad_operator": 400,
    "bad_unit": 400,
    "missing_key": 400,
}


def _notice_service(session: Session) -> OrgStandardsService:
    return OrgStandardsService(session)


def _commercial_service(session: Session) -> OrgCommercialStandardsService:
    return OrgCommercialStandardsService(session)


class CategoryBody(BaseModel):
    key: str
    label: str
    typical_days: int | None = None
    expected: bool = False
    keywords: list[str] = []
    note: str | None = None


class NoticeStandardBody(BaseModel):
    mode: str = "prevail"  # prevail | side_by_side
    categories: list[CategoryBody] = []


@router.get("/notice")
def get_notice(
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    std = _notice_service(session).get_notice(principal.org_id)
    return std or {"mode": "prevail", "categories": []}


@router.put("/notice")
def set_notice(
    body: NoticeStandardBody,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _notice_service(session).set_notice(
            principal.org_id,
            mode=body.mode,
            categories=[c.model_dump() for c in body.categories],
            actor=principal.user_id,
        )
    except StandardsError as exc:
        raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.delete("/notice")
def clear_notice(
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    _notice_service(session).clear_notice(principal.org_id)
    return {"cleared": True}


# ---- commercial policy thresholds ----


@router.get("/commercial")
def get_policies(
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {"policies": _commercial_service(session).list_policies(principal.org_id)}


@router.put("/commercial/{key}")
def set_policy(
    key: str,
    body: PolicyBody,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    payload = body.model_dump()
    payload["key"] = key
    try:
        return _commercial_service(session).set_policy(
            principal.org_id, policy=payload, actor=principal.user_id
        )
    except StandardsError as exc:
        raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.delete("/commercial/{key}")
def delete_policy(
    key: str,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    deleted = _commercial_service(session).delete_policy(principal.org_id, key)
    if not deleted:
        raise HTTPException(404, "not_found")
    return {"deleted": True}


@router.post("/opportunities/{opportunity_id}/check")
def check_standards(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Run org commercial standards against all accepted findings and persist
    `standard_violation` findings through the findings store."""
    reg = request.app.state.ctx.registry
    store_factory = reg.get("findings.store_factory")
    if store_factory is None:
        raise HTTPException(503, "findings_unavailable")

    store = store_factory(session)
    findings = store.list(principal.org_id, opportunity_id)
    accepted = [f for f in findings if f.review_status in {"accepted", "edited"}]

    commercial = _commercial_service(session)
    violations = commercial.check_violations(principal.org_id, _rows_to_dicts(accepted))

    from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity

    violation_findings = []
    for v in violations:
        f = v["finding"]
        violation_findings.append(
            Finding(
                kind=FindingKind.STANDARD_VIOLATION,
                category="standard_violation",
                severity=Severity.HIGH,
                title=f"Company standard violated: {v['policy_label']}",
                detail=(
                    f"Extracted value {v['value']} {v['operator']} threshold "
                    f"{v['threshold']} for policy '{v['policy_label']}'."
                ),
                source=FindingSource.DETERMINISTIC_CHECK,
                source_page=f.get("source_page"),
                source_quote=f.get("source_quote"),
                suggested_action=f"Review against company policy {v['policy_key']}.",
                pattern_id=v["policy_key"],
            )
        )

    if violation_findings:
        store.replace_for_producer(
            principal.org_id, opportunity_id, "standards", violation_findings
        )

    return {"violations": violations}


def _rows_to_dicts(rows) -> list[dict]:
    return [
        {
            "kind": r.kind,
            "title": r.title,
            "category": r.category,
            "detail": r.detail,
            "source_quote": r.source_quote,
            "source_page": r.source_page,
            "severity": r.severity,
            "suggested_action": r.suggested_action,
        }
        for r in rows
    ]
