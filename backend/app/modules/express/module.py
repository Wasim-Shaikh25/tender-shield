"""`express` module registration (TS-208, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.express.activation import activate_from_webhook
from app.modules.express.prices import validate_express_amount
from app.modules.express.router import router
from app.modules.express.service import ExpressService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return ExpressService(
            session,
            create_workspace=reg.get("auth.create_ephemeral_workspace"),
            ingestion_factory=reg.get("ingestion.service_factory"),
            findings_factory=reg.get("findings.store_factory"),
            run_risk=reg.get("risk.run_opportunity"),
            provider_factory=reg.get("billing.provider_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("express.session", factory)
    reg.provide("express.service_factory", factory)
    reg.provide(
        "express.activate_from_webhook",
        lambda session, **kwargs: activate_from_webhook(
            session, publish=ctx.events.publish, **kwargs
        ),
    )
    reg.provide(
        "express.validate_checkout_amount",
        lambda tier, currency, amount_minor: validate_express_amount(
            tier, currency, amount_minor
        ),
    )


module = ModuleSpec(
    name="express",
    version="0.1.0",
    router=router,
    soft_deps=(
        "auth",
        "ingestion",
        "risk",
        "boq",
        "export",
        "billing",
        "notifications",
        "findings",
    ),
    setup=setup,
)
