from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.billing.plans import PaywallError
from app.modules.billing.providers.select import select_provider
from app.modules.billing.service import BillingService

router = APIRouter()


def _service(request: Request, session: Session) -> BillingService:
    reg = request.app.state.ctx.registry
    settings = request.app.state.ctx.settings
    return BillingService(
        session,
        workspace_factory=reg.get("auth.workspace_factory"),
        provider_factory=lambda country: select_provider(settings, country),
    )


class CheckoutBody(BaseModel):
    kind: str  # paygo | subscription
    plan: str | None = None
    opportunity_id: str | None = None


@router.get("/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).status(principal.workspace_id)


@router.post("/checkout")
def checkout(
    body: CheckoutBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Creates a real payment_intents row + provider order (Doc §15.1,
    R-005 §B). Activates NOTHING — only the verified webhook does. Plan and
    price are resolved server-side; client input selects which plan, never
    what it costs."""
    if body.kind not in ("paygo", "subscription"):
        raise HTTPException(400, "bad_kind")
    plan = "paygo" if body.kind == "paygo" else (body.plan or "")
    try:
        return _service(request, session).create_checkout(
            principal.workspace_id,
            kind=body.kind,
            plan=plan,
            opportunity_id=body.opportunity_id,
        )
    except PaywallError as exc:
        status_code = 503 if exc.code == "payment_provider_unavailable" else 400
        raise HTTPException(status_code, exc.code) from exc


@router.get("/intents/{intent_id}")
def intent_status(
    intent_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Polled by the client after opening the provider checkout (R-008 §4) —
    the client-side handler activates nothing; this just reports what the
    webhook has (or hasn't) confirmed yet."""
    return _service(request, session).get_intent_status(principal.workspace_id, intent_id)


@router.post("/authorize-review")
def authorize_review(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        grant = _service(request, session).authorize_review(principal.workspace_id)
    except PaywallError as exc:
        raise HTTPException(402, detail={"code": exc.code, "upsell": exc.upsell}) from exc
    return {
        "kind": grant.kind,
        "watermark": grant.watermark,
        "requires_payment": grant.requires_payment,
    }


@router.get("/invoices")
def list_invoices(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount_minor": inv.amount_minor,
                "currency": inv.currency,
                "status": inv.status,
                "provider": inv.provider,
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in _service(request, session).list_invoices(principal.workspace_id)
        ]
    }


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    result = _service(request, session).process_webhook(raw, sig)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    return result
