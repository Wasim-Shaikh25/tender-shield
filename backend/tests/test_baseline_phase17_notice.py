"""Unit tests for notice register enrichment (TS-238)."""

from datetime import date, timedelta

from app.modules.baseline.notice_register import compute_deadline, enrich_rule, infer_trigger_event


def test_infer_trigger_event_classifies_milestone():
    assert infer_trigger_event("after practical completion of the works") == "milestone"
    assert infer_trigger_event("within 14 days of breach") == "event"


def test_compute_deadline_adds_days_to_confirmed_milestone():
    milestone = date(2026, 6, 1)
    result = compute_deadline(
        deadline_days=14,
        trigger_event="milestone",
        notice_type="claim",
        deadlines=[
            {
                "kind": "practical_completion",
                "due_at": milestone.isoformat(),
                "confirmed": True,
            }
        ],
    )
    assert result["deadline_unknown"] is False
    assert result["notice_deadline"] == (milestone + timedelta(days=14)).isoformat()


def test_enrich_rule_attaches_contact_without_inventing_defaults():
    rule = {
        "days": 28,
        "unit_raw": "days",
        "trigger": "claim within 28 days after practical completion",
        "category": "claim",
        "source_quote": "28 days",
        "source_page": 3,
    }

    class Contact:
        party = "employer"
        role_label = "Engineer"
        authorized_representative = "A. Engineer"
        postal_address = "Site office"
        email = "eng@example.com"
        required_content = ["Written claim notice"]

    enriched = enrich_rule(
        rule,
        categories=[{"key": "claim", "label": "Claim"}],
        contacts={"claim": Contact()},
        deadlines=[],
    )
    assert enriched["notice_type"] == "claim"
    assert enriched["authorized_representative"] == "A. Engineer"
    assert enriched["correspondence"]["email"] == "eng@example.com"
    assert enriched["required_content"] == ["Written claim notice"]
