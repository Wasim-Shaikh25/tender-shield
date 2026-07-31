"""Shared helpers for attaching employer context to API responses (TS-200)."""

from __future__ import annotations


def employer_context_for_opportunity(
    registry,
    session,
    *,
    workspace_id,
    opportunity_id,
) -> dict | None:
    ingestion_factory = registry.get("ingestion.service_factory")
    context_fn = registry.get("marketdata.employer_context_for_family")
    if ingestion_factory is None or context_fn is None:
        return None
    opp = ingestion_factory(session).get_opportunity(workspace_id, opportunity_id)
    family = getattr(opp, "employer_family", None) if opp is not None else None
    if not family:
        return None
    return context_fn(session, family)
