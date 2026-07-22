from app.core.module import AppContext, ModuleSpec
from app.modules.rulepacks.loader import RulePackLoader
from app.modules.rulepacks.router import router


def setup(ctx: AppContext) -> None:
    loader = RulePackLoader(ctx.settings.rulepacks_dir or None)
    ctx.registry.provide("rulepacks.loader", loader)


module = ModuleSpec(
    name="rulepacks",
    version="0.1.0",
    router=router,
    setup=setup,
)
