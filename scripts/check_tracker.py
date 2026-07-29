#!/usr/bin/env python3
"""Parses tasks/TRACKER.md and reports what's done vs. left — the single
source of truth for task status (CLAUDE.md §1, .cursor/rules/20-specs-tasks.mdc,
.devin/rules/20-specs-tasks.mdc).

For every task row it finds (first cell matching TS-###), it:
  - counts statuses (todo | in-progress | blocked | done),
  - verifies the "Task file" and "Requirement" columns link to real files
    when they contain a markdown link (plain-text refs like "Doc §5" are
    left alone),
  - flags duplicate task IDs and unrecognized status values.

A row with no task file yet is NOT an error — it's the backlog. The retrofit
task list. Only broken links, duplicate IDs, and bad status values fail the
exit code.

Usage:
    python scripts/check_tracker.py          # report only
    python scripts/check_tracker.py --fix    # also rewrite the summary block
                                              # between the STATUS markers
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKER = REPO_ROOT / "tasks" / "TRACKER.md"

STATUSES = {"todo", "in-progress", "blocked", "done"}
TASK_ID_RE = re.compile(r"^TS-\d+[a-z]?$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def normalize_status(raw: str) -> str:
    """'done¹²' -> 'done'; 'todo (needs creds)' -> 'todo'; the footnote
    marker / parenthetical annotation is real content (carried over from the
    tracker narrative) and stays in the row for a human to read — the
    checker only needs the bare status word to bucket and validate it."""
    s = raw.replace("**", "").strip()
    while s and s[-1] in SUPERSCRIPT_DIGITS:
        s = s[:-1]
    s = s.strip()
    first = s.split(" ", 1)[0].split("(", 1)[0].strip()
    return first or s


def split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def is_separator(line: str) -> bool:
    s = line.strip()
    return bool(s) and "-" in s and bool(re.match(r"^\|?[\s:|-]+\|?$", s))


def resolve_link(cell: str, base_dir: Path) -> tuple[bool, str]:
    """(ok, target). ok=True when the cell is empty/dash, or a markdown link
    whose target resolves to a real file relative to tasks/. Plain text
    (no markdown link syntax) is left alone — not every reference is a link
    (pre-R-doc tasks cite a Build Doc section as text)."""
    cell = cell.strip()
    if cell in ("—", "-", ""):
        return True, ""
    m = LINK_RE.search(cell)
    if not m:
        return True, ""
    target = m.group(1).split("#")[0]
    return (base_dir / target).resolve().is_file(), target


def parse_tasks(text: str) -> list[dict]:
    lines = text.splitlines()
    tasks: list[dict] = []
    header: list[str] | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            header = [c.lower() for c in split_row(line)]
            i += 2
            continue
        if header and line.strip().startswith("|"):
            cells = split_row(line)
            if len(cells) == len(header) and TASK_ID_RE.match(cells[0]):
                tasks.append(dict(zip(header, cells, strict=True)))
            i += 1
            continue
        if not line.strip().startswith("|"):
            header = None
        i += 1
    return tasks


def main() -> int:
    fix = "--fix" in sys.argv
    if not TRACKER.is_file():
        print(f"Not found: {TRACKER}", file=sys.stderr)
        return 1
    text = TRACKER.read_text()
    tasks = parse_tasks(text)

    if not tasks:
        print("No task rows found — parser or TRACKER.md format problem.", file=sys.stderr)
        return 1

    base_dir = TRACKER.parent
    issues: list[str] = []
    by_status: dict[str, int] = {}
    missing_task_file: list[str] = []
    seen_ids: set[str] = set()

    for row in tasks:
        tid = row.get("id", "")
        status = normalize_status(row.get("status", ""))

        if tid in seen_ids:
            issues.append(f"{tid}: duplicate row")
        seen_ids.add(tid)

        if status not in STATUSES:
            issues.append(f"{tid}: unrecognized status {status!r}")
        by_status[status] = by_status.get(status, 0) + 1

        task_file_cell = row.get("task file")
        if task_file_cell is not None:
            ok, target = resolve_link(task_file_cell, base_dir)
            if not ok:
                issues.append(f"{tid}: Task file link doesn't resolve: {target}")
            if task_file_cell.strip() in ("—", "-", ""):
                missing_task_file.append(tid)

        req_cell = row.get("requirement")
        if req_cell is not None:
            ok, target = resolve_link(req_cell, base_dir)
            if not ok:
                issues.append(f"{tid}: Requirement link doesn't resolve: {target}")

    total = len(tasks)
    done = by_status.get("done", 0)

    left_rows = [r for r in tasks if normalize_status(r.get("status", "")) != "done"]
    if left_rows:
        print(f"=== {len(left_rows)} task(s) not done ===")
        for row in left_rows:
            title = row.get("title") or row.get("task") or ""
            print(f"  {row['id']:<10} [{row.get('status', '?'):<11}] {title}")
        print()

    print("=== Status summary ===")
    for s in ("done", "in-progress", "blocked", "todo"):
        print(f"  {s:<12} {by_status.get(s, 0)}")
    print(f"  {'TOTAL':<12} {total}")

    if missing_task_file:
        print(
            f"\n=== {len(missing_task_file)} task(s) missing a tasks/specs/TS-###-*.md "
            "file (backlog, not a failure) ==="
        )
        for tid in missing_task_file:
            print(f"  {tid}")

    if issues:
        print(f"\n=== {len(issues)} issue(s) — these DO fail the check ===")
        for issue in issues:
            print(f"  {issue}")

    if fix:
        summary_lines = [
            f"**{done} / {total} tasks done** ({total - done} left).",
            "",
            "| Status | Count |",
            "|---|---|",
        ]
        for s in ("done", "in-progress", "blocked", "todo"):
            summary_lines.append(f"| {s} | {by_status.get(s, 0)} |")
        summary_lines.append("")
        if missing_task_file:
            summary_lines.append(
                f"**{len(missing_task_file)} task(s) still need a `tasks/specs/TS-###-*.md` "
                "file** (see the list above from a plain run)."
            )
        else:
            summary_lines.append(
                "**Every task has a `tasks/specs/TS-###-*.md` file.**"
            )
        new_summary = "\n".join(summary_lines)
        pattern = re.compile(r"<!-- STATUS:START -->.*?<!-- STATUS:END -->", re.DOTALL)
        replacement = f"<!-- STATUS:START -->\n{new_summary}\n<!-- STATUS:END -->"
        new_text, n = pattern.subn(replacement, text)
        if n == 0:
            print("\nCould not find STATUS:START/END markers in TRACKER.md.", file=sys.stderr)
            return 1
        TRACKER.write_text(new_text)
        print(f"\nRewrote status summary in {TRACKER}.")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
