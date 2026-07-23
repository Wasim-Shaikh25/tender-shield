from app.core.module import AppContext, ModuleSpec
from app.modules.billing.router import router
from app.modules.billing.service import BillingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Metering consumed by risk/ingestion before starting a review (Doc §7).
    reg.provide(
        "billing.service_factory",
        lambda session: BillingService(session, orgs_factory=reg.get("auth.orgs_factory")),
    )


module = ModuleSpec(
    name="billing",
    version="0.1.0",
    router=router,
    soft_deps=("auth",),
    setup=setup,
)
