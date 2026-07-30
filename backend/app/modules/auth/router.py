from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.deps import current_principal, get_session, require
from app.core.ratelimit import RateLimitDep
from app.modules.auth.apple import AppleClient
from app.modules.auth.deps import require_superadmin
from app.modules.auth.google import GoogleClient
from app.modules.auth.models import User
from app.modules.auth.rbac import Principal, principal_requires_verified
from app.modules.auth.service import AuthError, AuthService

router = APIRouter()


def _service(request: Request, session: Session) -> AuthService:
    settings = request.app.state.ctx.settings
    keys = request.app.state.ctx.registry.require("auth.keys")
    apple_client = AppleClient(settings) if settings.apple_services_id else None
    google_client = GoogleClient(settings) if settings.google_client_id else None
    sender = request.app.state.ctx.registry.get("notifications.sender")
    return AuthService(
        session,
        keys,
        settings=settings,
        access_ttl_min=settings.access_ttl_minutes,
        refresh_ttl_days=settings.refresh_ttl_days,
        apple_client=apple_client,
        google_client=google_client,
        sender=sender,
    )


# Public routes share a tight per-IP limit to slow credential stuffing.
_LOGIN_LIMIT = [Depends(RateLimitDep(5, 60))]
_SIGNUP_LIMIT = [Depends(RateLimitDep(5, 60))]
_FORGOT_LIMIT = [Depends(RateLimitDep(5, 60))]
_RESET_LIMIT = [Depends(RateLimitDep(5, 60))]
_REFRESH_LIMIT = [Depends(RateLimitDep(20, 60))]


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_is_secure(),
        samesite=settings.cookie_samesite.lower(),
        max_age=settings.refresh_ttl_days * 86400,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.cookie_name, path="/api/auth")


def _issue_token_response(response: Response, settings: Settings, tokens: dict) -> dict:
    """Return an access-token response and ship the refresh token as httpOnly cookie.

    If the service returned an MFA challenge instead of tokens, pass it through
    without setting any cookies.
    """
    if tokens.get("mfa_required"):
        return {"mfa_required": True, "mfa_token": tokens["mfa_token"]}
    _set_refresh_cookie(response, tokens["refresh_token"], settings)
    return {
        "access_token": tokens["access_token"],
        "role": tokens["role"],
        "workspace_id": tokens["workspace_id"],
        "is_superadmin": tokens["is_superadmin"],
    }


def _call_and_issue(
    request: Request, response: Response, session: Session, fn
) -> dict:
    """Call a service method that returns tokens and package the cookie response."""
    try:
        tokens = fn(_service(request, session))
    except AuthError as exc:
        raise HTTPException(_STATUS.get(exc.code, 400), exc.code) from exc
    return _issue_token_response(response, request.app.state.ctx.settings, tokens)


def _validate_password_field(v: str) -> str:
    from app.modules.auth import security as sec

    sec.validate_password(v)
    return v


class SignupBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    workspace_name: str | None = Field(default="Personal", min_length=1)
    country: str = "IN"

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_field(v)


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_field(v)


class VerifyEmailBody(BaseModel):
    token: str = Field(min_length=8)


class AddMemberBody(BaseModel):
    email: str
    role: str


class CreateWorkspaceBody(BaseModel):
    name: str = Field(min_length=1)
    country: str = "IN"


class CreateProjectBody(BaseModel):
    name: str = Field(min_length=1)
    status: str = "planning"


class CreateInvitationBody(BaseModel):
    email: str
    role: str
    project_id: str | None = None


class MfaEnrollBody(BaseModel):
    method: str = Field(default="totp", pattern="^(totp|email|sms)$")
    phone: str | None = None


class MfaVerifyBody(BaseModel):
    code: str


class MfaChallengeBody(BaseModel):
    mfa_token: str
    code: str


class GoogleLoginBody(BaseModel):
    id_token: str


class CreateSuperadminBody(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_field(v)


class SetSuperadminBody(BaseModel):
    is_superadmin: bool


_STATUS = {
    "email_taken": 409,
    "invalid_credentials": 401,
    "invalid_refresh": 401,
    "reuse_detected": 401,
    "no_workspace": 401,
    "email_not_verified": 403,
    "no_such_user": 400,
    "no_such_project": 400,
    "bad_role": 400,
    "not_workspace_member": 403,
    "apple_not_configured": 503,
    "apple_token_invalid": 401,
    "apple_email_missing": 400,
    "google_not_configured": 503,
    "google_token_invalid": 401,
    "google_email_missing": 400,
    "bad_mfa_method": 400,
    "mfa_not_enrolled": 400,
    "mfa_invalid": 401,
    "invalid_mfa_token": 401,
    "invalid_invitation": 400,
    "invitation_used": 400,
    "invitation_email_mismatch": 400,
    "invalid_reset_token": 400,
    "invalid_verification_token": 400,
    "email_not_configured": 503,
    "account_locked": 429,
    "password_too_short": 400,
    "password_missing_uppercase": 400,
    "password_missing_lowercase": 400,
    "password_missing_digit": 400,
    "password_missing_special": 400,
    "password_too_common": 400,
}


def _handle(fn):
    try:
        return fn()
    except AuthError as exc:
        raise HTTPException(_STATUS.get(exc.code, 400), exc.code) from exc


@router.post("/signup", dependencies=_SIGNUP_LIMIT)
def signup(body: SignupBody, request: Request, session: Session = Depends(get_session)):
    return _handle(
        lambda: _service(request, session).signup(
            body.email, body.password, body.workspace_name, body.country
        )
    )


@router.post("/login", dependencies=_LOGIN_LIMIT)
def login(
    body: LoginBody,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    return _call_and_issue(
        request, response, session, lambda svc: svc.login(body.email, body.password)
    )


@router.post("/google", dependencies=_LOGIN_LIMIT)
def google_login(
    body: GoogleLoginBody,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    return _call_and_issue(
        request, response, session, lambda svc: svc.google_login(body.id_token)
    )


@router.post("/refresh", dependencies=_REFRESH_LIMIT)
def refresh(
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
    body: RefreshBody | None = None,
):
    settings = request.app.state.ctx.settings
    raw = request.cookies.get(settings.cookie_name)
    if not raw and body:
        raw = body.refresh_token
    if not raw:
        raise HTTPException(401, "invalid_refresh")
    return _call_and_issue(request, response, session, lambda svc: svc.refresh(raw))


@router.post("/logout", dependencies=_REFRESH_LIMIT)
def logout(
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
    body: RefreshBody | None = None,
):
    settings = request.app.state.ctx.settings
    raw = request.cookies.get(settings.cookie_name)
    if not raw and body:
        raw = body.refresh_token
    if raw:
        _service(request, session).logout(raw)
    _clear_refresh_cookie(response, settings)
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "role": principal.role,
        "is_superadmin": principal.is_superadmin,
        "email_verified": principal.email_verified,
    }


@router.post("/forgot-password", dependencies=_FORGOT_LIMIT)
def forgot_password(
    body: ForgotPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).forgot_password(body.email))


@router.post("/reset-password", dependencies=_RESET_LIMIT)
def reset_password(
    body: ResetPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(
        lambda: _service(request, session).reset_password(body.token, body.new_password)
    )


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).verify_email(body.token))


@router.post("/resend-verification", dependencies=_LOGIN_LIMIT)
def resend_verification(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    def _do():
        _service(request, session).create_email_verification(principal.user_id)
        return {"status": "ok"}

    return _handle(_do)


# ---- workspaces & projects ---------------------------------------------


@router.post("/workspaces")
def create_workspace(
    body: CreateWorkspaceBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(
        lambda: _service(request, session).create_workspace(
            principal.user_id, body.name, body.country
        )
    )


@router.get("/workspaces")
def list_workspaces(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _service(request, session).list_workspaces(principal.user_id)


@router.post("/workspaces/{workspace_id}/switch")
def switch_workspace(
    workspace_id: str,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    settings = request.app.state.ctx.settings
    raw = request.cookies.get(settings.cookie_name)
    if not raw:
        raise HTTPException(401, "invalid_refresh")
    return _call_and_issue(
        request,
        response,
        session,
        lambda svc: svc.switch_workspace(principal.user_id, workspace_id, raw),
    )


@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    if not principal.is_superadmin and str(principal.workspace_id) != workspace_id:
        raise HTTPException(403, "not_workspace_member")
    return _handle(
        lambda: _service(request, session).add_workspace_member(workspace_id, body.email, body.role)
    )


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _service(request, session).list_workspace_members(workspace_id)


@router.post("/workspaces/{workspace_id}/projects")
def create_project(
    workspace_id: str,
    body: CreateProjectBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    return _handle(
        lambda: _service(request, session).create_project(
            principal.user_id, workspace_id, body.name, body.status
        )
    )


@router.get("/workspaces/{workspace_id}/projects")
def list_projects(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _service(request, session).list_projects(principal.user_id, workspace_id)


@router.post("/projects/{project_id}/members")
def add_project_member(
    project_id: str,
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    # project membership is scoped to the active workspace from the token
    return _handle(
        lambda: _service(request, session).add_project_member(
            principal.workspace_id, project_id, body.email, body.role
        )
    )


@router.get("/projects/{project_id}/members")
def list_project_members(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _service(request, session).list_project_members(project_id)


@router.post("/invitations")
def create_invitation(
    body: CreateInvitationBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).create_invitation(
            principal.workspace_id, body.email, body.role, body.project_id
        )
    )


@router.post("/invitations/{token}/accept")
def accept_invitation(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(lambda: _service(request, session).accept_invitation(principal.user_id, token))


# ---- MFA -----------------------------------------------------------------


def _user(session: Session, principal: Principal) -> User:
    import uuid

    user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
    if not user:
        raise HTTPException(404, "user_not_found")
    return user


@router.post("/mfa/enroll")
def mfa_enroll(
    body: MfaEnrollBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(
        lambda: _service(request, session).mfa_enroll(principal.user_id, body.method, body.phone)
    )


@router.post("/mfa/verify")
def mfa_verify(
    body: MfaVerifyBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(lambda: _service(request, session).mfa_verify(principal.user_id, body.code))


@router.post("/mfa/challenge", dependencies=_LOGIN_LIMIT)
def mfa_challenge(
    body: MfaChallengeBody,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    return _call_and_issue(
        request, response, session, lambda svc: svc.mfa_challenge(body.mfa_token, body.code)
    )


# ---- legacy workspace member route (kept for compatibility) ---------------


@router.post("/members")
def add_member(
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).add_workspace_member(
            principal.workspace_id, body.email, body.role
        )
    )


# ---- Sign in with Apple --------------------------------------------------


class AppleCallbackBody(BaseModel):
    id_token: str | None = None
    code: str | None = None
    user: str | None = None  # Apple sends a JSON string on first sign-in


@router.get("/apple/authorize")
def apple_authorize(request: Request):
    settings = request.app.state.ctx.settings
    url = (
        "https://appleid.apple.com/auth/authorize"
        f"?client_id={settings.apple_services_id}"
        f"&redirect_uri={settings.apple_redirect_uri}"
        "&response_type=code id_token"
        "&scope=name email"
        "&response_mode=form_post"
    )
    return {"url": url}


@router.post("/apple/callback", dependencies=_LOGIN_LIMIT)
def apple_callback(
    body: AppleCallbackBody,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    return _call_and_issue(
        request,
        response,
        session,
        lambda svc: svc.apple_callback(body.id_token, body.code, body.user),
    )


# ---- super-admin (application owner) -------------------------------------


@router.get("/admin/users")
def admin_list_users(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _service(request, session).list_users()


@router.get("/admin/workspaces")
def admin_list_workspaces(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _service(request, session).list_all_workspaces()


@router.post("/admin/users")
def admin_create_superadmin(
    body: CreateSuperadminBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _handle(
        lambda: _service(request, session).create_superadmin(body.email, body.password)
    )


@router.post("/admin/users/{user_id}/superadmin")
def admin_set_superadmin(
    user_id: str,
    body: SetSuperadminBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _handle(
        lambda: _service(request, session).set_superadmin(user_id, body.is_superadmin)
    )
