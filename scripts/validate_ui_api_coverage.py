#!/usr/bin/env python3
"""Validate that frontend api.ts wrappers cover the backend route surface.

Run from the repo root with the backend virtualenv Python:

    backend/.venv/bin/python scripts/validate_ui_api_coverage.py

Exit codes:
    0  No dead frontend wrappers and, unless --strict, Phase 1 routes are documented
    1  Dead frontend wrapper, or --strict with a Phase 1 route missing a consumer

The script writes two artifacts:
    /tmp/backend_routes.txt
    /tmp/frontend_routes.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_API = REPO_ROOT / "frontend" / "lib" / "api.ts"
ROADMAP = REPO_ROOT / "docs" / "PHASE2_UI_ROADMAP.md"

# Phase 1 route prefixes that must have a UI consumer before public launch.
# The backend mounts routers under /api/<module>; we compare paths without the /api prefix.
PHASE1_PREFIXES = [
    "POST /auth/logout",
    "POST /auth/mfa/enroll",
    "POST /auth/mfa/verify",
    "/auth/workspaces/{}/approval-matrix",
    "/auth/workspaces/{}/projects",
    "/auth/projects/{}/members",
    "/auth/admin",
    "POST /boq/opportunities/{}/upload",
    "/ingestion/documents/{}",
    "/ingestion/opportunities/{}/documents/{}/stream",
    "/ingestion/opportunities/{}/documents/{}/addendum",
    "/rulepacks/{}/patterns",
    "/rulepacks/corrections",
    "/rulepacks/admin/packs/{}/suggestions",
    "/rulepacks/admin/packs/{}/files",
    "/subcontract/status",
    "/billing/settings",
    "/billing/projects/{}/status",
]


def _normalize_path(p: str) -> str:
    p = p.split("?")[0]
    p = re.sub(r"\\\$\\\{[^}]+\\\}", "{}", p)
    p = re.sub(r"\$\{[^}]+\}", "{}", p)
    p = re.sub(r"/\{[^}]+\}", "/{}", p)
    p = re.sub(r"\{[^}]+\}", "{}", p)
    return p


def extract_frontend_wrappers() -> set[str]:
    text = FRONTEND_API.read_text()
    # Normalize so multi-line req(...) calls can be matched as one block.
    text2 = re.sub(r"req(?:<[^>]+>)?\s*\(", "req(", text, flags=re.DOTALL)
    methods: list[tuple[str, str]] = []

    for m in re.finditer(
        r'''req\(\s*(["'])([^"']*)\1\s*,\s*\{(?:[^{}]|\{[^}]*\})*method\s*:\s*(["'])([A-Z]+)\3''',
        text2,
        re.DOTALL,
    ):
        methods.append((m.group(4), m.group(2)))

    for m in re.finditer(r'''req\(\s*(["'])([^"']*)\1\s*,\s*\{\s*\}''', text2, re.DOTALL):
        methods.append(("GET", m.group(2)))

    for m in re.finditer(
        r'''req\(\s*`([^`]*)`\s*,\s*\{(?:[^{}]|\{[^}]*\})*method\s*:\s*(["'])([A-Z]+)\2''',
        text2,
        re.DOTALL,
    ):
        methods.append((m.group(3), m.group(1)))

    for m in re.finditer(r'''req\(\s*`([^`]*)`\s*,\s*\{\s*\}''', text2, re.DOTALL):
        methods.append(("GET", m.group(1)))

    for m in re.finditer(
        r'''\bclient\.(get|post|put|delete|patch)\s*\(\s*(["'])([^"']*)\2''',
        text2,
        re.IGNORECASE | re.DOTALL,
    ):
        methods.append((m.group(1).upper(), m.group(3)))

    seen = set()
    for method, path in methods:
        path = _normalize_path(path.split("?")[0])
        seen.add(f"{method} {path}")

    (Path("/tmp") / "frontend_routes.txt").write_text("\n".join(sorted(seen)) + "\n")
    return seen


def extract_backend_routes() -> set[str]:
    sys.path.insert(0, str(BACKEND_ROOT))
    # Use a minimal env so module setup that requires DB does not fail during import.
    import os

    os.environ.setdefault("TS_DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("TS_SECRET_KEY", "audit-only")
    os.environ.setdefault("TS_ENV", "dev")

    from app.core.config import Settings
    from app.core.loader import load_modules

    report = load_modules(Settings().enabled_module_names())
    seen = set()
    for spec in report.loaded:
        if spec.router is None:
            continue
        prefix = f"/{spec.name}"
        for r in spec.router.routes:
            methods = getattr(r, "methods", set())
            path = getattr(r, "path", "")
            if not methods or not path:
                continue
            for m in methods:
                if m == "HEAD":
                    continue
                seen.add(f"{m} {_normalize_path(prefix + path)}")

    (Path("/tmp") / "backend_routes.txt").write_text("\n".join(sorted(seen)) + "\n")
    return seen


def _is_phase1(method: str, path: str) -> bool:
    key = f"{method} {path}"
    for prefix in PHASE1_PREFIXES:
        if key.startswith(prefix) or path.startswith(prefix):
            return True
    return False


def _matches_route(needle: str, haystack: set[str]) -> bool:
    # Exact normalized match.
    return needle in haystack


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate UI/API route coverage.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a JSON summary instead of human-readable text.",
    )
    parser.add_argument(
        "--write-roadmap",
        action="store_true",
        help="Regenerate docs/PHASE2_UI_ROADMAP.md from unconsumed routes.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if a Phase 1 route has no UI consumer (default: warn only).",
    )
    args = parser.parse_args()

    frontend = extract_frontend_wrappers()
    backend = extract_backend_routes()

    missing_ui = sorted(backend - frontend)
    missing_fe = sorted(frontend - backend)

    phase1_missing = [
        line for line in missing_ui if _is_phase1(*line.split(" ", 1))
    ]
    phase2_missing = [
        line for line in missing_ui if not _is_phase1(*line.split(" ", 1))
    ]

    by_module = Counter()
    for line in missing_ui:
        path = line.split(" ", 1)[1]
        mod = path.split("/")[1] if "/" in path else "unknown"
        by_module[mod] += 1

    result = {
        "frontend_wrappers": len(frontend),
        "backend_routes": len(backend),
        "frontend_without_backend": len(missing_fe),
        "backend_without_frontend": len(missing_ui),
        "phase1_missing": len(phase1_missing),
        "phase2_missing": len(phase2_missing),
        "phase1_missing_routes": phase1_missing,
        "missing_by_module": dict(by_module.most_common()),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("UI/API coverage")
        print("=" * 60)
        print(f"Frontend wrappers : {len(frontend)}")
        print(f"Backend routes    : {len(backend)}")
        print(f"Missing UI consumer: {len(missing_ui)}")
        print(f"Missing backend match (dead wrappers): {len(missing_fe)}")
        print(f"Phase 1 missing   : {len(phase1_missing)}")
        print(f"Phase 2+ missing  : {len(phase2_missing)}")
        print()
        print("Missing UI by module:")
        for mod, cnt in by_module.most_common():
            print(f"  {mod:25s} {cnt}")
        if missing_fe:
            print("\nDead frontend wrappers (no matching backend route):")
            for line in missing_fe:
                print(f"  {line}")
        if phase1_missing:
            print("\nPhase 1 routes with no UI consumer:")
            for line in phase1_missing:
                print(f"  {line}")

    if args.write_roadmap:
        _write_roadmap(phase2_missing)

    if missing_fe:
        return 1
    if args.strict and phase1_missing:
        return 1
    return 0


def _write_roadmap(routes: list[str]) -> None:
    by_mod: dict[str, list[tuple[str, str]]] = {}
    for line in routes:
        method, path = line.split(" ", 1)
        mod = path.split("/")[1] if "/" in path else "unknown"
        by_mod.setdefault(mod, []).append((method, path))

    lines = [
        "# Phase 2+ UI Roadmap — Backend Routes Deferred from Round 13",
        "",
        "**Sourced from:** `PRODUCTION_READINESS_AUDIT.md` Round 13",
        "**Status:** Auto-generated from `scripts/validate_ui_api_coverage.py`",
        "",
        "This document lists backend routes with no UI consumer. Phase 1 routes",
        "must be wired in TS-382 before public launch; Phase 2+ routes are deferred.",
        "",
        "| Module | Method | Route | Proposed phase | Rationale |",
        "|---|---|---|---|---|",
    ]
    for mod in sorted(by_mod.keys()):
        for method, path in by_mod[mod]:
            phase = _infer_phase(mod)
            rationale = "Deferred pending product prioritization and phase exit gate."
            lines.append(
                f"| `{mod}` | {method} | `{path}` | {phase} | {rationale} |"
            )
    lines.extend([
        "",
        "## Next actions",
        "",
        "- When a module is promoted, move its routes to `docs/ROUND13_GAP_CLOSURE_REQUIREMENTS.md` R3.1 and create the corresponding `frontend/lib/api.ts` wrapper and page.",
        "- Review this roadmap at the start of each phase to confirm deferrals are still valid.",
    ])
    ROADMAP.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {ROADMAP} with {len(routes)} deferred routes.")


def _infer_phase(mod: str) -> str:
    phase_map = {
        "advisor": "Phase 2",
        "analytics": "Phase 3",
        "baseline": "Phase 2",
        "change": "Phase 2",
        "claims": "Phase 3",
        "comparison": "Phase 1/2",
        "controltower": "Phase 3",
        "crossref": "Phase 2",
        "drafting": "Phase 1/2",
        "drawings": "Phase 2",
        "evidence": "Phase 3",
        "export": "Phase 1/2",
        "express": "Phase 2",
        "governance": "Phase 3",
        "health": "N/A",
        "integrations": "Phase 2",
        "marketdata": "Phase 3",
        "outcomes": "Phase 3",
        "project_state": "Phase 2",
        "public_api": "Phase 2",
        "qualification": "Phase 1/2",
        "review": "Phase 1/2",
        "standards": "Phase 2",
        "subcontract": "Phase 3",
        "support": "Phase 1/2",
        "timeline": "Phase 2",
    }
    return phase_map.get(mod, "TBD")


if __name__ == "__main__":
    sys.exit(main())
