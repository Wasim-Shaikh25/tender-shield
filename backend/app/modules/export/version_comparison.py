"""Version comparison export — Generate before/after analysis diffs.

Shows changes between two analysis runs: new risks, resolved risks, severity changes.
"""

from __future__ import annotations

from typing import Any


def _delta_emoji(change: str) -> str:
    """Return emoji for change type."""
    return {
        "new": "✨",
        "resolved": "✓",
        "escalated": "⬆️",
        "de-escalated": "⬇️",
        "unchanged": "•",
    }.get(change, "•")


def _classify_change(old: dict | None, new: dict | None) -> str:
    """Classify what changed between two findings."""
    if old is None:
        return "new"
    if new is None:
        return "resolved"

    old_sev = old.get("severity", "info")
    new_sev = new.get("severity", "info")

    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    old_rank = sev_rank.get(old_sev, 9)
    new_rank = sev_rank.get(new_sev, 9)

    if new_rank < old_rank:
        return "escalated"
    elif new_rank > old_rank:
        return "de-escalated"
    else:
        return "unchanged"


def generate_comparison_summary(
    opportunity_title: str,
    version_1_date: str,
    version_1_findings: list[dict[str, Any]],
    version_2_date: str,
    version_2_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate comparison summary between two analysis versions.

    Returns dict with subject, body, summary stats, and detailed changes.
    """

    # Index findings by title for comparison
    v1_by_title = {f.get("title"): f for f in version_1_findings}
    v2_by_title = {f.get("title"): f for f in version_2_findings}

    # Track changes
    new_findings = []
    resolved_findings = []
    escalated_findings = []
    de_escalated_findings = []
    unchanged_findings = []

    # Find new and changed findings
    for title, v2 in v2_by_title.items():
        v1 = v1_by_title.get(title)
        if v1 is None:
            new_findings.append(v2)
        else:
            change = _classify_change(v1, v2)
            if change == "escalated":
                escalated_findings.append((v1, v2))
            elif change == "de-escalated":
                de_escalated_findings.append((v1, v2))
            else:
                unchanged_findings.append(v2)

    # Find resolved findings
    for title, v1 in v1_by_title.items():
        v2 = v2_by_title.get(title)
        if v2 is None:
            resolved_findings.append(v1)

    # Build summary
    subject = f"Risk Analysis Comparison — {opportunity_title}"

    lines = []
    lines.append("Hi Team,\n")
    lines.append(f"Comparison of risk analyses: {version_1_date} vs {version_2_date}\n")
    lines.append("---\n")

    lines.append("**SUMMARY**")
    lines.append(f"- New risks: {len(new_findings)}")
    lines.append(f"- Resolved risks: {len(resolved_findings)}")
    lines.append(f"- Escalated: {len(escalated_findings)}")
    lines.append(f"- De-escalated: {len(de_escalated_findings)}")
    lines.append(f"- Unchanged: {len(unchanged_findings)}\n")

    if new_findings:
        lines.append(f"### ✨ NEW RISKS ({len(new_findings)})\n")
        for f in new_findings[:5]:
            lines.append(f"- [{f.get('severity').upper()}] {f.get('title')}")
        if len(new_findings) > 5:
            lines.append(f"- ... and {len(new_findings) - 5} more\n")
        lines.append("")

    if escalated_findings:
        lines.append(f"### ⬆️ ESCALATED ({len(escalated_findings)})\n")
        for v1, v2 in escalated_findings[:5]:
            lines.append(f"- {v1.get('title')}: {v1.get('severity')} → {v2.get('severity')}")
        if len(escalated_findings) > 5:
            lines.append(f"- ... and {len(escalated_findings) - 5} more\n")
        lines.append("")

    if de_escalated_findings:
        lines.append(f"### ⬇️ DE-ESCALATED ({len(de_escalated_findings)})\n")
        for v1, v2 in de_escalated_findings[:5]:
            lines.append(f"- {v1.get('title')}: {v1.get('severity')} → {v2.get('severity')}")
        if len(de_escalated_findings) > 5:
            lines.append(f"- ... and {len(de_escalated_findings) - 5} more\n")
        lines.append("")

    if resolved_findings:
        lines.append(f"### ✓ RESOLVED ({len(resolved_findings)})\n")
        for f in resolved_findings[:5]:
            lines.append(f"- {f.get('title')}")
        if len(resolved_findings) > 5:
            lines.append(f"- ... and {len(resolved_findings) - 5} more\n")
        lines.append("")

    body = "\n".join(lines)

    return {
        "subject": subject,
        "body": body,
        "stats": {
            "new": len(new_findings),
            "resolved": len(resolved_findings),
            "escalated": len(escalated_findings),
            "de_escalated": len(de_escalated_findings),
            "unchanged": len(unchanged_findings),
        },
        "changes": {
            "new_findings": new_findings,
            "resolved_findings": resolved_findings,
            "escalated_findings": escalated_findings,
            "de_escalated_findings": de_escalated_findings,
        },
    }
