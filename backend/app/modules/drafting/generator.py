"""Deterministic artifact assembly (Doc §6.5): facts are injected, structure is
built from accepted findings. Prose comes only from grounded fields, so the
validators pass by construction; an LLM polish pass (later) is subject to the
same validators."""

from __future__ import annotations


def _rupees(v: float | None) -> str | None:
    return f"₹{v:,.2f}" if v is not None else None


def build_body(kind: str, opportunity_title: str, findings: list[dict], weights=None) -> dict:
    if kind == "clarification_letter":
        return _clarification(opportunity_title, findings)
    if kind == "assumptions_register":
        return _assumptions(opportunity_title, findings)
    if kind == "bid_decision":
        return _bid_decision(opportunity_title, findings, weights)
    raise ValueError(f"unknown artifact kind: {kind}")


def _clarification(title: str, findings: list[dict]) -> dict:
    items = []
    for i, f in enumerate(findings, 1):
        items.append(
            {
                "n": i,
                "heading": f["title"],
                "quote": f.get("source_quote"),
                "source_page": f.get("source_page"),
                "ask": f.get("suggested_action")
                or "Please confirm the position on the clause quoted above.",
            }
        )
    return {
        "kind": "clarification_letter",
        "title": f"Clarification queries — {title}",
        "preamble": (
            "With reference to the above tender, we request the following "
            "clarifications before bid submission:"
        ),
        "items": items,
    }


def _assumptions(title: str, findings: list[dict]) -> dict:
    items = []
    for i, f in enumerate(findings, 1):
        amt = _rupees(f.get("amount_exposure"))
        items.append(
            {
                "n": i,
                "category": f["category"],
                "assumption": f["detail"],
                "exposure": amt,
                "source_page": f.get("source_page"),
            }
        )
    return {
        "kind": "assumptions_register",
        "title": f"Assumptions & exclusions — {title}",
        "items": items,
    }


def _bid_decision(title: str, findings: list[dict], weights: dict | None) -> dict:
    weights = weights or {}
    risk_w = weights.get("risk", {"critical": 25, "high": 15, "medium": 8, "low": 3, "info": 0})
    qual_w = weights.get("qualification", {"not_met": 20, "unknown": 10, "met": 0})
    boq_w = weights.get("boq", {"critical": 15, "high": 10, "medium": 5, "low": 2, "info": 0})
    std_w = weights.get("standard_violation", 15)

    score = 100
    concerns = []
    qualification_not_met = False
    for f in findings:
        kind = f.get("kind", "risk_clause")
        sev = f.get("severity", "medium")
        if kind == "risk_clause":
            deduction = risk_w.get(sev, 0)
            score -= deduction
            if sev in ("critical", "high"):
                concerns.append(f)
        elif kind == "qualification_gap":
            status = f.get("explanation", {}).get("status") or "unknown"
            if status == "not_met":
                score -= qual_w.get("not_met", 20)
                qualification_not_met = True
                concerns.append(f)
            elif status == "unknown":
                score -= qual_w.get("unknown", 10)
        elif kind == "boq_defect":
            score -= boq_w.get(sev, 0)
            if sev in ("critical", "high"):
                concerns.append(f)
        elif kind == "standard_violation":
            score -= std_w
            concerns.append(f)

    score = max(0, min(100, score))

    strengths = []
    categories_with_high = {
        f.get("category", "").lower() for f in findings if f.get("severity") in ("critical", "high")
    }
    if "payment" not in categories_with_high:
        strengths.append("Payment terms appear acceptable")
    if "ld" not in categories_with_high and "liquidated" not in categories_with_high:
        strengths.append("Liquidated damages terms within normal range")
    if "escalation" not in categories_with_high:
        strengths.append("Price escalation provision acceptable")
    if not qualification_not_met:
        strengths.append("Qualification criteria appear addressable")
    if not any(
        f.get("kind") == "boq_defect" and f.get("severity") in ("critical", "high")
        for f in findings
    ):
        strengths.append("BOQ quality appears acceptable")

    has_critical = any(f.get("severity") == "critical" for f in findings)
    if score >= 75 and not qualification_not_met and not has_critical:
        recommendation = "proceed"
    elif score >= 50:
        recommendation = "proceed_with_conditions"
    else:
        recommendation = "do_not_proceed"

    conditions = []
    for f in concerns:
        action = f.get("suggested_action") or "Review and resolve before bid submission"
        page = f.get("source_page")
        page_ref = f" (page {page})" if page else ""
        conditions.append(f"{action}{page_ref}: {f.get('title', '')}")

    return {
        "kind": "bid_decision",
        "title": f"Bid / No-Bid Recommendation — {title}",
        "score": score,
        "weights": weights,
        "strengths": strengths,
        "concerns": [
            {
                "title": f.get("title", ""),
                "category": f.get("category", ""),
                "severity": f.get("severity", ""),
                "source_page": f.get("source_page"),
                "source_quote": f.get("source_quote", ""),
                "suggested_action": f.get("suggested_action", ""),
            }
            for f in concerns
        ],
        "recommendation": recommendation,
        "conditions": conditions,
    }


def render_text(body: dict) -> str:
    """Flatten a body to plain text for validator scanning. Quotes are wrapped
    in double quotes so the quote-validator sees them."""
    lines = [body["title"]]
    if body.get("preamble"):
        lines.append(body["preamble"])
    if body["kind"] == "bid_decision":
        for s in body.get("strengths", []):
            lines.append(f"Strength: {s}")
        for c in body.get("concerns", []):
            lines.append(f"Concern: {c['title']} [{c['category']}] {c.get('severity', '')}")
            if c.get("source_quote"):
                lines.append(f'   "{c["source_quote"]}"')
            if c.get("suggested_action"):
                lines.append(f"   {c['suggested_action']}")
        for cond in body.get("conditions", []):
            lines.append(f"Condition: {cond}")
        lines.append(f"Recommendation: {body['recommendation']}")
        return "\n".join(lines)
    for item in body["items"]:
        if body["kind"] == "clarification_letter":
            lines.append(f"{item['n']}. {item['heading']}")
            if item.get("quote"):
                lines.append(f'   "{item["quote"]}"')
            lines.append(f"   {item['ask']}")
        else:
            line = f"{item['n']}. [{item['category']}] {item['assumption']}"
            if item.get("exposure"):
                line += f" (exposure {item['exposure']})"
            lines.append(line)
    return "\n".join(lines)
