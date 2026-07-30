"""Shared test helpers for the TenderShield backend."""


TEST_PASSWORD = "Hunter2!Hunter2"


def _phone_from_email(email: str) -> str:
    """Derive a deterministic unique mobile number from an email address."""
    return f"+91{abs(hash(email)) % 10000000000:010d}"


def signup(client, email: str, password: str = TEST_PASSWORD, phone: str | None = None):
    """Sign up and verify email + mobile using the dev/test leaked tokens."""
    phone = phone or _phone_from_email(email)
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "phone": phone,
            "password": password,
            "confirm_password": password,
            "org_name": "Acme Infra Pvt Ltd",
            "city": "Mumbai",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "verification_required"
    if "email_verification_token" in data:
        assert client.post(
            "/api/auth/verify-email",
            json={"token": data["email_verification_token"]},
        ).status_code == 200
    if "mobile_verification_token" in data:
        assert client.post(
            "/api/auth/verify-mobile",
            json={"token": data["mobile_verification_token"]},
        ).status_code == 200
    return data


def login(client, email: str, password: str = TEST_PASSWORD) -> dict:
    """Log in and complete the mandatory OTP challenge."""
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    challenge = r.json()
    assert challenge["mfa_required"]
    r = client.post(
        "/api/auth/mfa/challenge",
        json={"mfa_token": challenge["mfa_token"], "code": challenge["mfa_code"]},
    )
    assert r.status_code == 200, r.text
    return r.json()


def ensure_workspace(client, tokens: dict, name: str = "Acme") -> str:
    """Create a workspace and switch the access token into it. Returns the switched tokens."""
    r = client.post(
        "/api/auth/workspaces",
        json={"name": name},
        headers={"authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text
    workspace_id = r.json()["workspace_id"]
    r = client.post(
        f"/api/auth/workspaces/{workspace_id}/switch",
        headers={"authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r.status_code == 200, r.text
    return r.json(), workspace_id


def auth_headers_and_workspace(
    client,
    email: str,
    password: str = TEST_PASSWORD,
    workspace_name: str = "Acme",
):
    """Full account setup: signup → verify → login → OTP → workspace → switch."""
    signup(client, email, password)
    tokens = login(client, email, password)
    tokens, workspace_id = ensure_workspace(client, tokens, workspace_name)
    return {"authorization": f"Bearer {tokens['access_token']}"}, workspace_id


def auth_headers(client, email: str, password: str = TEST_PASSWORD, workspace_name: str = "Acme"):
    """Full account setup returning only the Authorization headers."""
    h, _ = auth_headers_and_workspace(client, email, password, workspace_name)
    return h


def authenticated_user_id(client, headers: dict) -> str:
    """Return the current user's id from /api/auth/me."""
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["user_id"]
