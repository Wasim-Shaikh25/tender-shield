"""M4 metamorphic consistency (TS-229)."""

from app.evalmetamorphic.runner import (
    M4Result,
    MetamorphicCheck,
    check_order_invariance,
    check_redundancy_invariance,
    finding_fingerprints,
    run_m4,
)

__all__ = [
    "M4Result",
    "MetamorphicCheck",
    "check_order_invariance",
    "check_redundancy_invariance",
    "finding_fingerprints",
    "run_m4",
]
