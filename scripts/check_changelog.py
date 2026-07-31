#!/usr/bin/env python3
"""Enforce CLAUDE.md §1.5: a push without a changelog entry is incomplete work.

Fails (non-zero exit) when non-exempt ("code") files changed between BASE and
HEAD but CHANGELOG.md did not gain any real content in the same range.
See specs/902-changelog-check.md for the full behavior spec.
"""
from __future__ import annotations

import subprocess
import sys

SKIP_MARKER = "[skip-changelog]"

EXEMPT_PREFIXES = ("docs/", "specs/", "tasks/", ".github/", ".cursor/", ".devin/")
EXEMPT_FILES = {
    "CHANGELOG.md",
    "README.md",
    "CLAUDE.md",
    "DEVIN.md",
    "AGENTS.md",
    "PRODUCTION_READINESS_AUDIT.md",
    ".gitignore",
}


def _run(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=cwd
    )
    return result.stdout


def is_exempt(path: str) -> bool:
    if path in EXEMPT_FILES or path.endswith(".md"):
        return True
    return path.startswith(EXEMPT_PREFIXES)


def changed_files(base: str, head: str, cwd: str | None = None) -> list[str]:
    out = _run(["diff", "--name-only", f"{base}...{head}"], cwd=cwd)
    return [line for line in out.splitlines() if line.strip()]


def changelog_added_lines(base: str, head: str, cwd: str | None = None) -> list[str]:
    out = _run(["diff", f"{base}...{head}", "--", "CHANGELOG.md"], cwd=cwd)
    return [
        line[1:]
        for line in out.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def has_skip_marker(base: str, head: str, cwd: str | None = None) -> bool:
    out = _run(["log", f"{base}..{head}", "--format=%B"], cwd=cwd)
    return SKIP_MARKER in out


def check(base: str, head: str, cwd: str | None = None) -> tuple[bool, str]:
    if has_skip_marker(base, head, cwd=cwd):
        return True, f"Skipping changelog check: found '{SKIP_MARKER}' in commit range."

    files = changed_files(base, head, cwd=cwd)
    if not files:
        return True, "No changes between base and head; nothing to check."

    code_files = [f for f in files if not is_exempt(f)]
    if not code_files:
        return True, "Only docs/spec/task changes detected; changelog entry not required."

    if "CHANGELOG.md" not in files:
        offenders = "\n".join(f"  - {f}" for f in code_files)
        return False, (
            "CHANGELOG.md was not updated, but these files changed:\n"
            f"{offenders}\n\n"
            "CLAUDE.md §1.5: update CHANGELOG.md's [Unreleased] section in "
            "the same push (Done + Next), or add '[skip-changelog]' to a commit "
            "message if this change truly needs no entry."
        )

    added = [line for line in changelog_added_lines(base, head, cwd=cwd) if line.strip()]
    if not added:
        return False, (
            "CHANGELOG.md was touched but no content was added (only deletions "
            "or reformatting). Add a dated entry under [Unreleased] describing "
            "what was done."
        )

    added_text = "\n".join(added)
    if "TS-" not in added_text:
        return True, (
            "CHANGELOG.md updated, but no TS-### task ID found in the added "
            "lines — double-check the entry references its task "
            "(CLAUDE.md §1.5)."
        )

    return True, "CHANGELOG.md updated with a task-referenced entry."


def main(argv: list[str]) -> int:
    base = argv[0] if len(argv) > 0 else "origin/main"
    head = argv[1] if len(argv) > 1 else "HEAD"
    ok, message = check(base, head)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
