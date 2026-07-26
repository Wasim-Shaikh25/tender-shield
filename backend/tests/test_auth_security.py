"""Isolated unit tests for the pure security + refresh primitives. These have
no DB and no FastAPI, so they can be refactored/rewritten independently."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.modules.auth import refresh as rf
from app.modules.auth import security as sec


def test_password_hash_roundtrip():
    h = sec.hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert sec.verify_password("correct horse battery staple", h)
    assert not sec.verify_password("wrong", h)


def test_access_token_mint_and_decode():
    keys = sec.generate_keypair()
    token = sec.mint_access(
        keys, user_id="u1", workspace_id="o1", role="owner", ttl=timedelta(minutes=15)
    )
    claims = sec.decode_access(token, keys.public_pem)
    assert claims["sub"] == "u1"
    assert claims["workspace"] == "o1"
    assert claims["role"] == "owner"
    assert claims["iss"] == sec.ISSUER


def test_expired_token_rejected():
    keys = sec.generate_keypair()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = sec.mint_access(
        keys, user_id="u", workspace_id="o", role="viewer", ttl=timedelta(minutes=15), now=past
    )
    with pytest.raises(sec.AuthError):
        sec.decode_access(token, keys.public_pem)


def test_token_from_other_key_rejected():
    a, b = sec.generate_keypair(), sec.generate_keypair()
    token = sec.mint_access(
        a, user_id="u", workspace_id="o", role="viewer", ttl=timedelta(minutes=5)
    )
    with pytest.raises(sec.AuthError):
        sec.decode_access(token, b.public_pem)


def test_new_refresh_returns_hash_not_raw():
    raw, h = rf.new_refresh()
    assert h == rf.hash_token(raw)
    assert raw != h


def _row(**kw):
    base = {"revoked": False, "used_at": None, "expires_at": datetime.now(UTC) + timedelta(days=1)}
    base.update(kw)
    return SimpleNamespace(**base)


def test_evaluate_refresh_verdicts():
    now = datetime.now(UTC)
    assert rf.evaluate_refresh(_row(), now) == rf.RefreshVerdict.VALID
    assert rf.evaluate_refresh(None, now) == rf.RefreshVerdict.INVALID
    assert rf.evaluate_refresh(_row(revoked=True), now) == rf.RefreshVerdict.INVALID
    assert (
        rf.evaluate_refresh(_row(expires_at=now - timedelta(seconds=1)), now)
        == rf.RefreshVerdict.INVALID
    )
    assert rf.evaluate_refresh(_row(used_at=now), now) == rf.RefreshVerdict.REUSE
