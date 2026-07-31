# Schedule-of-Rates data (TS-204)

This directory is **intentionally empty**. It is where published Schedule-of-Rates
figures go — `rulepacks/in-works/rates/<authority>/<year>.yaml`, one file per
authority per year, validated against `RateSchedule` in
`app/modules/rulepacks/schemas.py`.

## Why there is no CPWD DSR data checked in yet

Risk-pattern *thresholds* in this pack (e.g. "LD capped at 10%") are loosely
derivable from public documents already cited in each pattern's `source:` field
(CPWD GCC, GFR 2017, HKA CRUX). A Schedule-of-Rates is different: it is a large
table of specific, authoritative, numeric rates published by a government body.
Entering it correctly is a **data-population task against a primary source**,
not a coding task — fabricating even a plausible-looking rate would corrupt the
one part of this product whose entire premise is "numbers never come from the
LLM, and never come from a guess" (`CLAUDE.md` §4).

## Format

```yaml
# rulepacks/in-works/rates/cpwd/2026.yaml
id: cpwd-2026
authority: cpwd
year: "2026"
currency: INR
confidence: unvalidated   # flips to validated once QS-checked against the source
source: "CPWD Delhi Schedule of Rates 2026, <exact document/edition>"
items:
  - code: "5.9"
    description: "Providing and laying in position cement concrete ..."
    unit: cum
    rate_minor: 850000   # minor units — paise, per CLAUDE.md §4
```

## Loader behavior when this directory is empty

`RulePackLoader` treats an empty (or missing) `rates/` directory as zero
available schedules — every BOQ rate-benchmark request reports every item
`unmatched`, never a fabricated variance. See
`app/modules/pricing_intel/benchmark.py` and its tests for the exact behavior.
