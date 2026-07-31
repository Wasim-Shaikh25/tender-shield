#!/usr/bin/env python3
"""Parse PRODUCTION_READINESS_AUDIT.md and build a detailed fix tracker plus
backlog additions for any finding that does not already have a task row.

The tracker is written to tasks/audit_fix_tracker.md.
Backlog additions are written to tasks/backlog.md (new section appended).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "PRODUCTION_READINESS_AUDIT.md"
BACKLOG = REPO / "tasks" / "backlog.md"
TRACKER = REPO / "tasks" / "audit_fix_tracker.md"


def _all_finding_ids(report_text: str) -> list[str]:
    crit = _comma_list(report_text, "Critical")
    high = _comma_list(report_text, "High")
    med = _comma_list(report_text, "Medium")
    low = _comma_list(report_text, "Low")
    return crit + high + med + low


def _comma_list(text: str, severity: str) -> list[str]:
    m = re.search(rf"\*\*{severity}\*\* \| \d+ \| \d+ \| (.*?) \|", text)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",")]


def _find_segments(text: str):
    """Return sorted list of (start, fid, title, kind) for every finding."""
    starts = []
    # headings
    for m in re.finditer(r"(?m)^(#{3,4}) (TS-[A-Z]\d+) — ([^\n]+)$", text):
        starts.append((m.start(), m.group(2), m.group(3).strip(), "heading"))
    # inline bold findings
    for m in re.finditer(r"\*\*(TS-[A-Z]\d+) — ([^*]+)\*\*", text):
        # avoid false positives inside tables (e.g. backlog rows)
        if m.group(1) not in text[m.start():m.start() + 100]:
            continue
        starts.append((m.start(), m.group(1), m.group(2).strip(), "inline"))
    starts.sort(key=lambda x: x[0])
    # dedupe by position/fid; if same fid appears twice, keep the one that looks like a start
    seen = set()
    cleaned = []
    for s, fid, title, kind in starts:
        if fid in seen:
            continue
        seen.add(fid)
        cleaned.append((s, fid, title, kind))
    return cleaned


def _segment_text(text: str, starts: list, idx: int) -> str:
    start = starts[idx][0]
    if idx + 1 < len(starts):
        end = starts[idx + 1][0]
    else:
        end = len(text)
    return text[start:end]


def _parse_meta_table(seg: str) -> dict:
    """Find the metadata table and return key-value pairs."""
    res = {}
    # The table starts right after the heading on the next non-empty line.
    m = re.search(r"\| \*\*([^|]+)\*\* \| ([^|]+) \|", seg)
    if not m:
        return res
    # collect rows until a line that is not a two-column table row
    table = ""
    for line in seg.splitlines():
        if re.match(r"\| \*\*[^|]+\*\* \| .+ \|", line):
            table += line + "\n"
        elif table and not line.startswith("|"):
            break
    for line in table.splitlines():
        m = re.match(r"\| \*\*([^|]+)\*\* \| ([^|]+) \|", line)
        if m:
            k = m.group(1).strip().lower().replace(" ", "_")
            v = m.group(2).strip()
            res[k] = v
    return res


def _extract_field(seg: str, name: str) -> str | None:
    """Extract text under **Name** until next **Field** or end."""
    pat = rf"(?m)^\*\*{re.escape(name)}\*\*[^\n]*\n"
    m = re.search(pat, seg)
    if not m:
        return None
    rest = seg[m.end():]
    # Stop at next bold heading (line starting with **Capital...)
    end_m = re.search(r"(?m)\n(?=\*\*[A-Z])", rest)
    if not end_m:
        end_m = re.search(r"\n---\n", rest)
    if end_m:
        val = rest[: end_m.start()]
    else:
        val = rest
    return val.strip()


def _clean_inline(seg: str, title: str, fid: str) -> dict:
    """Parse an inline/summarised finding block."""
    out = {}
    # Remove the title marker
    body = re.sub(rf"^\*\*{re.escape(fid)} — {re.escape(title)}\*\*\s*", "", seg, flags=re.MULTILINE).strip()
    # italic metadata line: *Status · Severity · `location`*  (may span one line)
    m = re.match(r"\*([^·\n*]+)\s*·\s*([^·\n*]+)\s*·\s*([^*\n]+)\*", body)
    if m:
        out["status"] = m.group(1).strip()
        out["severity"] = m.group(2).strip()
        out["location"] = m.group(3).strip()
        body = body[m.end():].strip()
    # Split body at the first *Fix:* or *Recommendation:* marker
    split_match = re.search(r"(?m)(?:^|\s)\*(?:Fix|Recommendation):\*\s*", body)
    if split_match:
        impact = body[: split_match.start()].strip()
        solution = body[split_match.end():].strip()
    else:
        impact = body
        solution = "TBD — see PRODUCTION_READINESS_AUDIT.md §5/§11/§12 remediation plans."
    # Remove trailing separator lines
    impact = re.sub(r"\n---\n*$", "", impact).strip()
    solution = re.sub(r"\n---\n*$", "", solution).strip()
    out["impact"] = impact
    out["recommended_solution"] = solution
    out["root_cause"] = impact.split("\n")[0][:200]
    return out


def _parse_segment(seg: str, kind: str, title: str, fid: str) -> dict:
    out = {"title": title, "kind": kind}
    if kind == "heading":
        meta = _parse_meta_table(seg)
        out.update(meta)
        for field in ["Location", "Evidence", "Root cause", "Impact", "Recommended solution", "Regression risks", "Tests to add", "Similar locations"]:
            val = _extract_field(seg, field)
            if val:
                out[field.lower().replace(" ", "_")] = val
    else:
        out.update(_clean_inline(seg, title, fid))
    # Normalise keys
    for k in list(out.keys()):
        out[k] = (out[k] or "").strip()
    return out


def _existing_task_map() -> dict[str, list[str]]:
    text = BACKLOG.read_text()
    rows = re.findall(r"\|\s*(TS-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|", text)
    mapping: dict = {}
    for tid, _, ref, _, _ in rows:
        for f in re.findall(r"TS-[A-Z]\d+", ref):
            mapping.setdefault(f, []).append(tid)
    return mapping


def _module_for_fid(fid: str) -> str:
    # Specific overrides based on which module actually owns the affected code/behavior.
    specific = {
        "TS-A01": "auth", "TS-A02": "auth", "TS-A03": "data-model", "TS-A04": "auth",
        "TS-A05": "auth", "TS-A06": "auth", "TS-A07": "auth", "TS-A08": "auth",
        "TS-A09": "auth", "TS-A10": "auth", "TS-A11": "crossref", "TS-A13": "assistant",
        "TS-A14": "assistant", "TS-A15": "review", "TS-A16": "review", "TS-A17": "auth",
        "TS-B01": "billing", "TS-B02": "billing", "TS-B03": "billing", "TS-B05": "baseline",
        "TS-B06": "billing", "TS-B07": "billing", "TS-B08": "billing",
        "TS-C01": "findings",
        "TS-D02": "timeline", "TS-D03": "timeline",
        "TS-F01": "frontend", "TS-F02": "frontend",
        "TS-I01": "ingestion", "TS-I02": "ingestion", "TS-I03": "ingestion", "TS-I04": "ingestion",
        "TS-I05": "ingestion", "TS-I06": "ingestion", "TS-I07": "ingestion", "TS-I08": "ingestion",
        "TS-I09": "ingestion", "TS-I10": "ingestion",
        "TS-L01": "core", "TS-L02": "core", "TS-L03": "frontend", "TS-L04": "core",
        "TS-N01": "notifications", "TS-N02": "notifications",
        "TS-O01": "core", "TS-O02": "health", "TS-O03": "core", "TS-O04": "deployment",
        "TS-O05": "core",
        "TS-P01": "assistant", "TS-P02": "rulepacks",
        "TS-Q01": "qualification",
        "TS-R01": "risk", "TS-R02": "risk", "TS-R03": "risk",
        "TS-S01": "ingestion", "TS-S02": "core", "TS-S03": "ingestion", "TS-S04": "ingestion",
        "TS-X01": "data-model", "TS-X02": "boq",
    }
    if fid in specific:
        mod = specific[fid]
    else:
        prefix_map = {
            "TS-A": "auth", "TS-B": "billing", "TS-I": "ingestion",
            "TS-O": "core", "TS-F": "frontend", "TS-R": "risk",
            "TS-D": "drafting", "TS-Q": "qualification", "TS-X": "data-model",
            "TS-S": "ingestion", "TS-N": "notifications", "TS-P": "rulepacks",
            "TS-L": "core", "TS-C": "findings",
        }
        mod = next((v for k, v in prefix_map.items() if fid.startswith(k)), "core")
    if mod == "frontend":
        return "specs/frontend.md"
    return f"specs/modules/{mod}.md"


def _task_title(fid: str, info: dict) -> str:
    title = info.get("title", "")
    # Remove backticks and shorten
    title = title.replace("`", "").strip()
    # Capitalise first letter
    if title:
        title = title[0].upper() + title[1:]
    return title


def main() -> None:
    report_text = REPORT.read_text()
    all_ids = _all_finding_ids(report_text)
    starts = _find_segments(report_text)
    by_id = {fid: (pos, title, kind) for pos, fid, title, kind in starts}

    mapping = _existing_task_map()
    new_tasks = []
    findings = []

    next_id_num = 133
    for fid in all_ids:
        if fid not in by_id:
            # Skip product-only gaps not described as findings
            info = {"title": "(description in report body)", "kind": "inline"}
        else:
            pos, title, kind = by_id[fid]
            idx = [i for i, s in enumerate(starts) if s[1] == fid][0]
            seg = _segment_text(report_text, starts, idx)
            info = _parse_segment(seg, kind, title, fid)
        tasks = mapping.get(fid, [])
        if not tasks:
            new_tid = f"TS-{next_id_num:03d}"
            next_id_num += 1
            tasks = [new_tid]
            new_tasks.append((new_tid, fid, info))
        findings.append({"id": fid, **info, "tasks": tasks})

    # Build tracker markdown
    lines = [
        "# Audit Fix Tracker",
        "",
        "Generated from `PRODUCTION_READINESS_AUDIT.md`. Maps every `TS-*` finding to a",
        "requirement, recommended solution, and task ID.",
        "",
        "| # | ID | Title | Severity | Release-blocking | Task ID(s) |",
        "|---|---|---|---|---|---|",
    ]
    for i, f in enumerate(findings, 1):
        rb = f.get("release-blocking", "No")
        sev = f.get("severity", "—")
        title = (f.get("title") or "").replace("|", "\\|")
        lines.append(f"| {i} | {f['id']} | {title} | {sev} | {rb} | {', '.join(f['tasks'])} |")
    lines.extend(["", "---", ""])

    for f in findings:
        lines.extend([
            f"## {f['id']} — {f.get('title', '')}",
            "",
            f"**Severity:** {f.get('severity', '—')}  ",
            f"**Release-blocking:** {f.get('release-blocking', 'No')}  ",
            f"**Task ID(s):** {', '.join(f['tasks'])}  ",
        ])
        if f.get("location"):
            lines.append(f"**Location:** {f['location']}  ")
        if f.get("status"):
            lines.append(f"**Status:** {f['status']}  ")
        lines.append("")
        if f.get("impact"):
            lines.extend(["### Requirement / Impact", "", f["impact"], ""])
        if f.get("root_cause") and f.get("root_cause") != f.get("impact", ""):
            lines.extend(["### Root cause", "", f["root_cause"], ""])
        if f.get("evidence"):
            lines.extend(["### Evidence", "", f["evidence"], ""])
        if f.get("recommended_solution"):
            lines.extend(["### Recommended solution", "", f["recommended_solution"], ""])
        if f.get("regression_risks"):
            lines.extend(["### Regression risks", "", f["regression_risks"], ""])
        if f.get("tests_to_add"):
            lines.extend(["### Tests to add", "", f["tests_to_add"], ""])
        if f.get("similar_locations"):
            lines.extend(["### Similar locations", "", f["similar_locations"], ""])
        lines.append("")

    TRACKER.write_text("\n".join(lines))

    # Backlog additions
    if new_tasks:
        backlog_lines = [
            "",
            "## Post-audit implementation tasks (generated from 61-finding tracker)",
            "",
            "| ID | Title | Req ref | Spec | Status |",
            "|---|---|---|---|---|",
        ]
        for new_tid, fid, info in new_tasks:
            mod = _module_for_fid(fid)
            title = _task_title(fid, info)
            ref = f"audit {fid}; `PRODUCTION_READINESS_AUDIT.md`"
            spec = f"`specs/modules/{mod}.md` (update)"
            backlog_lines.append(f"| {new_tid} | {title} | {ref} | {spec} | todo |")
        with BACKLOG.open("a") as bf:
            bf.write("\n".join(backlog_lines) + "\n")

    print(f"Tracker written to {TRACKER}")
    print(f"Backlog updated with {len(new_tasks)} new task rows")
    if new_tasks:
        print(f"New task IDs: {new_tasks[0][0]} .. {new_tasks[-1][0]}")


if __name__ == "__main__":
    main()
