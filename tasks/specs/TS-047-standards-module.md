# TS-047 — `standards` module: org-defined custom notice standards

**Status:** done
**Requirement:** Doc §10, §0.1, §2
**Spec(s) updated:** `specs/modules/standards.md`
**Module(s):** `standards`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

Lets an org override or extend the rule-pack's default notice/commercial
standards with their own policy (e.g. their legal team's own claim-notice
interpretation), applied prevail or side-by-side against the rule-pack
default, with the register showing which standard (org vs. rule-pack)
produced each entry.

## Implementation

```python
# backend/app/modules/standards/models.py
class WorkspaceNoticeStandard(Base, WorkspaceScopedMixin): ...
class WorkspaceCommercialStandard(Base, WorkspaceScopedMixin): ...
```

```python
# backend/app/modules/standards/router.py
def get_notice(...): ...
def set_notice(...): ...      # org overrides a notice standard
def clear_notice(...): ...    # revert to rule-pack default
def get_policies(...): ...
def set_policy(...): ...      # commercial policy (e.g. threshold checks)
def check_standards(...): ...
```

```python
# backend/app/modules/standards/service.py
def _extract_number(finding: dict, unit: str) -> float | None: ...
def _compare(value: float, operator: str, threshold: float) -> bool: ...
```

Frontend editor lets a workspace admin set/clear these; the notice register
(TS-041/046) shows an origin badge (rule-pack default vs. org override) on
each entry.

## Files touched

- `backend/app/modules/standards/{models,service,router,module}.py`
- frontend standards editor (`frontend/app/standards/`)

## Tests

- `backend/tests/modules/standards/test_service.py`

## Acceptance criteria

- [x] An org-set notice standard prevails over (or sits side-by-side with,
      per config) the rule-pack default.
- [x] Clearing an org override reverts the register entry to the rule-pack
      default without data loss of the override itself.
- [x] Every register entry's origin (org vs. rule-pack) is visible.

## Commit

Predates commit-granular history (PR #10 bulk import).
