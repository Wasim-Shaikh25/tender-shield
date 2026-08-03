"""Project state dashboard module."""

from app.core.module import AppContext, ModuleSpec
from app.modules.project_state.router import router


def setup(ctx: AppContext) -> None:
    pass


module = ModuleSpec(
    name="project_state",
    version="0.1.0",
    router=router,
    soft_deps=("auth", "ingestion", "findings", "baseline"),
    setup=setup,
)
