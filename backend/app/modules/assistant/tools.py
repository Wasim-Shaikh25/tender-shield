"""Grounded tools for the assistant (Doc §8: tools, not vibes). Each reads only
the org's own data via injected capabilities and returns structured, citable
results — no LLM involved, so the common queries work with no API key."""

from __future__ import annotations


def _opportunity_ids(ingestion_factory, session, workspace_id, opportunity_id):
    """Return the explicit opportunity id, or all opportunity ids in the workspace."""
    if opportunity_id:
        return [opportunity_id]
    if not ingestion_factory:
        return []
    svc = ingestion_factory(session)
    return [str(o.id) for o in svc.list_opportunities(workspace_id)]


def list_deadlines(ingestion_factory, session, workspace_id, opportunity_id) -> list[dict]:
    if not ingestion_factory:
        return []
    svc = ingestion_factory(session)
    out = []
    for opp_id in _opportunity_ids(ingestion_factory, session, workspace_id, opportunity_id):
        for d in svc.list_deadlines(workspace_id, opp_id):
            out.append({
                "kind": d.kind,
                "opportunity_id": opp_id,
                "due_at": d.due_at.isoformat() if d.due_at else None,
                "page": d.source_page,
                "confirmed": d.confirmed,
            })
    return out


def filter_findings(
    findings_factory, session, workspace_id, opportunity_id, *, severity=None, category=None
) -> list[dict]:
    if not findings_factory:
        return []
    store = findings_factory(session)
    if opportunity_id:
        rows = store.list(workspace_id, opportunity_id, producer=None)
    else:
        rows = store.list_for_workspace(workspace_id, producer=None)
    out = []
    for r in rows:
        if severity and r.severity != severity:
            continue
        if category and r.category != category:
            continue
        out.append({
            "severity": r.severity,
            "category": r.category,
            "title": r.title,
            "opportunity_id": str(r.opportunity_id),
            "page": r.source_page,
            "pattern_id": r.pattern_id,
        })
    return out


def missing_docs(ingestion_factory, session, workspace_id, opportunity_id) -> dict:
    if not ingestion_factory:
        return {"present": [], "missing": [], "expected": []}
    svc = ingestion_factory(session)
    present: list[str] = []
    for opp_id in _opportunity_ids(ingestion_factory, session, workspace_id, opportunity_id):
        present.extend(d.kind for d in svc.list_documents(workspace_id, opp_id))
    # De-duplicate while preserving order for the report.
    seen = set()
    present_unique: list[str] = []
    for k in present:
        if k not in seen:
            seen.add(k)
            present_unique.append(k)
    expected = svc._expected()
    missing = [kind for kind in expected if kind not in set(present_unique)]
    return {"present": sorted(set(present_unique)), "missing": missing, "expected": expected}


def rulepack_lookup(loader, topic: str, pack_id: str = "in-works") -> list[dict]:
    if not loader:
        return []
    topic_l = topic.lower()
    out = []
    for p in loader.list_patterns(pack_id):
        if topic_l in p.category.lower() or topic_l in p.title.lower():
            out.append({"pattern_id": p.id, "category": p.category, "title": p.title})
    return out
