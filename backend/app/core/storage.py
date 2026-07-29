"""Pluggable file storage: local filesystem with an optional S3 backend.

The storage backend is selected by `TS_STORAGE_TYPE` ("local" or "s3"). All public
operations are async so that S3 IO does not block the event loop.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import pathlib
from typing import Any, Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".zip",
}

# Max size per file type in bytes.
MAX_UPLOAD_SIZES: dict[str, int] = {
    ".pdf": 50 * 1024 * 1024,
    ".docx": 20 * 1024 * 1024,
    ".xlsx": 10 * 1024 * 1024,
    ".xls": 10 * 1024 * 1024,
    ".csv": 5 * 1024 * 1024,
    ".png": 20 * 1024 * 1024,
    ".jpg": 20 * 1024 * 1024,
    ".jpeg": 20 * 1024 * 1024,
    ".tiff": 50 * 1024 * 1024,
    ".tif": 50 * 1024 * 1024,
    ".zip": 100 * 1024 * 1024,
}

# 100 MB cap for unspecified types.
DEFAULT_MAX_UPLOAD_SIZE = 100 * 1024 * 1024

BOQ_MAX_UPLOAD_SIZE = 10 * 1024 * 1024


def _guess_ext(filename: str, declared_content_type: str | None) -> str | None:
    """Best-effort extension from filename, falling back to content type."""
    ext = pathlib.Path(filename).suffix.lower()
    if ext in ALLOWED_UPLOAD_EXTENSIONS:
        return ext
    ext_from_ct = mimetypes.guess_extension(declared_content_type or "")
    if ext_from_ct and ext_from_ct.lower() in ALLOWED_UPLOAD_EXTENSIONS:
        return ext_from_ct.lower()
    return None


def _content_type_from_ext(ext: str) -> str:
    ct = mimetypes.types_map.get(ext) or mimetypes.types_map.get(ext.upper())
    return ct or "application/octet-stream"


class StorageError(Exception):
    pass


class VirusScanError(StorageError):
    pass


class ValidationError(StorageError):
    pass


class StorageBackend(Protocol):
    async def write(self, key: str, data: bytes, content_type: str) -> str:
        """Persist data and return the public/path key."""
        ...

    async def read(self, key: str) -> bytes:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def url(self, key: str, *, expiry_seconds: int = 3600) -> str | None:
        """Return a pre-signed URL when supported, otherwise None."""
        ...


class LocalStorage:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def write(self, key: str, data: bytes, content_type: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.relative_to(self.root))

    async def read(self, key: str) -> bytes:
        path = self.root / key
        if not path.exists():
            raise StorageError("file_not_found")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self.root / key
        if path.exists():
            path.unlink()

    async def url(self, key: str, *, expiry_seconds: int = 3600) -> str | None:
        return None


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        import boto3
        import botocore.config

        self.bucket = settings.s3_bucket
        self.key_prefix = settings.storage_dir.strip("/") if settings.storage_dir else ""
        session = boto3.Session(
            aws_access_key_id=(
                settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None
            ),
            aws_secret_access_key=(
                settings.s3_secret_access_key.get_secret_value()
                if settings.s3_secret_access_key
                else None
            ),
            region_name=settings.s3_region or None,
        )
        config = botocore.config.Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        )
        endpoint_url = settings.s3_endpoint_url or None
        self.client = session.client(
            "s3", endpoint_url=endpoint_url, config=config
        )

    def _full_key(self, key: str) -> str:
        if self.key_prefix:
            return f"{self.key_prefix}/{key}"
        return key

    async def write(self, key: str, data: bytes, content_type: str) -> str:
        full = self._full_key(key)
        self.client.put_object(Bucket=self.bucket, Key=full, Body=data, ContentType=content_type)
        return full

    async def read(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=self._full_key(key))
        return resp["Body"].read()

    async def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._full_key(key))

    async def url(self, key: str, *, expiry_seconds: int = 3600) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expiry_seconds,
        )


def get_storage(settings: Settings) -> StorageBackend:
    if settings.storage_type == "s3":
        try:
            return S3Storage(settings)
        except Exception as exc:
            logger.warning("s3 storage failed, falling back to local: %s", exc)
    root = pathlib.Path(settings.storage_dir)
    return LocalStorage(root)


def _scan_stub(_data: bytes) -> None:
    """Placeholder virus scan. Production should call a sandboxed scanner or API."""
    return


async def validate_and_store(
    settings: Settings,
    filename: str,
    declared_content_type: str | None,
    data: bytes,
    *,
    max_size: int | None = None,
    workspace_id: str | None = None,
    scan: bool = True,
) -> dict[str, Any]:
    """Validate an upload by extension, magic number, size and (stub) virus scan,
    then write it to the configured storage backend.

    Returns a dict with `key`, `url`, `size`, `content_type`, `sha256`, `ext`.
    """
    ext = _guess_ext(filename, declared_content_type)
    if not ext:
        raise ValidationError("file_type_not_allowed")

    # declared content type should agree with the extension
    expected_ct = _content_type_from_ext(ext)
    if declared_content_type and not declared_content_type.lower().startswith(
        expected_ct.split("/")[0]
    ):
        # Some clients send generic application/octet-stream; only reject obvious mismatches.
        generic_types = {"application/octet-stream", "application/x-zip-compressed"}
        if declared_content_type not in generic_types:
            raise ValidationError("content_type_mismatch")

    # magic number validation
    import filetype

    kind = filetype.guess(data)
    if kind is None:
        # text-based files (CSV, some PDFs) may not have a reliable magic number; trust extension.
        if ext not in (".csv", ".xlsx", ".xls", ".docx", ".zip"):
            raise ValidationError("unrecognised_file_magic")
    else:
        allowed_magics = {
            "application/pdf": {".pdf"},
            "image/png": {".png"},
            "image/jpeg": {".jpg", ".jpeg"},
            "image/tiff": {".tiff", ".tif"},
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
            "application/zip": {".docx", ".xlsx", ".zip"},
        }
        if kind.mime not in allowed_magics or ext not in allowed_magics[kind.mime]:
            raise ValidationError("file_content_does_not_match_extension")

    size = len(data)
    limit = max_size or MAX_UPLOAD_SIZES.get(ext, DEFAULT_MAX_UPLOAD_SIZE)
    if size > limit:
        raise ValidationError(f"file_too_large: limit {limit} bytes")

    if scan:
        _scan_stub(data)

    storage = get_storage(settings)

    # Derive a safe key: workspace-scoped to avoid collisions/exposure.
    digest = hashlib.sha256(data).hexdigest()
    safe_name = pathlib.Path(filename).name
    # strip any leading dots / path traversal
    safe_name = pathlib.Path(safe_name).name
    prefix = f"workspace/{workspace_id}/" if workspace_id else "uploads/"
    key = f"{prefix}{digest[:16]}-{safe_name}"

    stored_key = await storage.write(key, data, expected_ct)
    url = await storage.url(stored_key) or f"/api/files/{stored_key}"

    return {
        "key": stored_key,
        "url": url,
        "size": size,
        "content_type": expected_ct,
        "sha256": digest,
        "ext": ext,
    }
