"""Upload/export-based source adapters (TS-281–TS-287)."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import uuid
from datetime import date, datetime
from typing import Any
from xml.etree import ElementTree as ET


def _result(
    *,
    documents: list[dict] | None = None,
    events: list[dict] | None = None,
    cost_lines: list[dict] | None = None,
    activities: list[dict] | None = None,
    skipped: int = 0,
    errors: list[str] | None = None,
) -> dict:
    return {
        "documents": documents or [],
        "events": events or [],
        "cost_lines": cost_lines or [],
        "activities": activities or [],
        "skipped": skipped,
        "errors": errors or [],
    }


class BaseAdapter:
    name: str = ""
    supported_mimetypes: tuple[str, ...] = ()

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        """Return a normalized import result with no external I/O.

        The result shape is:
        {
            "documents": [...],
            "events": [...],
            "cost_lines": [...],
            "activities": [...],
            "skipped": int,
            "errors": [str],
        }
        """
        raise NotImplementedError

    def _native_id(self, *parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]

    def _decode_text(self, data: str | None) -> str:
        if not data:
            return ""
        if data.startswith("data:"):
            data = data.split(",", 1)[-1]
        try:
            return base64.b64decode(data.encode()).decode("utf-8", errors="ignore")
        except Exception:
            return data


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


class SharepointOnedriveAdapter(BaseAdapter):
    name = "sharepoint_onedrive"
    supported_mimetypes = ("application/json",)

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        files = payload.get("files", [])
        if not files:
            return _result()
        documents = []
        errors = []
        skipped = 0
        for f in files:
            filename = f.get("filename", "")
            if not filename:
                skipped += 1
                continue
            content = self._decode_text(f.get("content_base64", ""))
            try:
                documents.append(
                    {
                        "source_native_id": self._native_id(
                            source_id, f.get("folder_path", ""), filename
                        ),
                        "filename": filename,
                        "mime_type": f.get("mime_type", "application/octet-stream"),
                        "source_path": f.get("folder_path"),
                        "last_modified_at": _parse_date(f.get("last_modified_at")),
                        "sample_text": content[:4000],
                        "metadata": {"size_bytes": f.get("size_bytes")},
                    }
                )
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
        return _result(documents=documents, skipped=skipped, errors=errors)


class ProcoreAdapter(BaseAdapter):
    name = "procore"
    supported_mimetypes = ("application/json",)

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        events: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        for item in payload.get("rfis", []):
            if not opportunity_id:
                continue
            events.append(
                {
                    "source_native_id": self._native_id(source_id, str(item.get("id"))),
                    "kind": "rfi",
                    "title": item.get("subject") or item.get("name") or "Procore RFI",
                    "occurred_at": item.get("created_at"),
                    "metadata": item,
                }
            )
        for item in payload.get("change_events", []):
            if not opportunity_id:
                continue
            events.append(
                {
                    "source_native_id": self._native_id(source_id, str(item.get("id"))),
                    "kind": "change_event",
                    "title": item.get("title") or item.get("subject") or "Procore change event",
                    "occurred_at": item.get("created_at"),
                    "metadata": item,
                }
            )
        return _result(documents=documents, events=events)


class AutodeskAdapter(BaseAdapter):
    name = "autodesk"
    supported_mimetypes = ("application/json",)

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        events = []
        for item in payload.get("issues", []):
            if not opportunity_id:
                continue
            kind = "change_event" if (item.get("type") or "").lower() == "change" else "issue"
            events.append(
                {
                    "source_native_id": self._native_id(source_id, str(item.get("id"))),
                    "kind": kind,
                    "title": item.get("title") or item.get("subject") or "Autodesk issue",
                    "occurred_at": item.get("created_at"),
                    "metadata": item,
                }
            )
        documents = []
        for item in payload.get("submittals", []):
            documents.append(
                {
                    "source_native_id": self._native_id(source_id, str(item.get("id"))),
                    "filename": item.get("title") or "submittal.pdf",
                    "mime_type": "application/pdf",
                    "sample_text": item.get("description", "")[:4000],
                    "metadata": item,
                }
            )
        return _result(documents=documents, events=events)


class AconexAdapter(BaseAdapter):
    name = "aconex"
    supported_mimetypes = ("application/json",)

    _CHANGE_KEYWORDS = ("variation", "change", "instruction", "revision", "amendment")

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        documents = []
        events = []
        for item in payload.get("mails", []) + payload.get("transmittals", []):
            subject = (item.get("subject") or "").lower()
            doc = {
                "source_native_id": self._native_id(source_id, str(item.get("id"))),
                "filename": item.get("subject") or "aconex_mail.pdf",
                "mime_type": "application/pdf",
                "sample_text": item.get("body", "")[:4000],
                "metadata": item,
            }
            documents.append(doc)
            if any(k in subject for k in self._CHANGE_KEYWORDS) and opportunity_id:
                events.append(
                    {
                        "source_native_id": self._native_id(source_id, f"event:{item.get('id')}"),
                        "kind": "change_event",
                        "title": item.get("subject") or "Aconex change item",
                        "occurred_at": item.get("sent_at"),
                        "metadata": item,
                    }
                )
        return _result(documents=documents, events=events)


class ErpAdapter(BaseAdapter):
    name = "erp"
    supported_mimetypes = ("text/csv", "application/json")

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        lines = []
        rows = payload.get("rows") or []
        currency = payload.get("currency", "INR")
        for row in rows:
            cost_code = row.get("cost_code") or row.get("costCode") or row.get("Cost Code")
            if not cost_code:
                continue
            lines.append(
                {
                    "source_native_id": self._native_id(source_id, str(cost_code)),
                    "opportunity_id": opportunity_id,
                    "cost_code": str(cost_code),
                    "description": row.get("description") or row.get("Description"),
                    "committed_cost_minor": int(row.get("committed_cost_minor") or 0),
                    "certified_value_minor": int(row.get("certified_value_minor") or 0),
                    "currency": currency,
                    "metadata": row,
                }
            )
        return _result(cost_lines=lines)


class ScheduleAdapter(BaseAdapter):
    name = "schedule"
    supported_mimetypes = ("text/csv", "application/xml", "application/x-xer")

    def normalize(
        self,
        payload: dict,
        *,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        user_id: uuid.UUID,
        opportunity_id: uuid.UUID | None = None,
    ) -> dict:
        activities = []
        fmt = payload.get("format", "csv")
        if fmt == "csv":
            activities = self._parse_csv(payload.get("content", ""))
        elif fmt == "ms_project_xml":
            activities = self._parse_ms_project_xml(payload.get("content", ""))
        elif fmt == "p6_xer":
            activities = self._parse_p6_xer(payload.get("content", ""))
        return _result(activities=activities)

    def _parse_csv(self, content: str) -> list[dict]:
        rows: list[dict[str, Any]] = []
        if not content:
            return rows
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            activity_id = row.get("activity_id") or row.get("Activity ID") or row.get("ID")
            if not activity_id:
                continue
            rows.append(
                {
                    "source_native_id": str(activity_id),
                    "name": row.get("name") or row.get("Name") or row.get("activity_name") or "",
                    "start_date": _parse_date(row.get("start") or row.get("Start")),
                    "finish_date": _parse_date(row.get("finish") or row.get("Finish")),
                    "duration_days": int(row.get("duration_days") or row.get("Duration") or 0),
                    "predecessors": None,
                    "linked_change_event_ids": None,
                    "metadata": row,
                }
            )
        return rows

    def _parse_ms_project_xml(self, content: str) -> list[dict]:
        rows: list[dict[str, Any]] = []
        if not content:
            return rows
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return rows
        namespace = "{http://schemas.microsoft.com/project}"
        for task in root.iter(f"{namespace}Task"):
            uid = task.find(f"{namespace}UID")
            name = task.find(f"{namespace}Name")
            start = task.find(f"{namespace}Start")
            finish = task.find(f"{namespace}Finish")
            task.find(f"{namespace}Duration")  # available for future duration parsing
            if uid is None or uid.text is None:
                continue
            rows.append(
                {
                    "source_native_id": uid.text,
                    "name": name.text if name is not None else "",
                    "start_date": _parse_date(start.text) if start is not None else None,
                    "finish_date": _parse_date(finish.text) if finish is not None else None,
                    "duration_days": 0,
                    "predecessors": None,
                    "linked_change_event_ids": None,
                    "metadata": {},
                }
            )
        return rows

    def _parse_p6_xer(self, content: str) -> list[dict]:
        rows: list[dict[str, Any]] = []
        if not content:
            return rows
        section = None
        headers = None
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("%T"):
                section = line[2:].strip().upper()
                headers = None
                continue
            if section != "TASK":
                continue
            if line.startswith("%F"):
                headers = [h.strip() for h in line[2:].split("\t")]
                continue
            if not line or line.startswith("%") or headers is None:
                continue
            values = line.split("\t")
            row = dict(zip(headers, values, strict=False))
            task_id = row.get("task_id") or row.get("task_code")
            if not task_id:
                continue
            rows.append(
                {
                    "source_native_id": str(task_id),
                    "name": row.get("task_name") or "",
                    "start_date": _parse_date(
                        row.get("act_start_date") or row.get("early_start_date")
                    ),
                    "finish_date": _parse_date(
                        row.get("act_end_date") or row.get("early_end_date")
                    ),
                    "duration_days": int(row.get("target_drtn_hr_cnt") or 0) // 8 or 0,
                    "predecessors": None,
                    "linked_change_event_ids": None,
                    "metadata": row,
                }
            )
        return rows


ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {
    cls.name: cls
    for cls in (
        SharepointOnedriveAdapter,
        ProcoreAdapter,
        AutodeskAdapter,
        AconexAdapter,
        ErpAdapter,
        ScheduleAdapter,
    )
}
