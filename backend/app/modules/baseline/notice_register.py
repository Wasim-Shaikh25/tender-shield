"""Notice register enrichment and deadline arithmetic (TS-238).

Deterministic — no LLM. Contacts are never invented; deadline math uses
confirmed milestone dates from ingestion when available.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_DATE_HINT = re.compile(
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.I,
)
_MILESTONE_HINT = re.compile(
    r"practical completion|completion date|handover|milestone|certificate|"
    r"substantial completion|taking over",
    re.I,
)

_CATEGORY_MILESTONES: dict[str, list[str]] = {
    "claim": ["practical_completion", "site_handover", "submission"],
    "extension_of_time": ["practical_completion", "submission"],
    "payment": ["practical_completion", "payment_certificate"],
    "variation": ["practical_completion", "submission"],
    "defect": ["practical_completion", "defects_liability"],
    "termination": ["practical_completion", "submission"],
}

_DEFAULT_CHECKLISTS: dict[str, list[str]] = {
    "claim": [
        "Written notice of claim",
        "Contract clause reference",
        "Description of triggering event",
        "Estimated time and cost impact",
    ],
    "extension_of_time": [
        "Written EOT notice",
        "Cause of delay described",
        "Supporting programme evidence",
    ],
    "payment": [
        "Interim application reference",
        "Supporting measurement / RA bill",
        "Contract payment clause cited",
    ],
}


def infer_trigger_event(trigger: str) -> str:
    text = trigger or ""
    if _MILESTONE_HINT.search(text):
        return "milestone"
    if _DATE_HINT.search(text):
        return "date"
    return "event"


def deadline_basis(unit_raw: str) -> str:
    return "business" if "working" in (unit_raw or "").lower() else "calendar"


def _parse_due(due_at: str) -> date | None:
    if not due_at:
        return None
    try:
        return datetime.fromisoformat(due_at.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def compute_deadline(
    *,
    deadline_days: int | None,
    trigger_event: str,
    notice_type: str,
    deadlines: list[dict],
) -> dict:
    if not deadline_days:
        return {"deadline_unknown": True, "deadline_reason": "no_days"}
    if trigger_event != "milestone":
        return {"deadline_unknown": True, "deadline_reason": f"trigger_is_{trigger_event}"}

    kinds = _CATEGORY_MILESTONES.get(notice_type, [])
    milestone: dict | None = None
    for kind in kinds:
        for row in deadlines:
            if row.get("kind") == kind and row.get("due_at"):
                milestone = row
                break
        if milestone:
            break
    if milestone is None:
        for row in deadlines:
            if row.get("due_at"):
                milestone = row
                break
    if milestone is None:
        return {"deadline_unknown": True, "deadline_reason": "no_confirmed_milestone"}

    trigger_date = _parse_due(milestone.get("due_at"))
    if trigger_date is None:
        return {"deadline_unknown": True, "deadline_reason": "invalid_milestone_date"}

    notice_deadline = (trigger_date + timedelta(days=deadline_days)).isoformat()
    return {
        "deadline_unknown": False,
        "notice_deadline": notice_deadline,
        "trigger_milestone_kind": milestone.get("kind"),
        "trigger_date": milestone.get("due_at"),
    }


def _contact_dict(row) -> dict:
    return {
        "party": row.party,
        "role_label": row.role_label,
        "postal_address": row.postal_address,
        "email": row.email,
    }


def required_content_for(
    notice_type: str, categories: list[dict], contact_required: list | None
) -> list[str]:
    if contact_required:
        return list(contact_required)
    for cat in categories:
        if cat.get("key") == notice_type:
            label = cat.get("label", notice_type)
            return _DEFAULT_CHECKLISTS.get(
                notice_type, [f"Written {label} notice", "Contract clause reference"]
            )
    return _DEFAULT_CHECKLISTS.get(notice_type, ["Written notice", "Contract clause reference"])


def enrich_rule(
    rule: dict,
    *,
    categories: list[dict],
    contacts: dict[str, object],
    deadlines: list[dict],
) -> dict:
    notice_type = rule.get("category", "other")
    trigger_event = infer_trigger_event(rule.get("trigger", ""))
    deadline_days = rule.get("days")
    basis = deadline_basis(rule.get("unit_raw", ""))
    deadline_info = compute_deadline(
        deadline_days=deadline_days,
        trigger_event=trigger_event,
        notice_type=notice_type,
        deadlines=deadlines,
    )
    contact = contacts.get(notice_type)
    enriched = {
        **rule,
        "notice_type": notice_type,
        "trigger_event": trigger_event,
        "deadline_days": deadline_days,
        "deadline_basis": basis,
        "required_content": required_content_for(
            notice_type,
            categories,
            getattr(contact, "required_content", None) if contact else None,
        ),
        **deadline_info,
    }
    if contact is not None:
        enriched["correspondence"] = _contact_dict(contact)
        enriched["authorized_representative"] = contact.authorized_representative
    else:
        enriched["correspondence"] = None
        enriched["authorized_representative"] = None
    return enriched
