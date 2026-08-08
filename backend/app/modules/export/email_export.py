"""Email export module — Generate email-ready summary templates with findings.

Creates pre-formatted email content that contractors can send to their team
with a one-click action. Supports attachment of PDF export.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _severity_emoji(severity: str) -> str:
    """Return emoji for severity level."""
    return {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "info": "ℹ️",
    }.get(severity, "•")


def generate_email_summary(
    opportunity_title: str,
    findings: list[dict[str, Any]],
    deadline_info: dict[str, Any] | None = None,
    reviewer_email: str | None = None,
) -> dict[str, str]:
    """
    Generate email-ready summary content.

    Returns:
        dict with keys:
        - subject: Email subject line
        - body: Plain text email body (Markdown)
        - html_body: HTML version (for rich email clients)
    """

    # Categorize findings by severity
    high_risk = [f for f in findings if f.get("severity") in ("critical", "high")]
    medium_risk = [f for f in findings if f.get("severity") == "medium"]
    boq_issues = [f for f in findings if f.get("category") == "boq"]

    # Build email subject
    subject = f"Risk Review Complete — {opportunity_title}"

    # Build email body
    lines = []
    lines.append("Hi Team,\n")
    lines.append(f"I've completed the risk analysis for **{opportunity_title}**.")
    lines.append("Here's the summary:\n")

    # High risks
    if high_risk:
        lines.append(f"### {_severity_emoji('high')} HIGH RISK ITEMS: {len(high_risk)}\n")
        for finding in high_risk[:5]:  # Limit to 5 for email readability
            lines.append(
                f"- **{finding.get('title')}**: {finding.get('detail', 'See full analysis')}"
            )
            if finding.get("source_page"):
                lines.append(f"  (Page {finding.get('source_page')})")
        if len(high_risk) > 5:
            lines.append(f"- ...and {len(high_risk) - 5} more high-risk items\n")
        lines.append("")

    # Medium risks
    if medium_risk:
        lines.append(f"### {_severity_emoji('medium')} WARNINGS: {len(medium_risk)}\n")
        for finding in medium_risk[:3]:  # Limit to 3
            lines.append(f"- {finding.get('title')}")
        if len(medium_risk) > 3:
            lines.append(f"- ...and {len(medium_risk) - 3} more warnings\n")
        lines.append("")

    # BOQ issues
    if boq_issues:
        lines.append(f"### 📊 BOQ ISSUES: {len(boq_issues)}\n")
        for finding in boq_issues[:3]:
            lines.append(f"- {finding.get('title')}")
        if len(boq_issues) > 3:
            lines.append(f"- ...and {len(boq_issues) - 3} more BOQ issues\n")
        lines.append("")

    # Deadline info
    if deadline_info:
        deadline_date = deadline_info.get("date")
        days_left = deadline_info.get("days_left", "?")
        lines.append("### 📅 DEADLINE\n")
        lines.append(f"**{deadline_date}** ({days_left} days away)\n")

    # Recommendation
    if high_risk:
        recommendation = "⚠️ RECOMMEND: Renegotiate critical terms before bidding"
    elif medium_risk:
        recommendation = "🟡 RECOMMEND: Address medium-risk items in clarifications"
    else:
        recommendation = "✓ RECOMMEND: Proceed with bid (low risk)"

    lines.append("### RECOMMENDATION\n")
    lines.append(f"{recommendation}\n")

    # Footer
    lines.append("---\n")
    lines.append("**Full Analysis**: See attached PDF for complete findings with citations.")
    lines.append("")
    if reviewer_email:
        lines.append(f"*Analyzed by: {reviewer_email}*")
    lines.append(f"*Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("*Tool: TenderShield AI Risk Review*")

    body = "\n".join(lines)

    # Generate HTML version (simple Markdown → HTML conversion)
    html_body = _markdown_to_html(body)

    return {
        "subject": subject,
        "body": body,
        "html_body": html_body,
    }


def _markdown_to_html(markdown_text: str) -> str:
    """Simple Markdown to HTML conversion for email."""
    html = markdown_text
    html = html.replace("**", "<strong>")  # Simplified - not perfect
    html = html.replace("###", "<h3>")
    html = html.replace("---", "<hr>")
    html = html.replace("\n\n", "</p><p>")
    html = html.replace("\n", "<br>")
    html = f"<p>{html}</p>"
    return html


def generate_mailto_link(
    to_email: str | None = None,
    cc_emails: list[str] | None = None,
    subject: str = "",
    body: str = "",
) -> str:
    """Generate a mailto: URL for composing email in the user's client.

    Uses URL encoding for the body and subject.
    """
    from urllib.parse import quote

    params = []

    if to_email:
        # mailto: doesn't use ?to=, the email comes after mailto:
        pass

    if cc_emails:
        cc_str = ",".join(cc_emails)
        params.append(f"cc={quote(cc_str)}")

    if subject:
        params.append(f"subject={quote(subject)}")

    if body:
        params.append(f"body={quote(body)}")

    query_string = "&".join(params) if params else ""
    mailto_url = f"mailto:{to_email or 'team@company.com'}"

    if query_string:
        mailto_url += f"?{query_string}"

    return mailto_url


def generate_email_template_for_api(
    opportunity_title: str,
    findings: list[dict[str, Any]],
    deadline_info: dict[str, Any] | None = None,
    reviewer_email: str | None = None,
) -> dict[str, Any]:
    """
    Generate email template data structure for API response.

    Returned for client to use in email composition UI.
    """
    email_data = generate_email_summary(
        opportunity_title, findings, deadline_info, reviewer_email
    )

    return {
        "subject": email_data["subject"],
        "body": email_data["body"],
        "body_html": email_data["html_body"],
        "mailto_link": generate_mailto_link(
            subject=email_data["subject"],
            body=email_data["body"],
        ),
        "preview": email_data["body"][:200] + "..."  # Preview for UI
    }
