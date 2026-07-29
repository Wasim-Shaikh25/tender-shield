# TS-041 — `baseline` module: hash-sealed baseline freeze + notice register + award delta

**Status:** done
**Requirement:** Doc §0.1 (P2), §10, §1.2
**Spec(s) updated:** `specs/modules/baseline.md`
**Module(s):** `baseline`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

The post-award handover surface: an immutable, hash-sealed snapshot of
accepted findings + confirmed deadlines + opportunity metadata at the moment
of bid submission (the "baseline"), a deterministic notice-rule register
(deadlines the contractor must meet post-award, e.g. claim notices), an
award-vs-tender delta, and a commercial handover pack.

## Implementation

```python
# backend/app/modules/baseline/models.py
class Baseline(Base, WorkspaceScopedMixin):
    """Stores a content hash of the frozen snapshot — integrity-verifiable;
    the frozen fields themselves are never mutated after freeze()."""
```

```python
# backend/app/modules/baseline/notices.py
@dataclass
class NoticeRule: ...

def extract_notice_rules(findings: list[dict]) -> list[NoticeRule]:
    """Deterministic regex/pattern scan over confirmed findings for
    notice-period language (e.g. "notice of claim within 28 days") —
    not LLM-judged, per CLAUDE.md §4."""
```

```python
# backend/app/modules/baseline/router.py
def freeze(...): ...
def verify_baseline(...): ...   # integrity check against the stored hash
def notice_register(...): ...
def compare(...): ...           # award-vs-tender delta
def handover(...): ...          # commercial handover pack
```

## Files touched

- `backend/app/modules/baseline/{models,notices,service,router,module}.py`

## Tests

- `backend/tests/modules/baseline/test_notices.py`, `test_service.py`

## Acceptance criteria

- [x] A frozen baseline's integrity hash detects any post-freeze tampering.
- [x] The notice-rule register is extracted deterministically from
      confirmed findings.
- [x] `compare()` produces an award-vs-tender delta from the frozen baseline.

## Commit

Predates commit-granular history (PR #10 bulk import).
