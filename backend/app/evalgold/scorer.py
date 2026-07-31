"""M5 human gold set loader and scorer (TS-233)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MANIFEST = Path(__file__).resolve().parents[3] / "evals" / "gold-set" / "manifest.yaml"


@dataclass(frozen=True)
class GoldCase:
    id: str
    slice: str
    input_dir: Path
    expected_path: Path
    notes: str = ""


@dataclass
class GoldExpected:
    critical_patterns: list[str] = field(default_factory=list)
    optional_patterns: list[str] = field(default_factory=list)
    max_noise: int = 2
    loss_maker_trap: str | None = None


@dataclass
class CaseScore:
    case_id: str
    slice: str
    critical_hits: int
    critical_total: int
    optional_hits: int
    optional_total: int
    noise: int
    critical_recall: float
    overall_recall: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "slice": self.slice,
            "critical_hits": self.critical_hits,
            "critical_total": self.critical_total,
            "optional_hits": self.optional_hits,
            "optional_total": self.optional_total,
            "noise": self.noise,
            "critical_recall": self.critical_recall,
            "overall_recall": self.overall_recall,
        }


@dataclass
class M5Result:
    cases_graded: int = 0
    critical_recall: float | None = None
    overall_recall: float | None = None
    noise_per_tender: float | None = None
    case_scores: list[CaseScore] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "cases_graded": self.cases_graded,
            "critical_recall": self.critical_recall,
            "overall_recall": self.overall_recall,
            "noise_per_tender": self.noise_per_tender,
            "cases": [c.to_dict() for c in self.case_scores],
        }


def load_manifest(path: str | Path | None = None) -> list[GoldCase]:
    manifest_path = Path(path or DEFAULT_MANIFEST)
    raw = yaml.safe_load(manifest_path.read_text())
    root = manifest_path.parent
    cases: list[GoldCase] = []
    for row in raw.get("cases") or []:
        input_dir = (root / row["input_dir"]).resolve()
        expected_path = (root / row["expected_file"]).resolve()
        cases.append(
            GoldCase(
                id=row["id"],
                slice=row["slice"],
                input_dir=input_dir,
                expected_path=expected_path,
                notes=row.get("notes") or "",
            )
        )
    return cases


def load_expected(path: Path) -> GoldExpected:
    raw = yaml.safe_load(path.read_text()) or {}
    return GoldExpected(
        critical_patterns=list(raw.get("critical_patterns") or []),
        optional_patterns=list(raw.get("optional_patterns") or []),
        max_noise=int(raw.get("max_noise", 2)),
        loss_maker_trap=raw.get("loss_maker_trap"),
    )


def score_case(case: GoldCase, findings: list[dict]) -> CaseScore:
    expected = load_expected(case.expected_path)
    found = {f.get("pattern_id") for f in findings if f.get("pattern_id")}
    critical = set(expected.critical_patterns)
    optional = set(expected.optional_patterns)
    allowed = critical | optional

    critical_hits = len(critical & found)
    optional_hits = len(optional & found)
    noise = len({p for p in found if p and p not in allowed})

    critical_recall = critical_hits / len(critical) if critical else 1.0
    gold_total = len(critical | optional)
    overall_hits = critical_hits + optional_hits
    overall_recall = overall_hits / gold_total if gold_total else 1.0

    return CaseScore(
        case_id=case.id,
        slice=case.slice,
        critical_hits=critical_hits,
        critical_total=len(critical),
        optional_hits=optional_hits,
        optional_total=len(optional),
        noise=noise,
        critical_recall=critical_recall,
        overall_recall=overall_recall,
    )


def score_m5(case_scores: list[CaseScore]) -> M5Result:
    if not case_scores:
        return M5Result()
    critical_rates = [c.critical_recall for c in case_scores if c.critical_total > 0]
    overall_rates = [c.overall_recall for c in case_scores]
    return M5Result(
        cases_graded=len(case_scores),
        critical_recall=sum(critical_rates) / len(critical_rates) if critical_rates else None,
        overall_recall=sum(overall_rates) / len(overall_rates),
        noise_per_tender=sum(c.noise for c in case_scores) / len(case_scores),
        case_scores=case_scores,
    )
