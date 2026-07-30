"""Application factory and production startup guard."""

import pytest

from app.core.config import Settings
from app.main import _validate_prod_settings


def test_prod_guard_rejects_cors_wildcard():
    settings = Settings(
        env="prod",
        cors_origins="https://app.example.com,*",
        allowed_hosts="app.example.com",
        razorpay_webhook_secret="not-a-real-secret-for-tests-123",
        jwt_private_key="dummy",
        jwt_public_key="dummy",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_CORS_ORIGINS" in str(exc.value)


def test_prod_guard_rejects_allowed_hosts_wildcard():
    settings = Settings(
        env="prod",
        cors_origins="https://app.example.com",
        allowed_hosts="*,app.example.com",
        razorpay_webhook_secret="not-a-real-secret-for-tests-123",
        jwt_private_key="dummy",
        jwt_public_key="dummy",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_ALLOWED_HOSTS" in str(exc.value)


def test_prod_guard_accepts_explicit_origins_and_hosts():
    settings = Settings(
        env="prod",
        cors_origins="https://app.example.com,https://admin.example.com",
        allowed_hosts="app.example.com,admin.example.com",
        razorpay_webhook_secret="not-a-real-secret-for-tests-123",
        jwt_private_key="dummy",
        jwt_public_key="dummy",
    )
    _validate_prod_settings(settings)
