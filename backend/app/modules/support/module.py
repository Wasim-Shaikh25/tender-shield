from app.core.module import AppContext, ModuleSpec
from app.modules.support.router import router


def setup(ctx: AppContext) -> None:
    pass


module = ModuleSpec(
    name="support",
    version="0.1.0",
    router=router,
    soft_deps=("auth",),
    setup=setup,
)
