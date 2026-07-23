from app.core.module import AppContext, ModuleSpec
from app.modules.findings.router import router
from app.modules.findings.store import FindingStore


def setup(ctx: AppContext) -> None:
    # Producers (risk, boq) resolve this to persist; review resolves it to read.
    ctx.registry.provide("findings.store_factory", lambda session: FindingStore(session))


module = ModuleSpec(
    name="findings",
    version="0.1.0",
    router=router,
    setup=setup,
)
