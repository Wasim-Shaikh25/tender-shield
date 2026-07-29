from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.ratelimit import RateLimitDep
from app.modules.billing.plans import PAYGO_PRICE_INR_PAISE, PaywallError
from app.modules.billing.service import BillingService

router = APIRouter()


def _service(request: Request, session: Session) -> BillingService:
    reg = request.app.state.ctx.registry
    return BillingService(session, workspace_factory=reg.get("auth.workspace_factory"))


SUBSCRIPTION_PRICES_INR_PAISE: dict[str, int] = {
    "pro": 4_999_00,
    "scale": 14_999_00,
}


class CheckoutBody(BaseModel):
    provider: str = "razorpay"  # razorpay | stripe
    kind: str  # paygo | subscription
    plan: str | None = None
    opportunity_id: str | None = None
    amount_minor: int | None = None


@router.get("/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).status(principal.workspace_id)


@router.post("/checkout", dependencies=[Depends(RateLimitDep(10, 60))])
def checkout(
    body: CheckoutBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Creates a provider order/subscription handle for the client SDK.
    Activates NOTHING — only the verified webhook does (Doc §15.1)."""
    if body.kind == "paygo":
        amount = body.amount_minor or PAYGO_PRICE_INR_PAISE
    elif body.kind == "subscription":
        amount = body.amount_minor or SUBSCRIPTION_PRICES_INR_PAISE.get(body.plan or "", 0)
        if not amount:
            raise HTTPException(400, "unknown_subscription_plan")
    else:
        raise HTTPException(400, "unknown_checkout_kind")

    notes = {"workspace_id": str(principal.workspace_id), "kind": body.kind}
    if body.opportunity_id:
        notes["opportunity_id"] = body.opportunity_id
    if body.plan:
        notes["plan"] = body.plan

    provider = request.app.state.ctx.registry.get("billing.provider_factory")(body.provider)
    if body.provider == "stripe":
        result = provider.create_session(amount, "INR", notes)
    else:
        result = provider.create_order(amount, "INR", notes)
    result["note"] = "activation happens via the signed webhook, never this response"
    return result


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


@router.post("/webhooks/razorpay", dependencies=[Depends(RateLimitDep(50, 60))])
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    secret = request.app.state.ctx.settings.razorpay_webhook_secret
    result = _service(request, session).process_razorpay_webhook(raw, sig, secret)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    return result
