"""Enforces the no-hard-dependency rule (spec core B1, CLAUDE.md §2):
a module may import only app.core.* and its own package — never a sibling
module. This test is the architecture; do not weaken it.
"""

import ast
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parents[1] / "app" / "modules"


def iter_imports(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_no_cross_module_imports():
    violations = []
    for pkg in MODULES_DIR.iterdir():
        if not pkg.is_dir():
            continue
        own_prefix = f"app.modules.{pkg.name}"
        for py in pkg.rglob("*.py"):
            for imported in iter_imports(py):
                if imported.startswith("app.modules") and not (
                    imported == own_prefix or imported.startswith(own_prefix + ".")
                ):
                    violations.append(f"{py.relative_to(MODULES_DIR.parent)}: imports {imported}")
    assert not violations, "hard cross-module dependencies found:\n" + "\n".join(violations)
