"""Deterministic BOQ engine (Doc §6.4) — zero LLM, bit-reproducible.

Pure functions over a pandas DataFrame; DuckDB runs the check SQL. Numbers here
are never AI opinions — same input always yields identical findings.
"""

from __future__ import annotations

import re

import duckdb
import pandas as pd

from app.core.contracts.findings import (
    Finding,
    FindingKind,
    FindingSource,
    Severity,
)

REQUIRED_COLUMNS = {"src_row", "description", "unit_raw", "qty", "rate", "amount"}


def normalize(df: pd.DataFrame, unit_canon: dict[str, str]) -> pd.DataFrame:
    """Canonicalize units and compute amount_calc = round(qty*rate, 2)."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"BOQ frame missing columns: {sorted(missing)}")
    df = df.copy()
    if "item_code" not in df.columns:  # optional column the check SQL displays
        df["item_code"] = ""
    raw = df["unit_raw"].astype(str).str.strip().str.lower()
    df["unit_canon"] = raw.map(unit_canon).fillna(raw)
    df["amount_calc"] = (
        pd.to_numeric(df["qty"], errors="coerce") * pd.to_numeric(df["rate"], errors="coerce")
    ).round(2)
    return df


CHECKS_SQL = """
SELECT
  src_row, item_code, description, unit_canon, qty, rate, amount, amount_calc,
  abs(amount - amount_calc) > {tol}                       AS arith_error,
  (rate IS NULL OR rate = 0)                              AS blank_rate,
  count(*) OVER (PARTITION BY lower(trim(description)), unit_canon) > 1
                                                          AS possible_duplicate,
  qty > quantile_cont(qty, {q}) OVER (PARTITION BY unit_canon) * {mult}
                                                          AS qty_outlier
FROM df
ORDER BY src_row
"""


def _defect(category: str, severity: Severity, title: str, detail: str, row) -> Finding:
    src_row = row.get("src_row")
    source_page = int(src_row) if src_row is not None else None
    return Finding(
        kind=FindingKind.BOQ_DEFECT,
        category=category,
        severity=severity,
        title=title,
        detail=detail,
        source=FindingSource.DETERMINISTIC_CHECK,
        source_page=source_page,
        suggested_action="Verify against the source workbook before bid submission.",
    )


def run_checks(
    df: pd.DataFrame,
    *,
    tolerance: float = 1.0,
    outlier_quantile: float = 0.99,
    outlier_multiplier: float = 3,
) -> list[Finding]:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"BOQ frame missing columns: {sorted(missing)}")
    if "amount_calc" not in df.columns:
        raise ValueError("call normalize() before run_checks()")

    sql = CHECKS_SQL.format(tol=tolerance, q=outlier_quantile, mult=outlier_multiplier)
    with duckdb.connect() as con:
        con.register("df", df)
        rows = con.execute(sql).fetchdf().to_dict("records")

        totals = con.execute(
            "SELECT sum(amount) a, sum(amount_calc) c FROM df"
        ).fetchone()

    findings: list[Finding] = []
    for r in rows:
        row_ref = f"row {int(r['src_row'])} ({r['item_code']}: {r['description']})"
        if r["arith_error"]:
            findings.append(
                _defect(
                    "arith",
                    Severity.HIGH,
                    f"Arithmetic error at {row_ref}",
                    f"amount {r['amount']:.2f} ≠ qty×rate {r['amount_calc']:.2f}.",
                    r,
                )
            )
        if r["blank_rate"]:
            findings.append(
                _defect(
                    "blank_rate",
                    Severity.MEDIUM,
                    f"Blank/zero rate at {row_ref}",
                    "Rate is missing or zero — item will be under-priced.",
                    r,
                )
            )
        if r["possible_duplicate"]:
            findings.append(
                _defect(
                    "duplicate",
                    Severity.MEDIUM,
                    f"Possible duplicate at {row_ref}",
                    "Same description and unit appears more than once.",
                    r,
                )
            )
        if r["qty_outlier"]:
            findings.append(
                _defect(
                    "qty_outlier",
                    Severity.LOW,
                    f"Quantity outlier at {row_ref}",
                    "Quantity far exceeds others of the same unit — confirm it.",
                    r,
                )
            )

    if totals[0] is not None and abs(totals[0] - totals[1]) > tolerance:
        findings.append(
            Finding(
                kind=FindingKind.BOQ_DEFECT,
                category="grand_total",
                severity=Severity.HIGH,
                title="Grand-total / carry-forward mismatch",
                detail=f"Sum of amounts {totals[0]:.2f} ≠ sum of qty×rate {totals[1]:.2f}.",
                source=FindingSource.DETERMINISTIC_CHECK,
                suggested_action="Recheck subtotals and carried-forward figures.",
            )
        )
    return findings


class SpecTextIndex:
    """Minimal page-aware text index built from a document with [pN] markers."""

    def __init__(self, text: str) -> None:
        self._pages: list[tuple[int, str]] = []
        current = 1
        for line in text.splitlines():
            m = re.fullmatch(r"\s*\[p(\d+)\]\s*", line)
            if m:
                current = int(m.group(1))
                continue
            self._pages.append((current, line.lower()))

    def contains(self, phrase: str) -> bool:
        needle = phrase.lower()
        return any(needle in line for _, line in self._pages)

    def page_of(self, phrase: str) -> int | None:
        needle = phrase.lower()
        for page, line in self._pages:
            if needle in line:
                return page
        return None


def scope_gaps(df: pd.DataFrame, spec: SpecTextIndex, checklist) -> list[Finding]:
    """A gap fires when a spec trigger is present AND no BOQ line matches the
    item's patterns (Doc §6.4). `checklist` is a rulepacks TradeChecklist."""
    descriptions = df["description"].astype(str).str.lower()
    findings: list[Finding] = []
    for item in checklist.items:
        matched_trigger = next((t for t in item.triggers if spec.contains(t)), None)
        if matched_trigger is None:
            continue
        present = descriptions.str.contains(
            "|".join(re.escape(p.lower()) for p in item.boq_patterns), regex=True
        ).any()
        if present:
            continue
        findings.append(
            Finding(
                kind=FindingKind.SCOPE_GAP,
                category=item.key,
                severity=Severity(item.severity),
                title=f"No BOQ item for {item.label}",
                detail=(
                    f"Spec indicates {item.label} is required "
                    f"(trigger: '{matched_trigger}') but no BOQ line covers it."
                ),
                source=FindingSource.DETERMINISTIC_CHECK,
                source_page=spec.page_of(matched_trigger),
                affected_trades=[checklist.trade],
                suggested_action="Raise a clarification or price it as an assumption.",
            )
        )
    return findings


_STOPWORDS = {"the", "and", "for", "of", "in", "to", "a", "an", "on", "at", "by", "with"}


def _token_overlap(activity_name: str, description: str) -> float:
    """Simple token overlap for matching schedule activities to BOQ descriptions."""
    name_tokens = {
        t
        for t in re.findall(r"[a-z0-9]+", activity_name.lower())
        if t not in _STOPWORDS and len(t) > 2
    }
    desc_tokens = set(re.findall(r"[a-z0-9]+", description.lower()))
    if not name_tokens:
        return 0.0
    return len(name_tokens & desc_tokens) / len(name_tokens)


def cross_check_schedule(df: pd.DataFrame, activities: list[dict]) -> list[Finding]:
    """Cross-check the BOQ against an imported programme/schedule (TS-318).

    Fires a `SCOPE_GAP` finding when a schedule activity has no likely matching
    BOQ item, and an `info` finding when a BOQ item has no likely schedule match.
    Matching is conservative token overlap on meaningful words.
    """
    if df.empty or not activities:
        return []
    findings: list[Finding] = []
    descriptions = df["description"].astype(str).str.lower().tolist()
    for idx, act in enumerate(activities):
        name = act.get("name", "")
        if not name:
            continue
        best = max((_token_overlap(name, desc) for desc in descriptions), default=0.0)
        if best < 0.5:
            findings.append(
                Finding(
                    kind=FindingKind.SCOPE_GAP,
                    category="schedule_mismatch",
                    severity=Severity.MEDIUM,
                    title=f"Schedule activity '{name}' has no matching BOQ item",
                    detail=(
                        f"Programme activity #{idx + 1} '{name}' could not be matched "
                        f"to any BOQ line. Confirm it is priced or raise a clarification."
                    ),
                    source=FindingSource.DETERMINISTIC_CHECK,
                    affected_trades=[trade]
                    if (trade := act.get("metadata", {}).get("trade"))
                    else [],
                    suggested_action=(
                        "Add the activity to the BOQ or confirm it is covered"
                        " under a preliminaries item."
                    ),
                )
            )
    for row in df.itertuples(index=False):
        desc = str(row.description).lower()
        best = max((_token_overlap(act.get("name", ""), desc) for act in activities), default=0.0)
        if best < 0.5:
            findings.append(
                Finding(
                    kind=FindingKind.BOQ_DEFECT,
                    category="schedule_mismatch",
                    severity=Severity.LOW,
                    title=f"BOQ item '{row.description[:60]}' not found in schedule",
                    detail=(
                        "This BOQ line does not appear to have a corresponding programme activity."
                    ),
                    source=FindingSource.DETERMINISTIC_CHECK,
                    source_page=(
                        int(row.src_row) if getattr(row, "src_row", None) is not None else None
                    ),
                    suggested_action=(
                        "Verify the item is in the programme or is non-scheduled work."
                    ),
                )
            )
    return findings


def historical_scope_suggestions(df: pd.DataFrame, historical_gaps: list[dict]) -> list[Finding]:
    """Suggest scope items that were historically missed but are not in the
    current BOQ (TS-319). `historical_gaps` come from past scope-gap findings.
    """
    if df.empty or not historical_gaps:
        return []
    findings: list[Finding] = []
    descriptions = df["description"].astype(str).str.lower()
    for gap in historical_gaps:
        keywords = [k.lower() for k in gap.get("keywords", []) if k]
        if not keywords:
            continue
        pattern = "|".join(re.escape(k) for k in keywords)
        if descriptions.str.contains(pattern, regex=True, na=False).any():
            continue
        findings.append(
            Finding(
                kind=FindingKind.SCOPE_GAP,
                category=f"historical:{gap['category']}",
                severity=Severity(gap.get("severity", "low")),
                title=f"Consider: {gap['label']}",
                detail=(
                    f"This item was missed in {gap.get('historical_count', 1)} prior "
                    f"opportunity(s). Verify whether it should be priced in this BOQ."
                ),
                source=FindingSource.DETERMINISTIC_CHECK,
                affected_trades=[],
                suggested_action="Check the spec and drawings, and add a BOQ line if required.",
            )
        )
    return findings
