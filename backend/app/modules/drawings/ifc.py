"""Lightweight IFC-SPF quantity extraction for drawing/model quantities (TS-326).

This is intentionally not a full geometry engine. It parses the STEP physical file
header/data section, extracts building element occurrences and linked quantity /
property values, and returns candidate BOQ lines and schedule activities with
`confidence: low` / `verify_manually` flags.
"""

from __future__ import annotations

import re
from collections import defaultdict

# IFC entity supertypes commonly found in building models.
_BUILDING_ELEMENT_TYPES = {
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCCURTAINWALL",
    "IFCDOOR",
    "IFCWINDOW",
    "IFCROOF",
    "IFCSLAB",
    "IFCCOLUMN",
    "IFCBEAM",
    "IFCPLATE",
    "IFCMEMBER",
    "IFCFOOTING",
    "IFCRAMP",
    "IFCSTAIR",
    "IFCBUILDINGELEMENTPROXY",
    "IFCCOVERING",
    "IFCFURNISHINGELEMENT",
    "IFCDISTRIBUTIONELEMENT",
    "IFCDISTRIBUTIONFLOWELEMENT",
}

_QUANTITY_NAMES = {
    "netvolume": "m3",
    "grossvolume": "m3",
    "netarea": "m2",
    "grossarea": "m2",
    "netlength": "m",
    "grosslength": "m",
    "length": "m",
    "width": "m",
    "height": "m",
    "depth": "m",
    "area": "m2",
    "volume": "m3",
    "count": "no",
}


def _split_step_args(raw: str) -> list[str]:
    """Split comma-separated STEP arguments while respecting single-quoted strings."""
    args: list[str] = []
    current = []
    in_quote = False
    for ch in raw:
        if ch == "'":
            in_quote = not in_quote
            current.append(ch)
        elif ch == "," and not in_quote:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current or raw.endswith(","):
        args.append("".join(current).strip())
    return args


def _parse_number(value: str) -> float | None:
    value = value.strip().strip("'")
    if not value:
        return None
    try:
        # STEP puts $ for null and * for derived.
        if value in ("$", "*"):
            return None
        # Some values include the unit suffix, e.g. "12.5".
        return float(value)
    except ValueError:
        return None


def _clean_name(value: str) -> str:
    return value.strip().strip("'").replace("'", "")


def extract_ifc_quantities(ifc_text: str) -> dict:
    """Return candidate BOQ lines and schedule activities from an IFC-SPF string."""
    if not ifc_text:
        return {"boq_candidates": [], "activity_candidates": [], "note": "empty_input"}

    # Find DATA section; ignore HEADER.
    data_match = re.search(r"DATA;(.*?)ENDSEC;", ifc_text, re.S | re.I)
    body = data_match.group(1) if data_match else ifc_text

    elements: dict[str, dict] = {}
    quantities: dict[str, dict[str, float]] = defaultdict(dict)
    property_sets: dict[str, dict[str, str]] = defaultdict(dict)
    quantity_values: dict[str, float] = {}
    rel_props: dict[str, list[str]] = {}
    rel_quantities: dict[str, list[str]] = {}
    type_counts: dict[str, int] = defaultdict(int)
    type_names: dict[str, str] = {}

    for line in body.splitlines():
        line = line.strip()
        if not line or not line.startswith("#"):
            continue
        m = re.match(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;", line, re.IGNORECASE)
        if not m:
            continue
        ref = f"#{m.group(1)}"
        entity = m.group(2).upper()
        raw_args = m.group(3)
        args = _split_step_args(raw_args)

        if entity == "IFCPROPERTYSINGLEVALUE" and len(args) >= 3:
            name = _clean_name(args[0]).lower()
            val = _parse_number(args[2])
            if val is not None:
                property_sets[ref][name] = val

        if entity == "IFCPROPERTYSET" and len(args) >= 5:
            # Arguments: GlobalId, OwnerHistory, Name, Description, HasProperties
            has_props = args[4] if len(args) > 4 else ""
            for token in re.findall(r"#\d+", has_props):
                rel_props.setdefault(ref, []).append(token)

        if entity == "IFCELEMENTQUANTITY" and len(args) >= 5:
            qty_refs = args[4] if len(args) > 4 else ""
            rel_quantities.setdefault(ref, []).extend(re.findall(r"#\d+", qty_refs))

        if entity == "IFCQUANTITYLENGTH" and len(args) >= 4:
            name = _clean_name(args[2]).lower()
            val = _parse_number(args[3])
            if val is not None:
                quantity_values[ref] = val
                quantities[ref][name] = val
        if entity == "IFCQUANTITYAREA" and len(args) >= 4:
            name = _clean_name(args[2]).lower()
            val = _parse_number(args[3])
            if val is not None:
                quantity_values[ref] = val
                quantities[ref][name] = val
        if entity == "IFCQUANTITYVOLUME" and len(args) >= 4:
            name = _clean_name(args[2]).lower()
            val = _parse_number(args[3])
            if val is not None:
                quantity_values[ref] = val
                quantities[ref][name] = val
        if entity == "IFCQUANTITYCOUNT" and len(args) >= 4:
            name = _clean_name(args[2]).lower()
            val = _parse_number(args[3])
            if val is not None:
                quantity_values[ref] = val
                quantities[ref][name] = val

        if entity in _BUILDING_ELEMENT_TYPES or (
            entity.startswith("IFC") and entity.endswith("ELEMENT")
        ):
            name = _clean_name(args[2]) if len(args) > 2 else ""
            type_counts[entity] += 1
            elements[ref] = {"type": entity, "name": name}
            type_names[ref] = name

        if entity == "IFCRELDEFINESBYPROPERTIES" and len(args) >= 6:
            related_objects = args[4] if len(args) > 4 else ""
            relating_prop = args[5] if len(args) > 5 else ""
            for obj in re.findall(r"#\d+", related_objects):
                rel_props.setdefault(obj, []).extend(rel_props.get(relating_prop, []))
            for prop in rel_props.get(relating_prop, []):
                for obj in re.findall(r"#\d+", related_objects):
                    rel_props.setdefault(obj, []).append(prop)

    # Aggregate quantities per element type.
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, int] = defaultdict(int)
    for ref, elem in elements.items():
        elem_type = elem["type"]
        counts[elem_type] += 1
        for prop_ref in rel_props.get(ref, []):
            for qty_name, value in quantities.get(prop_ref, {}).items():
                totals[elem_type][qty_name] += value
            if prop_ref in quantity_values:
                # quantity_values maps the quantity itself; find name from quantities
                for qn, val in quantities.get(prop_ref, {}).items():
                    totals[elem_type][qn] += val

    # Also aggregate property sets.
    for ref in elements:
        for prop_ref in rel_props.get(ref, []):
            for name, value in property_sets.get(prop_ref, {}).items():
                unit = _QUANTITY_NAMES.get(name, "")
                if unit and isinstance(value, (int, float)):
                    totals[elements[ref]["type"]][name] += float(value)

    boq_candidates: list[dict] = []
    for elem_type, qtys in totals.items():
        # Pick the single most material-looking quantity for a summary line.
        preferred = [
            "grossvolume", "netvolume", "volume",
            "grossarea", "netarea", "area",
            "grosslength", "netlength", "length", "count",
        ]
        chosen = None
        for p in preferred:
            if p in qtys and qtys[p] > 0:
                chosen = p
                break
        if chosen is None:
            chosen = next(iter(qtys), None)
        if chosen:
            boq_candidates.append({
                "description": f"{elem_type.replace('IFC', '').title()} ({chosen})",
                "classification": elem_type,
                "unit": _QUANTITY_NAMES.get(chosen, ""),
                "quantity": round(qtys[chosen], 4),
                "count": counts.get(elem_type, 0),
                "confidence": "low",
                "verify_manually": True,
            })

    activity_candidates = [
        {
            "source_native_id": ref,
            "name": info["name"] or info["type"].replace("IFC", "").title(),
            "classification": info["type"],
        }
        for ref, info in elements.items()
    ]

    return {
        "boq_candidates": boq_candidates,
        "activity_candidates": activity_candidates[:200],
        "element_count": len(elements),
        "note": (
            "Text/entity parse of IFC-SPF only; quantities are approximate and must be "
            "verified against the modelling software output."
        ),
    }
