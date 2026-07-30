"""Deterministic severity evaluation (Doc §6.3 — severity is RULE logic, never
LLM vibes). A tiny sandboxed evaluator for the pack's `severity_rule` strings
(e.g. "critical if cap_absent else high if rate_percent_per_week > 0.5 else
medium"). Pure and exhaustively unit-testable."""

from __future__ import annotations

import ast
import logging
import operator

logger = logging.getLogger(__name__)

_CMP = {
    ast.Gt: operator.gt,
    ast.Lt: operator.lt,
    ast.GtE: operator.ge,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}


def _ev(node: ast.AST, ctx: dict):
    if isinstance(node, ast.IfExp):
        return _ev(node.body, ctx) if _ev(node.test, ctx) else _ev(node.orelse, ctx)
    if isinstance(node, ast.BoolOp):
        vals = [_ev(v, ctx) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _ev(node.operand, ctx)
    if isinstance(node, ast.Compare):
        left = _ev(node.left, ctx)
        result = True
        for op, comp in zip(node.ops, node.comparators, strict=False):
            right = _ev(comp, ctx)
            result = result and _CMP[type(op)](left, right)
            left = right
        return result
    if isinstance(node, ast.Name):
        # Bare severity keywords are their own value; everything else is a fact.
        if node.id in _VALID_SEVERITIES:
            return node.id
        if node.id not in ctx:
            raise NameError(f"missing severity fact: {node.id}")
        return ctx[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"unsupported severity expression node: {type(node).__name__}")


def evaluate_severity(rule: str, context: dict, *, default: str = "medium") -> str:
    """Evaluate a severity_rule against a fact context. Falls back to `default`
    on any malformed rule/context rather than raising into the pipeline."""
    try:
        value = _ev(ast.parse(rule, mode="eval").body, context)
    except Exception:
        logger.warning("severity rule failed to evaluate: %r", rule, exc_info=True)
        return default
    if value not in _VALID_SEVERITIES:
        logger.warning("severity rule %r produced non-severity %r", rule, value)
        return default
    return value
