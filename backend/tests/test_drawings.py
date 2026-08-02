"""Drawing intelligence Phase 22 tests (TS-321–TS-326)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = "health,rulepacks,auth,ingestion,drawings"


def _pdf_bytes(text: str, pages: int = 1) -> bytes:
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=(595, 842))
    for i in range(pages):
        y = 700
        for line in text.split("\n"):
            c.drawString(72, y, line)
            y -= 14
        if i < pages - 1:
            c.showPage()
    c.save()
    return bio.getvalue()


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "drawings@x.com")


def _opp(client, headers):
    r = client.post(
        "/api/ingestion/opportunities", json={"title": "Drawing OPP"}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_drawing(client, headers, opp_id, **fields):
    r = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings",
        json=fields,
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_drawing_register_and_title_block_ts321(client):
    """TS-321: create drawing with title block fields and list it."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    drawing = _create_drawing(
        client,
        headers,
        opp_id,
        filename="foundation.pdf",
        drawing_number="D-101",
        title="Foundation Plan",
        revision="A",
        revision_date="15/08/2026",
        discipline="Civil",
    )
    assert drawing["drawing_number"] == "D-101"
    assert drawing["title"] == "Foundation Plan"
    assert drawing["discipline"] == "Civil"

    listed = client.get(
        f"/api/drawings/opportunities/{opp_id}/drawings", headers=headers
    ).json()
    assert len(listed["drawings"]) == 1


def test_drawing_upload_extracts_title_block_ts321(client):
    """TS-321: upload a PDF and extract title-block metadata."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    drawing = _create_drawing(client, headers, opp_id, filename="site_plan.pdf")
    text = (
        "Drawing No: D-202\nTitle: Site Plan\nRevision: B\n"
        "Date: 20/08/2026\nDiscipline: Architecture"
    )
    data = _pdf_bytes(text)
    r = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/upload",
        files={"file": ("site_plan.pdf", data, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["drawing_number"] == "D-202"
    assert body["title"] == "Site Plan"
    assert body["revision"] == "B"
    assert body["discipline"] == "Architecture"


def test_drawing_superseded_and_compare_ts322(client):
    """TS-322: supersede one drawing with another and compare pages."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    prev = _create_drawing(client, headers, opp_id, filename="rev_a.pdf")
    cur = _create_drawing(client, headers, opp_id, filename="rev_b.pdf")

    # Upload text to both; the second drawing compares the PDF pages.
    client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{prev['id']}/upload",
        files={"file": ("rev_a.pdf", _pdf_bytes("Original scope"), "application/pdf")},
        headers=headers,
    )
    client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{cur['id']}/upload",
        files={"file": ("rev_b.pdf", _pdf_bytes("Revised scope"), "application/pdf")},
        headers=headers,
    )

    r = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{cur['id']}/supersedes/{prev['id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["supersedes_id"] == prev["id"]

    comp = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{cur['id']}/compare/{prev['id']}",
        headers=headers,
    ).json()
    assert comp["current_drawing_id"] == cur["id"]
    assert comp["previous_drawing_id"] == prev["id"]
    assert len(comp["changed_pages"]) > 0


def test_symbol_assist_and_heatmap_ts323_ts325(client):
    """TS-323/TS-325: symbol counts and confidence heatmap from extracted text."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    drawing = _create_drawing(client, headers, opp_id, filename="electrical.pdf")
    text = "Lighting layout. WD WP MCB SP Fan Light Switch"
    client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/upload",
        files={"file": ("electrical.pdf", _pdf_bytes(text), "application/pdf")},
        headers=headers,
    )

    assist = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/symbol-assist",
        headers=headers,
    ).json()
    assert assist["totals"]["Light"] >= 1

    heat = client.get(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/heatmap",
        headers=headers,
    ).json()
    assert heat["overall_confidence"] > 0


def test_boq_link_and_list_ts324(client):
    """TS-324: link a drawing region to a BOQ line and list links."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    drawing = _create_drawing(client, headers, opp_id, filename="mep.pdf")
    client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/link-boq",
        json={
            "page": 1,
            "region": "header",
            "description": "LED light fixtures",
            "unit": "no",
            "qty": 12,
            "source_quote": "WD WP MCB",
        },
        headers=headers,
    )
    links = client.get(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/boq-links",
        headers=headers,
    ).json()
    assert len(links["links"]) == 1
    assert links["links"][0]["description"] == "LED light fixtures"


def test_ifc_quantity_extraction_ts326(client):
    """TS-326: parse IFC-SPF and return candidate BOQ lines."""
    headers = _auth(client)
    opp_id = _opp(client, headers)
    drawing = _create_drawing(client, headers, opp_id, filename="model.ifc")
    ifc_text = """ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1 = IFCWALL (#10, 'Wall', $, $, $, $, $, $, 'Standard');
#2 = IFCPROPERTYSINGLEVALUE ('netvolume', $, '12.5', $);
#3 = IFCPROPERTYSET ($, $, 'BaseQuantities', $, (#2));
#4 = IFCRELDEFINESBYPROPERTIES ($, $, $, $, (#1), #3);
ENDSEC;
END-ISO-10303-21;
"""
    r = client.post(
        f"/api/drawings/opportunities/{opp_id}/drawings/{drawing['id']}/ifc-quantities",
        files={"file": ("model.ifc", ifc_text.encode(), "application/x-step")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["element_count"] >= 1
    assert any("Wall" in c["description"] for c in body["boq_candidates"])
