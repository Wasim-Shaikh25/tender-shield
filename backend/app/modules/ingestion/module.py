from app.core.module import AppContext, ModuleSpec
from app.modules.ingestion.ocr import NullOcrProvider, RapidOcrProvider
from app.modules.ingestion.router import router
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.tables import file_to_boq_csv


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Published so risk/boq/drafting can resolve opportunities without importing
    # ingestion. rulepacks + auth are soft deps resolved lazily.
    reg.provide(
        "ingestion.service_factory",
        lambda session: IngestionService(
            session,
            loader_provider=lambda: reg.get("rulepacks.loader"),
            publish=ctx.events.publish,
        ),
    )
    # OCR provider (RapidOCR when enabled, else Null → honest degradation).
    reg.provide(
        "ingestion.ocr",
        RapidOcrProvider() if ctx.settings.ocr_enabled else NullOcrProvider(),
    )
    # Pure file→BOQ-CSV helper so the BOQ module reads PDF/XLSX tables without
    # importing ingestion.
    reg.provide("ingestion.file_to_boq_csv", file_to_boq_csv)


module = ModuleSpec(
    name="ingestion",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "auth"),
    setup=setup,
)
