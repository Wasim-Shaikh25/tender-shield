"""Application factory and production startup guard."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.main import _validate_prod_settings


def _rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv_pem, pub_pem


def _prod_settings(**overrides):
    priv, pub = _rsa_keypair()
    defaults = {
        "env": "prod",
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "app.example.com",
        "redis_url": "redis://localhost:6379",
        "email_from": "noreply@example.com",
        "ses_region": "us-east-1",
        "ses_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "ses_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "razorpay_key_id": "rzp_test_xxx",
        "razorpay_webhook_secret": "not-a-real-razorpay-secret-16",
        "jwt_private_key": priv,
        "jwt_public_key": pub,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_prod_guard_rejects_cors_wildcard():
    settings = _prod_settings(
        cors_origins="https://app.example.com,*",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_CORS_ORIGINS" in str(exc.value)


def test_prod_guard_rejects_allowed_hosts_wildcard():
    settings = _prod_settings(
        allowed_hosts="*,app.example.com",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_ALLOWED_HOSTS" in str(exc.value)


def test_prod_guard_accepts_explicit_origins_and_hosts():
    settings = _prod_settings()
    _validate_prod_settings(settings)


def test_prod_guard_requires_redis_url():
    settings = _prod_settings(redis_url="")
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_REDIS_URL" in str(exc.value)


def test_prod_guard_requires_notification_sender():
    settings = _prod_settings(
        email_from="",
        ses_region="",
        ses_access_key_id=None,
        ses_secret_access_key=None,
        msg91_auth_key="",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "notification sender" in str(exc.value)


def test_prod_guard_requires_payment_provider_and_webhook_secret():
    settings = _prod_settings(
        razorpay_key_id="",
        razorpay_webhook_secret=None,
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "payment provider" in str(exc.value)


def test_prod_guard_requires_stripe_webhook_when_stripe_configured():
    settings = _prod_settings(
        stripe_secret_key="sk_test_xxx",
    )
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_STRIPE_WEBHOOK_SECRET" in str(exc.value)


def test_prod_guard_rejects_weak_secrets():
    settings = _prod_settings(razorpay_webhook_secret="secret")
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "TS_RAZORPAY_WEBHOOK_SECRET" in str(exc.value)


def test_prod_guard_rejects_mismatched_jwt_keypair():
    priv_a, _ = _rsa_keypair()
    _, pub_b = _rsa_keypair()
    settings = _prod_settings(jwt_private_key=priv_a, jwt_public_key=pub_b)
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "matching pair" in str(exc.value)


def test_prod_guard_rejects_samesite_none_without_secure():
    settings = _prod_settings(cookie_samesite="none", cookie_secure=False)
    with pytest.raises(RuntimeError) as exc:
        _validate_prod_settings(settings)
    assert "SameSite" in str(exc.value) or "Secure" in str(exc.value)
