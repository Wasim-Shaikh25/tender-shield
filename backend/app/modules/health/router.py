from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
def health(request: Request) -> dict:
    report = request.app.state.load_report
    return {
        "status": "ok",
        "modules": [
            {"name": s.name, "version": s.version, "soft_deps": list(s.soft_deps)}
            for s in report.loaded
        ],
        "failed_modules": report.failed,
        "missing_soft_deps": report.missing_soft_deps,
        "capabilities": request.app.state.ctx.registry.names(),
    }
