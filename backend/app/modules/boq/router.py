from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
def boq_status(request: Request) -> dict:
    engine = request.app.state.ctx.registry.get("boq.engine")
    return {
        "engine": "deterministic (zero LLM)",
        "available_checklists": engine.available_checklists() if engine else [],
    }
