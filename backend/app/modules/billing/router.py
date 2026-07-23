from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.billing.plans import PaywallError
from app.modules.billing.service import BillingService

router = APIRouter()


def _service(request: Request, session: Session) -> BillingService:
    reg = request.app.state.ctx.registry
    return BillingService(session, orgs_factory=reg.get("auth.orgs_factory"))


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
    return _service(request, session).status(principal.org_id)


@router.post("/checkout")
def checkout(
    body: CheckoutBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Creates a provider order/subscription handle for the client SDK.
    Activates NOTHING — only the verified webhook does (Doc §15.1)."""
    # Live Razorpay order creation requires provider keys; without them we return
    # a deterministic handle carrying the notes the webhook will echo back.
    notes = {"org_id": str(principal.org_id), "kind": body.kind}
    if body.opportunity_id:
        notes["opportunity_id"] = body.opportunity_id
    if body.plan:
        notes["plan"] = body.plan
    return {
        "provider": "razorpay",
        "kind": body.kind,
        "notes": notes,
        "note": "activation happens via the signed webhook, never this response",
    }


@router.post("/authorize-review")
def authorize_review(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        grant = _service(request, session).authorize_review(principal.org_id)
    except PaywallError as exc:
        raise HTTPException(402, detail={"code": exc.code, "upsell": exc.upsell}) from exc
    return {
        "kind": grant.kind,
        "watermark": grant.watermark,
        "requires_payment": grant.requires_payment,
    }


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    secret = request.app.state.ctx.settings.razorpay_webhook_secret
    result = _service(request, session).process_razorpay_webhook(raw, sig, secret)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    return result
