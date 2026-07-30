# Repository Governance

This document records the repository-level rules that keep the TenderShield
mono-repo reviewable, auditable, and safe to release.

## Default branch

`claude/dev-workflow-modules-58dpqw` is the current integration branch.
All feature work is merged through pull requests; no direct pushes.

## Branch protection (configure in GitHub)

Apply these rules to the default branch:

- **Require a pull request before merging** with at least one approving review.
- **Require status checks to pass before merging:**
  - `ruff` (backend lint)
  - `mypy` (backend type check)
  - `pytest` (backend test suite)
  - `frontend-lint`, `frontend-typecheck`, `frontend-build` (when frontend files change)
  - `rls-postgres` (PostgreSQL RLS integration job)
- **Require branches to be up to date before merging**.
- **Restrict pushes that create files** to the default branch; only PRs may land.
- **Dismiss stale PR approvals** when new commits are pushed.
- **Require linear history** / no merge commits (`Rebase and merge` or `Squash and merge`).

## CODEOWNERS

The root `CODEOWNERS` file (`/.github/CODEOWNERS`) assigns `@Wasim-Shaikh25`
as the default owner for all paths. Module-specific owners can be added as the
team grows, e.g.:

```text
/backend/app/modules/billing/  @billing-lead
/backend/app/modules/auth/     @security-lead
/frontend/                     @frontend-lead
```

## Python virtual environment install

Backend dependencies should be installed in an isolated venv, not system Python:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then create the schema:

```bash
alembic upgrade head
```

Run the test suite before opening a PR:

```bash
ruff check app tests migrations
mypy app
pytest -q
```

## Frontend install

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_URL=http://localhost:8000/api
npm run dev
```

Before a PR:

```bash
npm run lint
npm run typecheck
npm run build
```

## AI assistant rules

All AI-generated changes must follow the workflow in `CLAUDE.md` /
`.cursor/rules/` / `.devin/rules/`:

1. Task first (`tasks/backlog.md`).
2. Spec before implementation (`specs/`).
3. Commit per logical step with a `Task: TS-###` reference.
4. Update `CHANGELOG.md` in the same push.
