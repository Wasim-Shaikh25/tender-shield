"""File storage abstraction. LocalStorage writes to a per-org directory and is
the dev/test backend; an S3 backend (SSE-KMS, per-org prefix, Doc §11.2) is the
production adapter behind the same interface."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def put(self, workspace_id: str, filename: str, data: bytes) -> tuple[str, str]:
        """Store bytes; return (storage_key, sha256_hex)."""
        ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    def put(self, workspace_id: str, filename: str, data: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        ext = Path(filename).suffix
        key = f"{workspace_id}/{sha}{ext}"
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key, sha
