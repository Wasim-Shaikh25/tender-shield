"""Tests for configurable auth toggles (TS-297)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.modules.auth.models  # noqa: F401 — register auth tables on Base.metadata
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth.models import User
from app.modules.notifications.adapters import BrevoSender, build_sender

TEST_PASSWORD = "Hunter2!Hunter2"


def _client(**settings_overrides):
    application = create_app(
        Settings(
            enabled_modules="health,auth",
            database_url="sqlite:///:memory:",
            **settings_overrides,
        )
    )
    engine = application.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    return TestClient(application)


def _signup(client, email="a@example.com", phone=None):
    payload = {
        "email": email,
        "password": TEST_PASSWORD,
        "confirm_password": TEST_PASSWORD,
        "org_name": "Acme Infra Pvt Ltd",
        "city": "Mumbai",
    }
    if phone is not None:
        payload["phone"] = phone
    r = client.post("/api/auth/signup", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _verify_email(client, signup_resp):
    token = signup_resp.get("email_verification_token")
    assert token
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text


def _verify_mobile(client, signup_resp):
    token = signup_resp.get("mobile_verification_token")
    assert token
    r = client.post("/api/auth/verify-mobile", json={"token": token})
    assert r.status_code == 200, r.text


def test_signup_without_phone_succeeds_when_mobile_disabled():
    client = _client()
    resp = _signup(client, phone=None)
    assert resp["status"] == "verification_required"
    assert "email_verification_token" in resp
    assert "mobile_verification_token" not in resp
    engine = client.app.state.ctx.registry.require("db.engine")
    with Session(engine) as s:
        user = s.scalar(select(User).where(User.email == "a@example.com"))
        assert user is not None
        assert user.phone is None
        assert user.mobile_verified is True


def test_signup_requires_phone_when_mobile_enabled():
    client = _client(auth_mobile_verification_enabled=True)
    r = client.post(
        "/api/auth/signup",
        json={
            "email": "a@example.com",
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD,
            "org_name": "Acme Infra Pvt Ltd",
            "city": "Mumbai",
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "phone_required"


def test_login_four_methods():
    client = _client(auth_sms_otp_enabled=True)
    phone = "+919876543210"
    signup_resp = _signup(client, email="a@example.com", phone=phone)
    _verify_email(client, signup_resp)

    # 1. email + password
    r = client.post(
        "/api/auth/login",
        json={
            "identifier": "a@example.com",
            "identifier_type": "email",
            "method": "password",
            "password": TEST_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["mfa_required"] is True

    # 2. mobile + password
    r = client.post(
        "/api/auth/login",
        json={
            "identifier": phone,
            "identifier_type": "mobile",
            "method": "password",
            "password": TEST_PASSWORD,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["mfa_required"] is True

    # 3. email + OTP
    r = client.post(
        "/api/auth/login",
        json={
            "identifier": "a@example.com",
            "identifier_type": "email",
            "method": "otp",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mfa_required"] is True
    r2 = client.post(
        "/api/auth/mfa/challenge",
        json={"mfa_token": data["mfa_token"], "code": data["mfa_code"]},
    )
    assert r2.status_code == 200, r2.text
    assert "access_token" in r2.json()

    # 4. mobile + OTP (SMS disabled, falls back to email OTP by default)
    r = client.post(
        "/api/auth/login",
        json={
            "identifier": phone,
            "identifier_type": "mobile",
            "method": "otp",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mfa_required"] is True
    r2 = client.post(
        "/api/auth/mfa/challenge",
        json={"mfa_token": data["mfa_token"], "code": data["mfa_code"]},
    )
    assert r2.status_code == 200, r2.text
    assert "access_token" in r2.json()


def test_login_otp_disabled_returns_tokens_immediately():
    client = _client(auth_login_otp_enabled=False)
    signup_resp = _signup(client, email="a@example.com", phone=None)
    _verify_email(client, signup_resp)
    r = client.post(
        "/api/auth/login",
        json={"identifier": "a@example.com", "method": "password", "password": TEST_PASSWORD},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("mfa_required") is None
    assert "access_token" in data

    r2 = client.post(
        "/api/auth/login",
        json={"identifier": "a@example.com", "method": "otp"},
    )
    assert r2.status_code == 403, r2.text
    assert r2.json()["detail"] == "otp_disabled"


def test_brevo_sender_is_selected_when_key_configured():
    settings = Settings(brevo_api_key=SecretStr("test-brevo-key"), email_from="noreply@example.com")
    sender = build_sender(settings)
    assert isinstance(sender, BrevoSender)
