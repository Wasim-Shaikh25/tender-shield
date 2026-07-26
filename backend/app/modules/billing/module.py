from app.core.module import AppContext, ModuleSpec
from app.modules.billing.router import router
from app.modules.billing.service import BillingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Metering consumed by risk/ingestion before starting a review (Doc §7).
    reg.provide(
        "billing.service_factory",
        lambda session: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ),
    )
    reg.provide(
        "billing.record_usage",
        lambda session, workspace_id, event, ref_id=None: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).record_usage(workspace_id, event, ref_id),
    )


module = ModuleSpec(
    name="billing",
    version="0.1.0",
    router=router,
    soft_deps=("auth",),
    setup=setup,
)
