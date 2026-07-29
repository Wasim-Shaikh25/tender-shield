# Task files (`tasks/specs/`)

One file per task, named `TS-###-<slug>.md`, code-level. This is the "how" —
distinct from the requirement doc (`specs/requirements/R-0xx-*.md`), which
stays business/behavior-level (why + what + acceptance criteria), and from
the module spec (`specs/modules/<name>.md`), which is the standing contract
for the module regardless of which task touched it last.

Every task gets one — done or not. `tasks/TRACKER.md` links to it from the
"Task file" column; `python scripts/check_tracker.py` verifies the link
resolves.

## Template

```markdown
# TS-### — <Title>

**Status:** todo | in-progress | blocked | done
**Requirement:** [R-0xx](../../specs/requirements/R-0xx-<slug>.md) — or "—"
  for pre-R-doc tasks, which cite a Build Doc section instead
**Spec(s) updated:** `specs/modules/<name>.md` (§B#, §A#) — every spec this
  task's behavior touches
**Module(s):** <names>
**Severity / Gate:** P0/P1/P2 · <gate or phase name>

## What this builds
1–3 sentences: the concrete thing this task adds or changes.

## Current (only when replacing existing behavior)
​```<language>
<real code, with file:line>
​```

## Implementation
​```<language>
<the shipped code for a done task, or the reference implementation for an
 open one — with file:line for shipped code>
​```

## Files touched
- `path/to/file.ext` — what changed / what will change

## Tests
- `tests/test_x.py::test_y` — what it proves

## Acceptance criteria
- [ ] A1 …
(mirrors the relevant A-numbered criteria from the parent requirement doc —
check them off as they get a passing test, not before)

## Commit
`<hash>` — `<subject>`   (done tasks only; omit for open tasks)
```

## Conventions

- **Slug** is a short kebab-case summary of the title (`TS-090-coupons-referrals.md`,
  not `TS-090-implement-the-coupons-discounts-credits-referrals-trials-and-pilot-comps-feature.md`).
- **Code snippets are real**, not illustrative pseudocode — quote the actual
  file, with `file:line`, the same discipline the R-docs already use for
  their "Current"/"Target" blocks (this is where that content now lives when
  it's specific to one task rather than shared across several tasks under
  one requirement).
- When a requirement doc spans several tasks (e.g. R-002 → TS-085/093/094/101,
  R-016 → TS-105…TS-109), each task gets its OWN file with only the
  code/tests relevant to it — don't duplicate the whole requirement's detail
  into every task file, and don't leave it undivided across all of them
  either (that's the exact scattering this restructure fixes).
- A task file for a **pre-R-doc task** (TS-001…TS-070ish, before the
  requirement-doc system existed) is reconstructed from the current code and
  the relevant `specs/modules/*.md` — that IS the ground truth for what
  those tasks built, since git history for that span isn't commit-granular
  (see `tasks/TRACKER.md`'s intro).
