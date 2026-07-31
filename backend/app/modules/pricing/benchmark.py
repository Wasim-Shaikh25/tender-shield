"""Schedule-of-Rates benchmarking (TS-205).

Compares BOQ rates against a published rate schedule with two disclosed
confidence bands — never blended (`specs/modules/pricing-intel.md` §2):

* **code** — the schedule's own item code appears in the BOQ row. High
  confidence; this is what the headline portfolio variance is computed from.
* **description** — no code match, but the normalized descriptions are similar
  above a threshold. Reported as indicative, excluded from the headline number.
* **unmatched** — neither. Reported as unmatched, never force-matched into
  either band.

Pure functions over a normalized BOQ dataframe (already produced by the `boq`
module's `BoqEngine`, consumed via the registry — this module never imports
`app.modules.boq`) and a `RateSchedule` from the rulepack loader.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any

_DESCRIPTION_MATCH_THRESHOLD = 0.82


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


@dataclass(frozen=True)
class RateMatch:
    src_row: int
    boq_description: str
    boq_unit: str
    boq_rate_minor: int
    matched_by: str  # "code" | "description" | "unmatched"
    schedule_code: str | None = None
    schedule_description: str | None = None
    schedule_rate_minor: int | None = None
    variance_minor: int | None = None
    variance_pct: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "src_row": self.src_row,
            "boq_description": self.boq_description,
            "boq_unit": self.boq_unit,
            "boq_rate_minor": self.boq_rate_minor,
            "matched_by": self.matched_by,
            "schedule_code": self.schedule_code,
            "schedule_description": self.schedule_description,
            "schedule_rate_minor": self.schedule_rate_minor,
            "variance_minor": self.variance_minor,
            "variance_pct": self.variance_pct,
        }


@dataclass(frozen=True)
class BenchmarkResult:
    matches: list[RateMatch]
    schedule_id: str | None
    schedule_confidence: str | None

    @property
    def code_matched(self) -> list[RateMatch]:
        return [m for m in self.matches if m.matched_by == "code"]

    @property
    def description_matched(self) -> list[RateMatch]:
        return [m for m in self.matches if m.matched_by == "description"]

    @property
    def unmatched(self) -> list[RateMatch]:
        return [m for m in self.matches if m.matched_by == "unmatched"]

    @property
    def headline_variance_pct(self) -> float | None:
        """Value-weighted portfolio variance over **code-matched items only**
        (spec §2) — precision over coverage. `None` when nothing code-matched,
        never a coverage-diluted approximation."""
        priced = self.code_matched
        if not priced:
            return None
        total_boq = sum(m.boq_rate_minor for m in priced)
        total_schedule = sum(m.schedule_rate_minor or 0 for m in priced)
        if total_schedule == 0:
            return None
        return (total_boq - total_schedule) / total_schedule * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "schedule_confidence": self.schedule_confidence,
            "headline_variance_pct": self.headline_variance_pct,
            "code_matched": [m.to_dict() for m in self.code_matched],
            "description_matched": [m.to_dict() for m in self.description_matched],
            "unmatched": [m.to_dict() for m in self.unmatched],
        }


def benchmark(boq_rows: list[dict], schedule: Any | None) -> BenchmarkResult:
    """`boq_rows` are normalized BOQ records with `src_row`, `item_code`,
    `description`, `unit_canon`, `rate`. `schedule` is a `RateSchedule` (or
    `None` — an empty/missing schedule reports every row unmatched, never an
    error; see `rulepacks/in-works/rates/README.md`)."""
    items = list(schedule.items) if schedule is not None else []
    by_code = {str(i.code).strip(): i for i in items}

    matches: list[RateMatch] = []
    for row in boq_rows:
        src_row = int(row.get("src_row", 0))
        description = str(row.get("description", ""))
        unit = str(row.get("unit_canon") or row.get("unit_raw") or "")
        try:
            boq_rate_minor = int(round(float(row.get("rate") or 0) * 100))
        except (TypeError, ValueError):
            boq_rate_minor = 0

        code = str(row.get("item_code") or "").strip()
        schedule_item = by_code.get(code) if code else None

        if schedule_item is not None:
            variance = boq_rate_minor - schedule_item.rate_minor
            variance_pct = (
                (variance / schedule_item.rate_minor * 100.0)
                if schedule_item.rate_minor
                else None
            )
            matches.append(
                RateMatch(
                    src_row=src_row,
                    boq_description=description,
                    boq_unit=unit,
                    boq_rate_minor=boq_rate_minor,
                    matched_by="code",
                    schedule_code=schedule_item.code,
                    schedule_description=schedule_item.description,
                    schedule_rate_minor=schedule_item.rate_minor,
                    variance_minor=variance,
                    variance_pct=variance_pct,
                )
            )
            continue

        best_item, best_ratio = None, 0.0
        nd = _norm(description)
        for item in items:
            ratio = difflib.SequenceMatcher(None, nd, _norm(item.description)).ratio()
            if ratio > best_ratio:
                best_item, best_ratio = item, ratio

        if best_item is not None and best_ratio >= _DESCRIPTION_MATCH_THRESHOLD:
            variance = boq_rate_minor - best_item.rate_minor
            variance_pct = (
                (variance / best_item.rate_minor * 100.0) if best_item.rate_minor else None
            )
            matches.append(
                RateMatch(
                    src_row=src_row,
                    boq_description=description,
                    boq_unit=unit,
                    boq_rate_minor=boq_rate_minor,
                    matched_by="description",
                    schedule_code=best_item.code,
                    schedule_description=best_item.description,
                    schedule_rate_minor=best_item.rate_minor,
                    variance_minor=variance,
                    variance_pct=variance_pct,
                )
            )
            continue

        matches.append(
            RateMatch(
                src_row=src_row,
                boq_description=description,
                boq_unit=unit,
                boq_rate_minor=boq_rate_minor,
                matched_by="unmatched",
            )
        )

    return BenchmarkResult(
        matches=matches,
        schedule_id=schedule.id if schedule is not None else None,
        schedule_confidence=schedule.confidence if schedule is not None else None,
    )
