"""Tests for scripts/check_changelog.py (TS-196, specs/902-changelog-check.md)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_changelog as cc  # noqa: E402


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def write(repo: Path, rel_path: str, content: str) -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


INITIAL_CHANGELOG = "# Changelog\n\n## [Unreleased]\n\nOLD LINE TO REMOVE\n"


class ChangelogCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.repo = Path(self.tmp)
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.email", "test@example.com")
        run_git(self.repo, "config", "user.name", "Test")
        write(self.repo, "CHANGELOG.md", INITIAL_CHANGELOG)
        write(self.repo, "backend/app/foo.py", "x = 1\n")
        write(self.repo, "README.md", "hello\n")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def branch(self, name: str) -> None:
        run_git(self.repo, "checkout", "-q", "-b", name)

    def commit_all(self, message: str) -> None:
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-q", "-m", message)

    def test_docs_only_change_passes(self) -> None:
        self.branch("feature")
        write(self.repo, "docs/notes.md", "notes\n")
        self.commit_all("docs: notes")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertTrue(ok, msg)

    def test_code_change_without_changelog_fails(self) -> None:
        self.branch("feature")
        write(self.repo, "backend/app/foo.py", "x = 2\n")
        self.commit_all("feat: change foo")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertFalse(ok, msg)
        self.assertIn("CHANGELOG.md", msg)

    def test_code_change_with_changelog_passes(self) -> None:
        self.branch("feature")
        write(self.repo, "backend/app/foo.py", "x = 2\n")
        write(
            self.repo,
            "CHANGELOG.md",
            "# Changelog\n\n## [Unreleased]\n\n### Done\n- TS-999 did a thing\n",
        )
        self.commit_all("feat: change foo, TS-999")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertTrue(ok, msg)

    def test_changelog_touch_without_addition_fails(self) -> None:
        self.branch("feature")
        write(self.repo, "backend/app/foo.py", "x = 2\n")
        write(self.repo, "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n")
        self.commit_all("feat: change foo, drop a changelog line")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertFalse(ok, msg)

    def test_skip_marker_bypasses(self) -> None:
        self.branch("feature")
        write(self.repo, "backend/app/foo.py", "x = 2\n")
        self.commit_all("chore: bump dep [skip-changelog]")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertTrue(ok, msg)

    def test_no_changes_passes(self) -> None:
        self.branch("feature")
        ok, msg = cc.check("main", "feature", cwd=str(self.repo))
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
