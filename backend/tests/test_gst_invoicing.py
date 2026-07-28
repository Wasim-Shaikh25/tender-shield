"""GST invoicing (R-007, TS-096): gst.py wired into real invoices with tax
columns, gap-free per-FY numbering, credit notes, GSTIN validation, and a
workspace-scoped PDF route. Complements the pure gst.py tests already in
test_hardening.py (which cover the older pre-tax-base `compute_invoice`)."""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.billing.gst import (
    compute_invoice_from_inclusive_total,
    gstin_check_digit,
    validate_gstin,
)
from app.modules.billing.providers.base import OrderHandle
from app.modules.billing.providers.razorpay import RazorpayProvider

SECRET = "dev-razorpay-secret"


# ---- pure: compute_invoice_from_inclusive_total ----------------------------


def test_inclusive_split_intra_state_reconstructs_exactly():
    inv = compute_invoice_from_inclusive_total(
        number="TS/1", total_minor=1_000_000, buyer_gstin="27ABCDE1234F1Z5", seller_state_code="27"
    )
    assert inv.intra_state is True
    names = {line.name for line in inv.lines}
    assert names == {"CGST", "SGST"}
    total = inv.base_minor + sum(line.amount_minor for line in inv.lines) + inv.round_off_minor
    assert total == 1_000_000


def test_inclusive_split_inter_state_reconstructs_exactly():
    inv = compute_invoice_from_inclusive_total(
        number="TS/2", total_minor=1_000_000, buyer_gstin="29ABCDE1234F1Z5", seller_state_code="27"
    )
    assert inv.intra_state is False
    assert [line.name for line in inv.lines] == ["IGST"]
    assert inv.base_minor + inv.lines[0].amount_minor + inv.round_off_minor == 1_000_000


def test_inclusive_split_no_buyer_gstin_is_treated_as_inter_state():
    inv = compute_invoice_from_inclusive_total(
        number="TS/3", total_minor=750_000, buyer_gstin=None, seller_state_code="27"
    )
    assert inv.intra_state is False  # B2C: no input credit, still a valid invoice


def test_inclusive_split_reconstructs_exactly_property():
    """R-007 A6: base + all taxes + round_off == total for many random
    amounts, both intra- and inter-state."""
    seeded_random = random.Random(7)
    for _ in range(1000):
        total = seeded_random.randint(1, 50_000_000)
        buyer_state = seeded_random.choice(["27", "29", "07"])
        gstin = f"{buyer_state}ABCDE1234F1Z5"
        inv = compute_invoice_from_inclusive_total(
            number="TS/x", total_minor=total, buyer_gstin=gstin, seller_state_code="27"
        )
        reconstructed = inv.base_minor + sum(line.amount_minor for line in inv.lines)
        assert reconstructed + inv.round_off_minor == total


# ---- pure: GSTIN validation -------------------------------------------------


def test_gstin_checksum_self_consistent():
    prefix = "27AAPFU0939F1Z"  # state + PAN + entity + fixed 'Z'
    gstin = prefix + gstin_check_digit(prefix)
    assert validate_gstin(gstin) is True


def test_gstin_checksum_rejects_a_corrupted_character():
    prefix = "27AAPFU0939F1Z"
    gstin = prefix + gstin_check_digit(prefix)
    corrupted = gstin[:5] + ("X" if gstin[5] != "X" else "Y") + gstin[6:]
    assert validate_gstin(corrupted) is False


def test_gstin_rejects_bad_format():
    assert validate_gstin("too-short") is False
    assert validate_gstin("99AAPFU0939F1Z5") is False  # invalid state code
    assert validate_gstin("27aapfu0939f1z5") is False  # lowercase PAN


# ---- integration ------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    app = create_app(
        Settings(
            enabled_modules="health,auth,billing",
            database_url="sqlite:///:memory:",
            razorpay_key_id="rzp_test_fake",
            razorpay_key_secret="fake_secret",
            razorpay_webhook_secret=SECRET,
            seller_gstin="27AAAAA0000A1Z5",
            seller_state_code="27",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))

    def fake_create_order(self, req):
        return OrderHandle(
            provider="razorpay",
            order_id=f"order_{req.idempotency_key[:16]}",
            amount_minor=req.amount_minor,
            currency=req.currency,
            checkout_payload={"key": self._key_id, "amount": req.amount_minor},
        )

    monkeypatch.setattr(RazorpayProvider, "create_order", fake_create_order)
    return TestClient(app)


def _auth(client, email="gst@x.com"):
    client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "hunter2hunter2"})
    return {"authorization": f"Bearer {r.json()['access_token']}"}, r.json()["workspace_id"]


def _signed(body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig


def _pay(client, headers, *, kind="paygo", plan=None, opportunity_id=None, event_id="evt_1"):
    body = {"kind": kind}
    if plan:
        body["plan"] = plan
    if opportunity_id:
        body["opportunity_id"] = opportunity_id
    checkout = client.post("/api/billing/checkout", json=body, headers=headers).json()
    event_body = {
        "id": event_id,
        "event": "order.paid" if kind == "paygo" else "subscription.activated",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "notes": {"intent_id": checkout["intent_id"]},
                }
            }
        },
    }
    raw, sig = _signed(event_body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text
    return checkout


def test_set_billing_details_rejects_invalid_gstin(client):
    headers, _ = _auth(client)
    r = client.put(
        "/api/billing/details",
        json={"gstin": "not-a-real-gstin"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_gstin"


def test_set_billing_details_accepts_a_valid_gstin(client):
    headers, _ = _auth(client)
    prefix = "29AAPFU0939F1Z"
    gstin = prefix + gstin_check_digit(prefix)
    r = client.put(
        "/api/billing/details",
        json={"legal_name": "Acme Infra Pvt Ltd", "gstin": gstin, "place_of_supply": "29"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    status_before = client.get("/api/billing/status", headers=headers)
    assert status_before.status_code == 200

    checkout = _pay(client, headers, opportunity_id=str(uuid.uuid4()))
    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    assert invoices[0]["igst_minor"] > 0  # buyer state 29 vs seller state 27 -> inter-state
    assert invoices[0]["amount_minor"] == checkout["amount_minor"]


def test_invoice_numbers_are_gap_free_within_a_fy(client):
    headers, _ = _auth(client)
    numbers = []
    for i in range(3):
        _pay(client, headers, opportunity_id=str(uuid.uuid4()), event_id=f"evt_seq_{i}")
        invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
        numbers.append(sorted(inv["invoice_number"] for inv in invoices)[-1])
    seqs = [int(n.rsplit("/", 1)[1]) for n in numbers]
    assert seqs == sorted(seqs)
    assert seqs[-1] - seqs[0] == len(seqs) - 1  # consecutive, no gaps


def test_refund_issues_a_credit_note_against_the_original_invoice(client):
    headers, workspace_id = _auth(client)
    checkout = _pay(client, headers, kind="subscription", plan="pro", event_id="evt_sub_activate")
    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    original = next(i for i in invoices if i["doc_type"] == "invoice")

    body = {
        "id": "evt_refund",
        "event": "refund.processed",
        "payload": {
            "payment": {
                "entity": {
                    "amount": checkout["amount_minor"],
                    "notes": {"intent_id": checkout["intent_id"]},
                }
            }
        },
    }
    raw, sig = _signed(body)
    r = client.post(
        "/api/billing/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig}
    )
    assert r.status_code == 200, r.text

    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    credit_notes = [i for i in invoices if i["doc_type"] == "credit_note"]
    assert len(credit_notes) == 1
    assert credit_notes[0]["amount_minor"] == original["amount_minor"]


def test_invoice_pdf_downloads_for_the_owning_workspace(client):
    headers, _ = _auth(client)
    _pay(client, headers, opportunity_id=str(uuid.uuid4()))
    invoices = client.get("/api/billing/invoices", headers=headers).json()["invoices"]
    inv_id = invoices[0]["id"]
    r = client.get(f"/api/billing/invoices/{inv_id}/pdf", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_invoice_pdf_hides_another_workspaces_invoice(client):
    headers_a, _ = _auth(client, "ownera@x.com")
    _pay(client, headers_a, opportunity_id=str(uuid.uuid4()))
    inv_id = client.get("/api/billing/invoices", headers=headers_a).json()["invoices"][0]["id"]

    headers_b, _ = _auth(client, "ownerb@x.com")
    r = client.get(f"/api/billing/invoices/{inv_id}/pdf", headers=headers_b)
    assert r.status_code == 404
