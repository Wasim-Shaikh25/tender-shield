"""Deterministic artifact assembly (Doc §6.5): facts are injected, structure is
built from accepted findings. Prose comes only from grounded fields, so the
validators pass by construction; an LLM polish pass (later) is subject to the
same validators."""

from __future__ import annotations


def _rupees(v: float | None) -> str | None:
    return f"₹{v:,.2f}" if v is not None else None


def build_body(kind: str, opportunity_title: str, findings: list[dict]) -> dict:
    if kind == "clarification_letter":
        return _clarification(opportunity_title, findings)
    if kind == "assumptions_register":
        return _assumptions(opportunity_title, findings)
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


def render_text(body: dict) -> str:
    """Flatten a body to plain text for validator scanning. Quotes are wrapped
    in double quotes so the quote-validator sees them."""
    lines = [body["title"]]
    if body.get("preamble"):
        lines.append(body["preamble"])
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
