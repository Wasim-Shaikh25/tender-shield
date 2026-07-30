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
    return Finding(
        kind=FindingKind.BOQ_DEFECT,
        category=category,
        severity=severity,
        title=title,
        detail=detail,
        source=FindingSource.DETERMINISTIC_CHECK,
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
