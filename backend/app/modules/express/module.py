"""`express` module registration (TS-208, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
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
            publish=ctx.events.publish,
        )

    reg.provide("express.session", factory)
    reg.provide("express.service_factory", factory)


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
