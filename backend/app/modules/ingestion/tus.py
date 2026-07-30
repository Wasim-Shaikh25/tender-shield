"""Minimal tus 1.0 resumable upload server (TS-033).

Supports Creation → PATCH → HEAD with local chunk storage. When the final chunk
is received the file is moved to the normal storage backend and processed.

In production the chunk directory must be a shared volume or the tus server must
be pinned to a single instance. A TTL sweeper removes abandoned uploads.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import pathlib
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.storage import (
    DEFAULT_MAX_UPLOAD_SIZE,
    MAX_UPLOAD_SIZES,
    StorageError,
    ValidationError,
    validate_and_store,
)
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.tasks import process_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tus")

UPLOAD_DIR = pathlib.Path("/tmp/tender-shield-tus")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Abandoned uploads are removed after this many seconds (24 hours).
UPLOAD_TTL_SECONDS = 24 * 60 * 60
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _service(request: Request, session: Session) -> IngestionService:
    reg = request.app.state.ctx.registry
    return IngestionService(
        session,
        loader_provider=lambda: reg.get("rulepacks.loader"),
        publish=request.app.state.ctx.events.publish,
    )


def _decode_metadata(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    out = {}
    for part in (header or "").split(","):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition(" ")
        try:
            out[key] = base64.b64decode(value).decode("utf-8")
        except Exception:
            out[key] = value
    return out


def _state_path(upload_id: str) -> pathlib.Path:
    return UPLOAD_DIR / f"{upload_id}.json"


def _file_path(upload_id: str) -> pathlib.Path:
    return UPLOAD_DIR / f"{upload_id}.part"


def _validate_upload_id(upload_id: str) -> None:
    if not _UPLOAD_ID_RE.match(upload_id):
        raise HTTPException(400, "invalid_upload_id")


def _load_state(upload_id: str) -> dict[str, Any]:
    _validate_upload_id(upload_id)
    path = _state_path(upload_id)
    if not path.exists():
        raise HTTPException(404, "upload_not_found")
    return json.loads(path.read_text())


def _save_state(upload_id: str, state: dict) -> None:
    _state_path(upload_id).write_text(json.dumps(state))


def _max_upload_size(filename: str) -> int:
    ext = pathlib.Path(filename).suffix.lower()
    return MAX_UPLOAD_SIZES.get(ext, DEFAULT_MAX_UPLOAD_SIZE)


def _is_expired(path: pathlib.Path) -> bool:
    try:
        return time.time() - path.stat().st_mtime > UPLOAD_TTL_SECONDS
    except OSError:
        return False


def sweep_expired_uploads() -> int:
    """Remove tus chunk/state files older than UPLOAD_TTL_SECONDS."""
    removed = 0
    for path in UPLOAD_DIR.glob("*"):
        if _is_expired(path):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


@router.options("/")
def tus_options():
    """Return tus server capabilities (tus 1.0.0 spec)."""
    return Response(
        status_code=204,
        headers={
            "Tus-Resumable": "1.0.0",
            "Tus-Version": "1.0.0",
            "Tus-Max-Size": str(DEFAULT_MAX_UPLOAD_SIZE),
            "Tus-Extension": "creation,creation-with-upload",
            "Cache-Control": "no-store",
        },
    )


@router.post("/")
async def tus_create(
    request: Request,
    upload_length: int | None = Header(None, alias="Upload-Length"),
    upload_metadata: str | None = Header(None, alias="Upload-Metadata"),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    metadata = _decode_metadata(upload_metadata)
    filename = metadata.get("filename", "upload")
    max_size = _max_upload_size(filename)
    if upload_length is not None and upload_length > max_size:
        raise HTTPException(413, "file_too_large")
    upload_id = uuid.uuid4().hex
    state = {
        "id": upload_id,
        "offset": 0,
        "length": upload_length,
        "max_size": max_size,
        "filename": filename,
        "workspace_id": str(principal.workspace_id),
        "opportunity_id": metadata.get("opportunity_id", ""),
        "async": metadata.get("async", "false").lower() == "true",
        "content_type": metadata.get("content_type", "application/octet-stream"),
        "uploaded_by": str(principal.user_id),
    }

    def _init():
        _file_path(upload_id).write_bytes(b"")
        _save_state(upload_id, state)

    await asyncio.to_thread(_init)

    return Response(
        status_code=201,
        headers={
            "Location": f"/api/ingestion/tus/{upload_id}",
            "Tus-Resumable": "1.0.0",
        },
    )


@router.head("/{upload_id}")
def tus_status(
    upload_id: str,
    principal: Any = Depends(require("estimator")),
):
    state = _load_state(upload_id)
    if state["workspace_id"] != str(principal.workspace_id):
        raise HTTPException(403, "workspace_mismatch")
    return Response(
        status_code=200,
        headers={
            "Upload-Offset": str(state["offset"]),
            "Upload-Length": str(state["length"] or ""),
            "Tus-Resumable": "1.0.0",
            "Cache-Control": "no-store",
        },
    )


@router.patch("/{upload_id}")
async def tus_patch(
    upload_id: str,
    request: Request,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    state = await asyncio.to_thread(_load_state, upload_id)
    if state["workspace_id"] != str(principal.workspace_id):
        raise HTTPException(403, "workspace_mismatch")
    if upload_offset != state["offset"]:
        raise HTTPException(409, "offset_conflict")
    data = await request.body()
    file_path = _file_path(upload_id)
    max_size = state.get("max_size", DEFAULT_MAX_UPLOAD_SIZE)

    def _append():
        if file_path.stat().st_size + len(data) > max_size:
            raise HTTPException(413, "file_too_large")
        with file_path.open("ab") as f:
            f.write(data)
        state["offset"] = file_path.stat().st_size
        _save_state(upload_id, state)
        return state["offset"]

    new_offset = await asyncio.to_thread(_append)

    if state["length"] and new_offset >= state["length"]:
        return await _finalize(request, session, state, upload_id)

    return Response(
        status_code=204,
        headers={
            "Upload-Offset": str(new_offset),
            "Tus-Resumable": "1.0.0",
        },
    )


async def _finalize(request, session, state, upload_id):
    file_path = _file_path(upload_id)

    def _read():
        return file_path.read_bytes()

    data = await asyncio.to_thread(_read)
    settings = request.app.state.ctx.settings
    svc = _service(request, session)
    opportunity_id = state["opportunity_id"]
    workspace_id = state["workspace_id"]
    if not svc.get_opportunity(workspace_id, opportunity_id):
        raise HTTPException(404, "not_found")
    try:
        stored = await validate_and_store(
            settings,
            state["filename"],
            state["content_type"],
            data,
            workspace_id=workspace_id,
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(500, str(exc)) from exc

    if state["async"]:
        doc = svc.register_document(
            workspace_id,
            opportunity_id,
            state["filename"],
            "",
            s3_key=stored["key"],
            sha256=stored["sha256"],
            ocr_status="pending",
            uploaded_by=uuid.UUID(state["uploaded_by"]),
        )
        task = process_document.delay(str(doc.id), workspace_id, opportunity_id)
        result = {
            "id": str(doc.id),
            "filename": doc.filename,
            "task_id": task.id,
            "ocr_status": "pending",
        }
    else:
        ocr = request.app.state.ctx.registry.get("ingestion.ocr")
        text, ocr_status = await asyncio.to_thread(extract_upload, state["filename"], data, ocr)
        doc = svc.register_document(
            workspace_id,
            opportunity_id,
            state["filename"],
            text,
            s3_key=stored["key"],
            sha256=stored["sha256"],
            ocr_status=ocr_status,
            uploaded_by=uuid.UUID(state["uploaded_by"]),
        )
        result = {
            "id": str(doc.id),
            "filename": doc.filename,
            "kind": doc.kind,
            "chars": len(text),
            "ocr_status": ocr_status,
        }

    def _cleanup():
        file_path.unlink(missing_ok=True)
        _state_path(upload_id).unlink(missing_ok=True)

    await asyncio.to_thread(_cleanup)

    return Response(
        status_code=204,
        headers={
            "Upload-Offset": str(state["offset"]),
            "X-Document-Id": result["id"],
            "Tus-Resumable": "1.0.0",
        },
    )
