from app.core.module import ModuleSpec
from app.modules.health.router import router

module = ModuleSpec(
    name="health",
    version="0.1.0",
    router=router,
)
