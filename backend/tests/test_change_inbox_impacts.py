"""Unit tests for inbox and impact helpers (TS-248, TS-249)."""

import pytest

from app.modules.change.impacts import compute_impact_exposure, validate_impact_links
from app.modules.change.inbox import sort_inbox


def test_sort_inbox_orders_by_confidence_then_recency():
    events = [
        {"confidence_band": "low", "created_at": "2026-08-01T10:00:00+00:00"},
        {"confidence_band": "high", "created_at": "2026-08-01T09:00:00+00:00"},
        {"confidence_band": "high", "created_at": "2026-08-01T11:00:00+00:00"},
    ]
    ordered = sort_inbox(events)
    assert ordered[0]["confidence_band"] == "high"
    assert ordered[0]["created_at"].endswith("11:00:00+00:00")
    assert ordered[-1]["confidence_band"] == "low"


def test_validate_impact_links_rejects_unknown_cost_code():
    with pytest.raises(ValueError, match="invalid_cost_code"):
        validate_impact_links(
            {
                "cost_code_ids": ["missing"],
                "finding_ids": [],
                "boq_src_rows": [],
                "subcontract_refs": [],
            },
            valid_cost_code_ids={"known"},
            valid_finding_ids=set(),
        )


class _Finding:
    def __init__(self, amount):
        self.amount_exposure = amount
        self.currency = "INR"


def test_compute_impact_exposure_sums_minor_units():
    links = {
        "finding_ids": ["f1", "f2"],
        "cost_code_ids": [],
        "boq_src_rows": [],
        "subcontract_refs": [],
    }
    summary = compute_impact_exposure(
        links,
        {"f1": _Finding(100_00), "f2": _Finding(50_00)},
    )
    assert summary["total_minor"] == 150_00
