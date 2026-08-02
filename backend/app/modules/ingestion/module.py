from app.core.module import AppContext, ModuleSpec
from app.modules.ingestion.doc_text import DocTextService
from app.modules.ingestion.ocr import NullOcrProvider, RapidOcrProvider, RapidTableProvider
from app.modules.ingestion.router import router
from app.modules.ingestion.segment import segment_clauses
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.tables import file_to_boq_csv, scanned_boq_csv
from app.modules.ingestion.tus import sweep_expired_uploads


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
    # Pure text→clause segmentation so baseline award comparison never imports ingestion.
    reg.provide("ingestion.segment_clauses", segment_clauses)
    # Scanned-table fallback (offline rapid-table; no cloud) — only when OCR is on.
    if ctx.settings.ocr_enabled:
        table_provider = RapidTableProvider()
        reg.provide(
            "ingestion.scanned_boq_csv",
            lambda data: scanned_boq_csv(table_provider.table_html(data)),
        )
    # Page-level text access for crossref / assistant / search.
    reg.provide(
        "ingestion.doc_text",
        lambda session: DocTextService(session),
    )
    reg.provide(
        "ingestion.documents_for_retention",
        lambda session, workspace_id, retention_days: IngestionService(
            session,
            loader_provider=lambda: reg.get("rulepacks.loader"),
            publish=ctx.events.publish,
        ).documents_for_retention(workspace_id, retention_days),
    )

    scheduler = reg.get("core.scheduler")
    if scheduler is not None:
        scheduler.add_job(sweep_expired_uploads, "interval", hours=1)


module = ModuleSpec(
    name="ingestion",
    version="0.1.0",
    router=router,
    soft_deps=("rulepacks", "auth"),
    setup=setup,
)
