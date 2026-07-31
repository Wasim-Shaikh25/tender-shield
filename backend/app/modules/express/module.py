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
    ),
    setup=setup,
)
