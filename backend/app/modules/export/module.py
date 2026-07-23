from app.core.module import ModuleSpec
from app.modules.export.router import router

module = ModuleSpec(
    name="export",
    version="0.1.0",
    router=router,
    soft_deps=("review", "findings", "drafting", "ingestion", "rulepacks", "auth"),
)
