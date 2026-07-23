"""Refresh-token rotation + reuse detection (Doc §5) — pure logic, DB-free.

The security-critical decision (is this refresh valid, expired, or a replay of
an already-used token?) lives in evaluate_refresh() so it can be unit-tested
exhaustively without a database. The service just acts on the verdict.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


def new_refresh() -> tuple[str, str]:
    """Returns (raw_token, sha256_hash). Only the hash is ever stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class RefreshVerdict(StrEnum):
    VALID = "valid"
    INVALID = "invalid"  # not found / revoked / expired
    REUSE = "reuse"  # already used → stolen token, revoke the whole family


class RefreshRowLike(Protocol):
    revoked: bool
    used_at: datetime | None
    expires_at: datetime


def _as_aware(dt: datetime) -> datetime:
    # SQLite stores datetimes tz-naive; treat naive values as UTC so the
    # verdict logic stays correct regardless of the backing store.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def evaluate_refresh(row: RefreshRowLike | None, now: datetime) -> RefreshVerdict:
    if row is None or row.revoked or _as_aware(row.expires_at) < now:
        return RefreshVerdict.INVALID
    if row.used_at is not None:
        return RefreshVerdict.REUSE
    return RefreshVerdict.VALID
