# Validation automation — Spec

**Status:** implemented  
**Requirement refs:** Doc §11.5 (eval at scale), user request for unattended full-pipeline validation  
**Task refs:** TS-344

## Purpose

Provide an unattended script that drives a running TenderShield backend through
the complete product pipeline — signup, workspace creation, opportunity seeding,
ingestion, risk/BOQ review, baseline lock, post-award features, and export — so a
human can log in to a pre-populated workspace and review findings. The script
produces a pass/fail report and can be re-run locally or on a VPS against a
fresh SQLite database.

## Public interface

- CLI: `scripts/validate_full_pipeline.py`
- Configuration via command-line flags and `backend/.env.validation`.
- All interaction is through the public REST API (`/api/*`); the script does not
  import backend internals.

## Behavior

1. Optionally start the backend in a subprocess with a chosen `.env` file.
2. Sign up / log in with email+password (OTP/MFA disabled for automation).
3. Create or reuse a workspace.
4. Seed N opportunities from sample tender fixtures (`evals/in-works/sample_tender`).
   - Title, jurisdiction, currency, and employer rotate through Indian and UAE
     presets so the same fixtures exercise multiple markets.
5. For each opportunity:
   - Upload a `.docx` generated from `conditions.md`.
   - Run risk review (`POST /risk/opportunities/{id}/run`).
   - Run deterministic BOQ checks (`POST /boq/opportunities/{id}/run`).
6. For a configurable subset (`--complete-count`) run the full lifecycle:
   - Auto-accept all findings.
   - Freeze baseline (`POST /baseline/opportunities/{id}/freeze`).
   - Generate notice register (`GET .../notice-register`).
   - Create drafting artifacts (`clarification_letter`, `assumptions_register`).
   - Create a subcontract, change event, and claim.
   - Run pricing checks (`loading`, `rate-benchmark`) and control-tower
     dashboards.
7. Run workspace-level export report once.
8. Write `validation_report.md` with account credentials, opportunity IDs, and
   pass/fail per feature.

## Acceptance criteria

- Script is `ruff` clean and passes `mypy` on the repo's strictness settings.
- 50 opportunities can be seeded without 5xx.
- 5 complete-opportunity lifecycles succeed end-to-end.
- Generated report lists exact login email, workspace, opportunity IDs, and a
  feature pass/fail summary.
- Validation DB and local storage dir can be copied to another machine and used
  with the same `.env.validation` settings.

## Out of scope

- Public tender corpus download/harvesting (covered by `scripts/corpus_harvest.py`
  and `specs/eval-at-scale.md`).
- LLM risk validation (requires `TS_OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`).
- UI automation; all validation is API-driven.
