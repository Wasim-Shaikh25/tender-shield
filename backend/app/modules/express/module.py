"""`express` module registration (TS-208, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.express.router import router
from app.modules.express.service import ExpressService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    reg.provide("express.session", lambda session: ExpressService(session))
    reg.provide("express.service_factory", lambda session: ExpressService(session))


module = ModuleSpec(
    name="express",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "risk", "boq", "export", "billing", "notifications", "auth"),
    setup=setup,
)
