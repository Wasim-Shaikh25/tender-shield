"""Grounded tools for the assistant (Doc §8: tools, not vibes). Each reads only
the org's own data via injected capabilities and returns structured, citable
results — no LLM involved, so the common queries work with no API key."""

from __future__ import annotations


def list_deadlines(ingestion_factory, session, org_id, opportunity_id) -> list[dict]:
    if not ingestion_factory:
        return []
    svc = ingestion_factory(session)
    return [
        {
            "kind": d.kind,
            "due_at": d.due_at.isoformat() if d.due_at else None,
            "page": d.source_page,
            "confirmed": d.confirmed,
        }
        for d in svc.list_deadlines(org_id, opportunity_id)
    ]


def filter_findings(
    findings_factory, session, org_id, opportunity_id, *, severity=None, category=None
) -> list[dict]:
    if not findings_factory:
        return []
    rows = findings_factory(session).list(org_id, opportunity_id)
    out = []
    for r in rows:
        if severity and r.severity != severity:
            continue
        if category and r.category != category:
            continue
        out.append(
            {
                "severity": r.severity,
                "category": r.category,
                "title": r.title,
                "page": r.source_page,
                "pattern_id": r.pattern_id,
            }
        )
    return out


def missing_docs(ingestion_factory, session, org_id, opportunity_id) -> dict:
    if not ingestion_factory:
        return {"present": [], "missing": [], "expected": []}
    return ingestion_factory(session).missing_doc_report(org_id, opportunity_id)


def rulepack_lookup(loader, topic: str, pack_id: str = "in-works") -> list[dict]:
    if not loader:
        return []
    topic_l = topic.lower()
    out = []
    for p in loader.list_patterns(pack_id):
        if topic_l in p.category.lower() or topic_l in p.title.lower():
            out.append({"pattern_id": p.id, "category": p.category, "title": p.title})
    return out
