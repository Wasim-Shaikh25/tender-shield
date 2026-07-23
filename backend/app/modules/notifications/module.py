from app.core.module import AppContext, ModuleSpec
from app.modules.notifications.sender import ConsoleSender


def setup(ctx: AppContext) -> None:
    # ConsoleSender in dev/test; SES/MSG91 adapters register here in prod (TS-035).
    ctx.registry.provide("notifications.sender", ConsoleSender())


module = ModuleSpec(
    name="notifications",
    version="0.1.0",
    router=None,
    soft_deps=("ingestion",),
    setup=setup,
)
