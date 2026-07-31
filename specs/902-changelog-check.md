# Changelog Enforcement — Spec

**Status:** implemented
**Requirement refs:** `CLAUDE.md` §1.5 "Changelog every session... A push without
a changelog entry is incomplete work."; `README.md` "Requirement → Task → Spec →
Implement → Commit → Changelog."
**Task refs:** TS-196

## Purpose

`CLAUDE.md` §1 mandates a `CHANGELOG.md` `[Unreleased]` entry in the same push as
any code change, but nothing enforced it — reviewers had to remember to check by
hand. This adds an automated CI gate (`scripts/check_changelog.py`) that fails a
pull request when code changed but `CHANGELOG.md` did not, so the rule is
enforced mechanically instead of by convention.

## Public interface

- **Capabilities published / consumed:** none — this is a repo-tooling script,
  not an `app.core` or `app.modules.*` component. It has no runtime dependency on
  the backend and does not participate in the service registry or event bus
  (`CLAUDE.md` §2 module rules don't apply to it).
- **Events emitted / consumed:** none.
- **API routes:** none.
- **CLI:** `python3 scripts/check_changelog.py [BASE] [HEAD]` (defaults
  `origin/main`, `HEAD`); prints a message and exits non-zero on violation.
- **CI:** new `changelog` job in `.github/workflows/ci.yml`, gated on
  `pull_request` events, running the script against the PR's base branch.

## Data owned

None — reads git history/diff only; persists nothing.

## Behavior

- B1. Compute the changed file set between `BASE` and `HEAD`
  (`git diff BASE...HEAD --name-only`), using the merge-base so unrelated
  base-branch drift is ignored.
- B2. Files under `docs/`, `specs/`, `tasks/`, `.github/`, `.cursor/`, `.devin/`,
  any `*.md` file, and `.gitignore` are exempt ("process/docs" changes) — they
  never require a changelog entry on their own.
- B3. If every changed file is exempt (or nothing changed), the check passes
  with no changelog entry required.
- B4. Otherwise (at least one non-exempt "code" file changed — e.g. under
  `backend/`, `frontend/`, `mcp-servers/`, `rulepacks/`, `scripts/`,
  `observability/`), `CHANGELOG.md` must also appear in the changed file set,
  and its diff must contain at least one non-empty added line — touching the
  file with no net addition (e.g. pure reformatting or only deletions) does not
  satisfy the rule.
- B5. If the added `CHANGELOG.md` lines don't reference any `TS-###` task ID,
  the check still passes but prints a warning — task-ID discipline is enforced
  by the task-first rule in `tasks/backlog.md`, not re-derived here.
- B6. Any commit message in the `BASE..HEAD` range containing the literal
  marker `[skip-changelog]` bypasses the check entirely (escape hatch for
  merges, reverts, and dependency bumps where a changelog entry doesn't apply).

## Acceptance criteria

- A1. A PR that only touches `docs/`, `specs/`, `tasks/backlog.md`, or `*.md`
  files passes without touching `CHANGELOG.md`.
- A2. A PR that adds/edits `backend/`, `frontend/`, `mcp-servers/`,
  `rulepacks/`, `scripts/`, or `observability/` files and does not touch
  `CHANGELOG.md` fails with a message listing the offending files.
- A3. A PR that touches `CHANGELOG.md` but only deletes/reformats lines (no net
  addition) fails.
- A4. A PR that adds a real `CHANGELOG.md` entry alongside code changes passes.
- A5. A commit with `[skip-changelog]` in its message bypasses the check.
- A6. Unit tests in `scripts/tests/test_check_changelog.py` cover A1–A5 against
  throwaway git repos.

## Out of scope

- Enforcing changelog entries on direct pushes to `main` outside a PR (the CI
  job only runs on `pull_request` events, since a merge-base diff needs a PR
  base ref).
- Validating changelog *content* quality beyond "non-empty addition" (spelling,
  matching the actual diff, etc.) — left to human review.
- Auto-generating changelog entries from commits.

## Assumptions

- `assumption:` the exempt-path list above is a reasonable definition of a
  "process/docs-only" change; it isn't enumerated in the Build Doc since the
  Doc doesn't cover repo tooling.
