"""Pluggable file storage: local filesystem with an optional S3 backend.

The storage backend is selected by `TS_STORAGE_TYPE` ("local" or "s3"). All public
operations are async so that S3 IO does not block the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import pathlib
import re
import socket
import struct
from typing import Any, Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Return a filename safe for storage keys and HTTP Content-Disposition.

    Removes path separators, control characters, CR/LF, quotes, and semicolons to
    prevent response-splitting / header-injection attacks.
    """
    # Take only the basename; collapse path traversal attempts.
    base = pathlib.Path(name).name
    # Remove control characters and known dangerous punctuation.
    base = re.sub(r"[\x00-\x1f\x7f\"';%?#&=\\]", "", base)
    # Collapse whitespace and ensure the result is non-empty.
    base = base.strip() or "file"
    return base


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


class ValidationError(StorageError):
    pass


class VirusScanError(ValidationError):
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
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return str(path.relative_to(self.root))

    async def read(self, key: str) -> bytes:
        path = self.root / key
        if not await asyncio.to_thread(path.exists):
            raise StorageError("file_not_found")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self.root / key
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)

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
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=full,
            Body=data,
            ContentType=content_type,
        )
        return full

    async def read(self, key: str) -> bytes:
        resp = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=self._full_key(key)
        )
        return await asyncio.to_thread(resp["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=self._full_key(key)
        )

    async def url(self, key: str, *, expiry_seconds: int = 3600) -> str | None:
        return await asyncio.to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expiry_seconds,
        )


def get_storage(settings: Settings) -> StorageBackend:
    if settings.storage_type == "s3":
        try:
            return S3Storage(settings)
        except Exception as exc:
            if settings.is_prod():
                raise StorageError(f"s3_initialisation_failed: {exc}") from exc
            logger.warning("s3 storage failed, falling back to local: %s", exc)
    root = pathlib.Path(settings.storage_dir)
    return LocalStorage(root)


def _clamd_scan(socket_path: str, data: bytes) -> None:
    """Stream `data` to a local clamd daemon and fail closed on any FOUND reply."""
    try:
        if socket_path.startswith("tcp://"):
            host, _, port = socket_path[6:].partition(":")
            sock = socket.create_connection((host, int(port)), timeout=10)
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(socket_path)
    except OSError as exc:
        raise VirusScanError(f"scanner_unavailable: {exc}") from exc

    try:
        sock.sendall(b"zINSTREAM\0")
        chunk_size = 4096
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
        sock.sendall(struct.pack(">I", 0))
        response = b""
        while True:
            try:
                part = sock.recv(4096)
                if not part:
                    break
                response += part
            except TimeoutError:
                break
    finally:
        sock.close()

    if b"FOUND" in response:
        finding = response.decode("utf-8", errors="replace").strip()
        raise VirusScanError(f"virus_detected: {finding}")
    if not response.strip().endswith(b"OK"):
        raise VirusScanError(f"scan_unavailable: {response.decode('utf-8', errors='replace')}")


def _quarantine(quarantine_dir: str, filename: str, data: bytes) -> None:
    qdir = pathlib.Path(quarantine_dir)
    qdir.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(filename) or "quarantine"
    qpath = qdir / f"{safe}.{hashlib.sha256(data).hexdigest()[:16]}"
    qpath.write_bytes(data)


def _scan(settings: Settings, filename: str, data: bytes) -> None:
    """Validate an upload with a configured clamd scanner; quarantine and reject on detection."""
    socket_path = settings.clamd_socket
    if not socket_path:
        logger.warning("Virus scanning skipped: TS_CLAMD_SOCKET not configured")
        return
    try:
        _clamd_scan(socket_path, data)
    except VirusScanError:
        if settings.quarantine_dir:
            _quarantine(settings.quarantine_dir, filename, data)
        raise


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
        _scan(settings, filename, data)

    storage = get_storage(settings)

    # Derive a safe key: workspace-scoped to avoid collisions/exposure.
    digest = hashlib.sha256(data).hexdigest()
    safe_name = sanitize_filename(filename)
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
