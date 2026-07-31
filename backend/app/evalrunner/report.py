"""Scorecard and regression diff (TS-231).

Turns `evals/runs/<run_id>/results.jsonl` into the human-readable report the
whole point of the eval harness depends on. Reports **only what the current
harness actually measures** — M1 (this phase) plus cost/timing/BOQ/findings
distributions computed from `TenderResult`. Metrics that need M2/M3/M5
(TS-227/228/233) are listed as explicitly **not yet available**, never
approximated or invented — a fabricated number in a report about a system whose
entire premise is "no invented numbers" would be the wrong kind of ironic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Regression bar from specs/eval-at-scale.md §3.4 / Build Doc §11.5: a >2pt drop
# on a headline pass-rate metric blocks the change that caused it.
_REGRESSION_POINTS = 0.02
_CRASH_RATE_REGRESSION_POINTS = 0.01  # matches the <1% crash-rate bar itself


@dataclass
class RunData:
    run_id: str
    run_dir: Path
    manifest: dict[str, Any]
    results: list[dict[str, Any]]

    @property
    def corpus_root(self) -> str:
        return self.manifest.get("corpus_root", "")

    @property
    def shard(self) -> str:
        return self.manifest.get("shard", "")

    @property
    def started_at(self) -> str:
        return self.manifest.get("started_at", "")


def load_run(run_dir: str | Path) -> RunData:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    results_path = run_dir / "results.jsonl"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    results = []
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return RunData(run_id=run_dir.name, run_dir=run_dir, manifest=manifest, results=results)


def find_baseline(runs_root: str | Path, current: RunData) -> RunData | None:
    """The most recent other run on the same corpus + shard, started before the
    current run. `None` if this is the first run on this slice — that is a
    normal, reportable state, not an error."""
    runs_root = Path(runs_root)
    if not runs_root.exists():
        return None
    candidates: list[RunData] = []
    for child in runs_root.iterdir():
        if not child.is_dir() or child.name == current.run_id or child.name.startswith("_"):
            continue
        if not (child / "manifest.json").exists():
            continue
        run = load_run(child)
        if run.corpus_root == current.corpus_root and run.shard == current.shard:
            if run.started_at and run.started_at < current.started_at:
                candidates.append(run)
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.started_at)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(int(round(pct * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


@dataclass
class Metrics:
    tenders_graded: int = 0
    m1_pass_rate: float | None = None
    quote_verbatim_rate: float | None = None
    citation_completeness_rate: float | None = None
    crash_rate: float | None = None          # unknown_error + parse_failed + ocr_failed + timeout
    invariant_violation_rate: float | None = None
    llm_error_rate: float | None = None
    findings_per_tender: dict[str, float | None] = field(default_factory=dict)
    wall_seconds: dict[str, float | None] = field(default_factory=dict)
    cost_minor: dict[str, float | None] = field(default_factory=dict)
    boq_status_counts: dict[str, int] = field(default_factory=dict)
    failure_reason_counts: dict[str, int] = field(default_factory=dict)
    violations_by_invariant: dict[str, int] = field(default_factory=dict)
    not_yet_available: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenders_graded": self.tenders_graded,
            "m1_pass_rate": self.m1_pass_rate,
            "quote_verbatim_rate": self.quote_verbatim_rate,
            "citation_completeness_rate": self.citation_completeness_rate,
            "crash_rate": self.crash_rate,
            "invariant_violation_rate": self.invariant_violation_rate,
            "llm_error_rate": self.llm_error_rate,
            "findings_per_tender": self.findings_per_tender,
            "wall_seconds": self.wall_seconds,
            "cost_minor": self.cost_minor,
            "boq_status_counts": self.boq_status_counts,
            "failure_reason_counts": self.failure_reason_counts,
            "violations_by_invariant": self.violations_by_invariant,
            "not_yet_available": self.not_yet_available,
        }


_CRASH_REASONS = {"parse_failed", "ocr_failed", "timeout", "unknown_error"}


def compute_metrics(run: RunData) -> Metrics:
    m = Metrics(tenders_graded=len(run.results))
    if not run.results:
        m.not_yet_available = [
            "M2 (portal-metadata agreement) — TS-227",
            "M3 (outcome backtest) — TS-228",
            "M5 (human gold set) — TS-233",
        ]
        return m

    n = len(run.results)
    m1_graded = [r for r in run.results if r.get("m1_ok") is not None]
    if m1_graded:
        m.m1_pass_rate = sum(1 for r in m1_graded if r["m1_ok"]) / len(m1_graded)

    violations_by_invariant: dict[str, int] = {}
    for r in run.results:
        for invariant, count in (r.get("m1_summary") or {}).get(
            "violations_by_invariant", {}
        ).items():
            violations_by_invariant[invariant] = violations_by_invariant.get(invariant, 0) + count
    m.violations_by_invariant = violations_by_invariant

    if m1_graded:
        # A per-tender pass rate needs per-tender violation presence, not the
        # aggregated invariant counts above.
        quote_violated_tenders = sum(
            1
            for r in m1_graded
            if (r.get("m1_summary") or {})
            .get("violations_by_invariant", {})
            .get("quote_integrity", 0)
            > 0
        )
        citation_violated_tenders = sum(
            1
            for r in m1_graded
            if (r.get("m1_summary") or {})
            .get("violations_by_invariant", {})
            .get("citation_completeness", 0)
            > 0
        )
        m.quote_verbatim_rate = 1 - (quote_violated_tenders / len(m1_graded))
        m.citation_completeness_rate = 1 - (citation_violated_tenders / len(m1_graded))

    failure_reasons: dict[str, int] = {}
    for r in run.results:
        if r.get("status") == "failed":
            reason = r.get("failure_reason") or "unknown_error"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
    m.failure_reason_counts = failure_reasons

    crash_count = sum(v for k, v in failure_reasons.items() if k in _CRASH_REASONS)
    m.crash_rate = crash_count / n
    m.invariant_violation_rate = failure_reasons.get("invariant_violation", 0) / n
    m.llm_error_rate = failure_reasons.get("llm_error", 0) / n

    findings_counts = [float(r.get("findings_count") or 0) for r in run.results]
    m.findings_per_tender = {
        "min": min(findings_counts) if findings_counts else None,
        "p50": _percentile(findings_counts, 0.5),
        "p95": _percentile(findings_counts, 0.95),
        "max": max(findings_counts) if findings_counts else None,
    }

    wall = [float(r.get("wall_seconds") or 0) for r in run.results]
    m.wall_seconds = {"p50": _percentile(wall, 0.5), "p95": _percentile(wall, 0.95)}

    priced = [
        float(r["cost_minor"])
        for r in run.results
        if r.get("fully_priced") and r.get("cost_minor") is not None
    ]
    m.cost_minor = {"p50": _percentile(priced, 0.5), "p95": _percentile(priced, 0.95)}

    boq_counts: dict[str, int] = {}
    for r in run.results:
        status = r.get("boq_status") or "not_applicable"
        boq_counts[status] = boq_counts.get(status, 0) + 1
    m.boq_status_counts = boq_counts

    m.not_yet_available = [
        "Deadline / tender-value exact match vs portal metadata (M2) — TS-227",
        "L1 backtest MAPE (M3) — TS-228",
        "Metamorphic consistency (M4) — TS-229",
        "Gold-set recall / critical recall / noise (M5) — TS-233",
    ]
    return m


@dataclass
class RegressionFinding:
    metric: str
    baseline: float
    current: float
    delta: float
    blocking: bool


def diff_metrics(baseline: Metrics | None, current: Metrics) -> list[RegressionFinding]:
    """Compares headline pass-rate metrics against `_REGRESSION_POINTS`
    (Build Doc §11.5's ">2pt drop blocks the change"). Wall-clock and cost are
    reported in the scorecard as trend information but are not gated here —
    the spec states an exact point threshold only for pass-rate metrics."""
    if baseline is None:
        return []
    findings: list[RegressionFinding] = []

    def _check(name: str, base: float | None, cur: float | None, *, higher_is_better: bool):
        if base is None or cur is None:
            return
        delta = cur - base
        threshold = _CRASH_RATE_REGRESSION_POINTS if name == "crash_rate" else _REGRESSION_POINTS
        regressed = (delta < -threshold) if higher_is_better else (delta > threshold)
        if regressed:
            findings.append(RegressionFinding(name, base, cur, delta, blocking=True))

    _check("m1_pass_rate", baseline.m1_pass_rate, current.m1_pass_rate, higher_is_better=True)
    _check(
        "quote_verbatim_rate",
        baseline.quote_verbatim_rate,
        current.quote_verbatim_rate,
        higher_is_better=True,
    )
    _check(
        "citation_completeness_rate",
        baseline.citation_completeness_rate,
        current.citation_completeness_rate,
        higher_is_better=True,
    )
    _check("crash_rate", baseline.crash_rate, current.crash_rate, higher_is_better=False)
    return findings


def _fmt_pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _fmt_num(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}"


def render_scorecard(run: RunData, metrics: Metrics) -> str:
    lines = [
        f"# Eval Scorecard — `{run.run_id}`",
        "",
        f"Corpus: `{run.corpus_root}` · shard `{run.shard}` · "
        f"rulepack `{run.manifest.get('rulepack_version', '?')}` · "
        f"model `{run.manifest.get('model_id', '?')}`",
        "",
        f"Tenders in shard: {run.manifest.get('tenders_in_shard', '?')} · "
        f"run: {run.manifest.get('tenders_run', '?')} · "
        f"cached: {run.manifest.get('tenders_cached', '?')} · "
        f"resumed-skip: {run.manifest.get('tenders_resumed_skip', '?')}",
        "",
        "## Headline metrics",
        "",
        "| Metric | Bar | Actual | Status |",
        "|---|---|---|---|",
    ]

    def row(label: str, bar: str, value: str, ok: bool | None) -> str:
        status = "n/a" if ok is None else ("✅" if ok else "❌")
        return f"| {label} | {bar} | {value} | {status} |"

    m1_ok = metrics.m1_pass_rate == 1.0 if metrics.m1_pass_rate is not None else None
    lines.append(row("M1 structural pass rate", "100%", _fmt_pct(metrics.m1_pass_rate), m1_ok))
    quote_ok = (
        metrics.quote_verbatim_rate == 1.0 if metrics.quote_verbatim_rate is not None else None
    )
    lines.append(
        row("Quote-verbatim rate", "100%", _fmt_pct(metrics.quote_verbatim_rate), quote_ok)
    )
    crash_ok = metrics.crash_rate < 0.01 if metrics.crash_rate is not None else None
    lines.append(
        row("Crash / parse / timeout rate", "< 1%", _fmt_pct(metrics.crash_rate), crash_ok)
    )
    lines += [
        row("Deadline / tender-value match vs portal", "≥ 95%", "n/a — TS-227", None),
        row("L1 backtest MAPE", "baseline first", "n/a — TS-228", None),
        row("Gold-set critical recall", "≥ 90%", "n/a — TS-233", None),
    ]

    lines += [
        "",
        "## Findings, timing and cost (informational — not blocking)",
        "",
        "| | p50 | p95 |",
        "|---|---|---|",
        f"| Findings per tender | {_fmt_num(metrics.findings_per_tender.get('p50'))} | "
        f"{_fmt_num(metrics.findings_per_tender.get('p95'))} |",
        f"| Wall-clock (s) | {_fmt_num(metrics.wall_seconds.get('p50'))} | "
        f"{_fmt_num(metrics.wall_seconds.get('p95'))} |",
        f"| Cost (minor units, fully-priced tenders only) | "
        f"{_fmt_num(metrics.cost_minor.get('p50'))} | {_fmt_num(metrics.cost_minor.get('p95'))} |",
    ]

    if metrics.boq_status_counts:
        lines += ["", "## BOQ status", "", "| Status | Count |", "|---|---|"]
        for status, count in sorted(metrics.boq_status_counts.items()):
            lines.append(f"| {status} | {count} |")

    if metrics.failure_reason_counts:
        lines += ["", "## Failures by reason", "", "| Reason | Count |", "|---|---|"]
        for reason, count in sorted(metrics.failure_reason_counts.items()):
            lines.append(f"| {reason} | {count} |")

    if metrics.violations_by_invariant:
        lines += ["", "## M1 violations by invariant", "", "| Invariant | Count |", "|---|---|"]
        for name, count in sorted(metrics.violations_by_invariant.items()):
            lines.append(f"| {name} | {count} |")

    if metrics.not_yet_available:
        lines += ["", "## Not yet available", ""]
        lines += [f"- {item}" for item in metrics.not_yet_available]

    lines.append("")
    return "\n".join(lines)


def render_regressions(
    baseline: RunData | None, current: RunData, findings: list[RegressionFinding]
) -> str:
    if baseline is None:
        return (
            f"# Regression Diff — `{current.run_id}`\n\n"
            "No prior run found on this corpus + shard. This is the baseline "
            "for future comparisons.\n"
        )

    lines = [
        f"# Regression Diff — `{current.run_id}` vs `{baseline.run_id}`",
        "",
        f"Baseline started: `{baseline.started_at}` · current started: `{current.started_at}`",
        "",
    ]
    if not findings:
        lines.append(
            "No regression on any headline metric (bar: >2pt drop, or >1pt for crash rate)."
        )
        lines.append("")
        return "\n".join(lines)

    lines += [
        "**BLOCKING** — the following headline metrics regressed:",
        "",
        "| Metric | Baseline | Current | Δ |",
        "|---|---|---|---|",
    ]
    for f in findings:
        lines.append(
            f"| {f.metric} | {_fmt_pct(f.baseline)} | {_fmt_pct(f.current)} | {_fmt_pct(f.delta)} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(
    run_dir: str | Path, runs_root: str | Path
) -> tuple[Metrics, list[RegressionFinding]]:
    """Writes `scorecard.md` and `regressions.md` into `run_dir`. Returns the
    computed metrics and any blocking regressions, so a CLI can set an exit code
    without re-parsing its own output."""
    run = load_run(run_dir)
    metrics = compute_metrics(run)
    baseline_run = find_baseline(runs_root, run)
    baseline_metrics = compute_metrics(baseline_run) if baseline_run else None
    findings = diff_metrics(baseline_metrics, metrics)

    run_path = Path(run_dir)
    (run_path / "scorecard.md").write_text(render_scorecard(run, metrics))
    (run_path / "regressions.md").write_text(render_regressions(baseline_run, run, findings))
    return metrics, findings
