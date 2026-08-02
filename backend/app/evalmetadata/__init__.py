"""M2 portal-metadata agreement (TS-227)."""

from app.evalmetadata.m2 import (
    ExtractedMetadata,
    FieldComparison,
    M2Result,
    extract_metadata_from_text,
    project_duration_months_from_record,
    score_m2,
)

__all__ = [
    "ExtractedMetadata",
    "FieldComparison",
    "M2Result",
    "extract_metadata_from_text",
    "project_duration_months_from_record",
    "score_m2",
]
