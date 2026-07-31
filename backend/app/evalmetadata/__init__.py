"""M2 portal-metadata agreement (TS-227)."""

from app.evalmetadata.m2 import (
    ExtractedMetadata,
    FieldComparison,
    M2Result,
    extract_metadata_from_text,
    score_m2,
)

__all__ = [
    "ExtractedMetadata",
    "FieldComparison",
    "M2Result",
    "extract_metadata_from_text",
    "score_m2",
]
