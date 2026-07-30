#!/usr/bin/env python3
"""Task tracker for tasks/backlog.md.

Parses the backlog, validates its integrity, and reports progress — including
which tasks are still incomplete and which phase they belong to.

Usage:
    python scripts/task_tracker.py                  # summary by phase
    python scripts/task_tracker.py --incomplete     # every unfinished task
    python scripts/task_tracker.py --phase 16       # filter to one phase
    python scripts/task_tracker.py --validate       # strict; exit 1 on any error
    python scripts/task_tracker.py --json           # machine-readable

Validation rules (CLAUDE.md §1):
  * every task row has a unique ID
  * status is exactly one of: todo | in-progress | blocked | done
  * rows are well-formed 5-column markdown table rows
  * paths referenced by a *done* task must exist on disk
  * task IDs cited in tasks/*_tracker.md must exist in the backlog

Exit codes: 0 = clean, 1 = validation errors (only with --validate).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKLOG = REPO / "tasks" / "backlog.md"
TRACKER_GLOB = "tasks/*tracker*.md"

VALID_STATUS = ("todo", "in-progress", "blocked", "done")
INCOMPLETE_STATUS = ("todo", "in-progress", "blocked")

ROW_RE = re.compile(r"^\|+\s*\**\s*(TS-\d+[a-z]?)\s*\**\s*\|")
ID_RE = re.compile(r"TS-\d+[a-z]?")
H2_RE = re.compile(r"^##\s+(?!#)(.*)$")
H3_RE = re.compile(r"^###\s+(.*)$")
PATH_RE = re.compile(r"`([^`]+)`")


@dataclass
class Task:
    id: str
    title: str
    req: str
    spec: str
    status: str
    line: int
    section: str          # nearest heading (h3 subsection if present, else h2)
    phase_heading: str    # nearest h2, which is where the phase name lives

    @property
    def phase(self) -> str:
        m = re.search(r"Phase\s+([0-9]+(?:\.[0-9]+)?)", self.phase_heading)
        if m:
            return m.group(1)
        head = self.phase_heading.lower()
        if "bootstrap" in head:
            return "0"
        if "audit" in head:
            return "audit"
        return "unphased"

    @property
    def done(self) -> bool:
        return self.status == "done"


@dataclass
class Report:
    tasks: list[Task] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_backlog(path: Path = BACKLOG) -> Report:
    rep = Report()
    if not path.exists():
        rep.errors.append(f"backlog not found: {path}")
        return rep

    phase_heading = "(preamble)"
    section = "(preamble)"
    seen: dict[str, int] = {}

    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        h2 = H2_RE.match(raw)
        if h2:
            phase_heading = section = h2.group(1).strip()
            continue
        h3 = H3_RE.match(raw)
        if h3:
            section = h3.group(1).strip()
            continue

        if not ROW_RE.match(raw):
            continue

        if raw.startswith("||"):
            rep.errors.append(
                f"{path.name}:{lineno} malformed row — starts with '||' "
                f"(breaks table rendering)"
            )

        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) != 5:
            rep.errors.append(
                f"{path.name}:{lineno} expected 5 columns, found {len(cells)}"
            )
            continue

        task_id = ID_RE.search(cells[0])
        if not task_id:
            rep.errors.append(f"{path.name}:{lineno} unparseable task id: {cells[0]!r}")
            continue
        tid = task_id.group(0)

        if tid in seen:
            rep.errors.append(
                f"{path.name}:{lineno} duplicate id {tid} (first seen line {seen[tid]})"
            )
        seen[tid] = lineno

        status = cells[4].lower().strip()
        if status not in VALID_STATUS:
            rep.errors.append(
                f"{path.name}:{lineno} {tid} invalid status {cells[4]!r} — "
                f"must be one of {', '.join(VALID_STATUS)}"
            )

        rep.tasks.append(
            Task(
                id=tid,
                title=cells[1],
                req=cells[2],
                spec=cells[3],
                status=status,
                line=lineno,
                section=section,
                phase_heading=phase_heading,
            )
        )

    return rep


def check_paths(rep: Report) -> None:
    """A done task must not reference a path that does not exist."""
    for t in rep.tasks:
        if not t.done:
            continue
        for candidate in PATH_RE.findall(t.spec):
            candidate = candidate.split()[0].rstrip(",")
            if candidate.startswith("http") or candidate in {"—", "-"}:
                continue
            if "/" not in candidate and not candidate.endswith((".md", ".py")):
                continue
            target = REPO / candidate
            if target.exists():
                continue
            # tolerate directory prefixes written loosely (e.g. "tests/x.py")
            if list(REPO.glob(f"**/{candidate}")):
                continue
            rep.warnings.append(
                f"{t.id} (done) references missing path: {candidate}"
            )


def check_trackers(rep: Report) -> None:
    """Every TS- id cited in a tracker must exist in the backlog."""
    known = {t.id for t in rep.tasks}
    for tracker in sorted(REPO.glob(TRACKER_GLOB)):
        cited = set(ID_RE.findall(tracker.read_text()))
        for tid in sorted(cited - known):
            rep.errors.append(
                f"{tracker.relative_to(REPO)} cites unknown task {tid}"
            )


def phase_summary(tasks: list[Task]) -> list[tuple[str, dict]]:
    buckets: dict[str, dict] = {}
    for t in tasks:
        b = buckets.setdefault(
            t.phase, {"total": 0, "done": 0, "todo": 0, "in-progress": 0, "blocked": 0}
        )
        b["total"] += 1
        if t.status in b:
            b[t.status] += 1

    def sort_key(item):
        key = item[0]
        try:
            return (0, float(key))
        except ValueError:
            return (1, 0.0)

    return sorted(buckets.items(), key=sort_key)


def bar(done: int, total: int, width: int = 24) -> str:
    filled = 0 if not total else round(width * done / total)
    return "█" * filled + "░" * (width - filled)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--incomplete", action="store_true", help="list unfinished tasks")
    ap.add_argument("--phase", help="filter to one phase, e.g. 16")
    ap.add_argument("--validate", action="store_true", help="exit 1 on validation errors")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    rep = parse_backlog()
    check_paths(rep)
    check_trackers(rep)

    tasks = rep.tasks
    if args.phase:
        tasks = [t for t in tasks if t.phase == args.phase]

    if args.json:
        print(
            json.dumps(
                {
                    "total": len(tasks),
                    "done": sum(t.done for t in tasks),
                    "incomplete": [
                        {
                            "id": t.id,
                            "phase": t.phase,
                            "status": t.status,
                            "title": t.title,
                        }
                        for t in tasks
                        if t.status in INCOMPLETE_STATUS
                    ],
                    "errors": rep.errors,
                    "warnings": rep.warnings,
                },
                indent=2,
            )
        )
        return 1 if (args.validate and rep.errors) else 0

    total = len(tasks)
    done = sum(t.done for t in tasks)
    print(f"\nTenderShield task tracker — {BACKLOG.relative_to(REPO)}")
    print("=" * 72)
    print(f"{'PHASE':<10}{'DONE':>6}{'TOTAL':>7}  PROGRESS")
    print("-" * 72)
    for phase, b in phase_summary(tasks):
        pct = 0 if not b["total"] else 100 * b["done"] // b["total"]
        extra = ""
        if b["in-progress"]:
            extra += f"  {b['in-progress']} in-progress"
        if b["blocked"]:
            extra += f"  {b['blocked']} blocked"
        print(
            f"{'Phase ' + phase:<10}{b['done']:>6}{b['total']:>7}  "
            f"{bar(b['done'], b['total'])} {pct:>3}%{extra}"
        )
    print("-" * 72)
    pct = 0 if not total else 100 * done // total
    print(f"{'ALL':<10}{done:>6}{total:>7}  {bar(done, total)} {pct:>3}%")

    incomplete = [t for t in tasks if t.status in INCOMPLETE_STATUS]
    blocked = [t for t in incomplete if t.status == "blocked"]
    inprog = [t for t in incomplete if t.status == "in-progress"]

    print(f"\nIncomplete: {len(incomplete)}  (in-progress {len(inprog)}, blocked {len(blocked)})")

    if blocked:
        print("\nBLOCKED:")
        for t in blocked:
            print(f"  {t.id}  {t.title[:90]}")
    if inprog:
        print("\nIN PROGRESS:")
        for t in inprog:
            print(f"  {t.id}  {t.title[:90]}")

    if args.incomplete:
        print("\nALL INCOMPLETE TASKS:")
        current = None
        for t in incomplete:
            if t.section != current:
                current = t.section
                print(f"\n  ── {current}")
            print(f"    [{t.status:<11}] {t.id}  {t.title[:80]}")

    if rep.warnings:
        print(f"\nWARNINGS ({len(rep.warnings)}):")
        for w in rep.warnings:
            print(f"  ! {w}")

    if rep.errors:
        print(f"\nERRORS ({len(rep.errors)}):")
        for e in rep.errors:
            print(f"  ✗ {e}")
    else:
        print("\nValidation: clean ✓")

    print()
    return 1 if (args.validate and rep.errors) else 0


if __name__ == "__main__":
    sys.exit(main())
