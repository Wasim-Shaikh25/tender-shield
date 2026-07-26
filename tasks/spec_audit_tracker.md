# Spec Audit Fix Tracker

Created from the spec-vs-code audit on 2026-07-26. Tracks the follow-up work
needed to bring `specs/modules/*.md` and the backend into alignment.

## Goal

Close the gaps found between the spec declarations and the current
implementation without adding new product domains.

## Sprint map

| Sprint | Theme | Tasks | Status |
|--------|-------|-------|--------|
| 0 | Quick spec/code alignment | TS-062 (service_factory publish), TS-063 (route wording) | done |
| 1 | Missing module specs | TS-058 (findings), TS-059 (export), TS-060 (health), TS-061 (notifications) | done |
| 2 | Public-interface alignment | TS-064 (ingestion), TS-065 (risk), TS-066 (drafting) | done |
| 3 | Missing test coverage | TS-067 (export/health/notifications tests) | done |
| 4 | Deeper feature gaps | TS-069 (assistant SSE/history), TS-070 (billing invoice list/record_usage) (TS-068 done) | in_progress |

## Feature tracker

| ID | Feature | Module(s) | Priority | Status | Acceptance Gate |
|----|---------|-----------|----------|--------|-----------------|
| TS-058 | Spec: findings module | `findings` | P1 | done | `specs/modules/findings.md` exists and matches `store.py` + `models.py` |
| TS-059 | Spec: export module | `export` | P1 | done | `specs/modules/export.md` exists and matches `router.py` + `service.py` |
| TS-060 | Spec: health module | `health` | P1 | done | `specs/modules/health.md` exists and matches `router.py` |
| TS-061 | Spec: notifications module | `notifications` | P1 | done | `specs/modules/notifications.md` exists and matches `digest.py` + `sender.py` |
| TS-062 | Publish analytics/comparison service_factory | `analytics`, `comparison` | P0 | done | `module.py` provides the capability declared in each spec |
| TS-063 | Fix spec route wording | `timeline`, `crossref` (specs) | P0 | done | Spec route strings match actual router paths |
| TS-064 | Align ingestion public interface | `ingestion` | P2 | done | Spec reflects actual capabilities; `doc_chunks`/`doc_text` documented as gap |
| TS-065 | Align risk public interface | `risk` | P2 | done | Spec reflects actual `risk.classifier` / `risk.service_factory` shape |
| TS-066 | Align drafting public interface | `drafting` | P2 | done | Spec reflects `drafting.service_factory` and separate `export` module |
| TS-067 | Tests for export/health/notifications | `export`, `health`, `notifications` | P2 | done | `tests/test_export.py`, `test_health.py`, `test_notifications.py` pass |
| TS-068 | Ingestion doc_chunks + doc_text | `ingestion` | P2 | done | `doc_chunks` table + migration; `doc_text` capability published |
| TS-069 | Assistant SSE + history | `assistant` | P2 | pending | SSE `/chat`; conversation/session persistence |
| TS-070 | Billing invoice list + record_usage | `billing` | P2 | in_progress | Invoice list route; `billing.record_usage` capability published |

## Definition of done

- [ ] Sprint 0 complete and tests passing.
- [ ] Sprint 1 complete: every backend module has a matching spec.
- [ ] Sprint 2 complete: every spec's public interface matches the code or is
      explicitly documented as a deferred follow-up.
- [ ] Sprint 3 complete: every module has at least a smoke test.
- [ ] Sprint 4 accepted as a roadmap: larger features get their own task IDs
      before implementation.
