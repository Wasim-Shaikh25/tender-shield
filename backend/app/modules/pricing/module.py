"""`pricing` module registration (TS-201, spec §Public interface).

Highest-liability module in the product (spec §Guardrails) — this is where
that discipline is enforced structurally: no capability here ever touches an
LLM client, and every route is gated on the review workflow via a soft
dependency, never a hard import."""

from app.core.module import AppContext, ModuleSpec
from app.modules.pricing.router import router
from app.modules.pricing.service import PricingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide(
        "pricing.service_factory",
        lambda session: PricingService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            rulepacks_loader_provider=lambda: reg.get("rulepacks.loader"),
            boq_engine_provider=lambda: reg.get("boq.engine"),
            review_factory=reg.get("review.service_factory"),
        ),
    )


module = ModuleSpec(
    name="pricing",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "rulepacks", "boq", "review", "auth"),
    setup=setup,
)
