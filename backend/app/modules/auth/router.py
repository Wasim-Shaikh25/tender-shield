import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.config import Settings
from app.core.deps import current_principal, get_session, require
from app.core.pagination import PaginationParams, paginated_list_response
from app.core.ratelimit import RateLimitDep
from app.modules.auth.deps import require_superadmin
from app.modules.auth.models import User
from app.modules.auth.rbac import Principal, principal_requires_verified
from app.modules.auth.security import hash_password, validate_password, verify_password
from app.modules.auth.service import AuthError, AuthService

router = APIRouter()


def _service(request: Request, session: Session) -> AuthService:
    settings = request.app.state.ctx.settings
    keys = request.app.state.ctx.registry.require("auth.keys")
    sender = request.app.state.ctx.registry.get("notifications.sender")
    seat_limits = request.app.state.ctx.registry.get("billing.seat_limits")
    audit_factory = request.app.state.ctx.registry.get("review.service_factory")
    return AuthService(
        session,
        keys,
        settings=settings,
        access_ttl_min=settings.access_ttl_minutes,
        refresh_ttl_days=settings.refresh_ttl_days,
        sender=sender,
        seat_limits=seat_limits,
        audit_factory=audit_factory,
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
        result: dict = {"mfa_required": True, "mfa_token": tokens["mfa_token"]}
        if "mfa_code" in tokens:
            result["mfa_code"] = tokens["mfa_code"]
        return result
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
    validate_password(v)
    return v


class SignupBody(BaseModel):
    email: str
    phone: str = Field(min_length=1)
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)
    org_name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    dob: str | None = None

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
        validate_password(v)
        return v


class VerifyEmailBody(BaseModel):
    token: str = Field(min_length=8)


class VerifyMobileBody(BaseModel):
    token: str = Field(min_length=6)


class AccountSettingsBody(BaseModel):
    org_name: str | None = None
    phone: str | None = None
    dob: str | None = None
    city: str | None = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_field(v)


class DeleteAccountBody(BaseModel):
    password: str
    confirm: bool = False


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


class ChangeRoleBody(BaseModel):
    role: str


class MfaEnrollBody(BaseModel):
    method: str = Field(default="totp", pattern="^(totp|email|sms)$")
    phone: str | None = None


class MfaVerifyBody(BaseModel):
    code: str


class MfaChallengeBody(BaseModel):
    mfa_token: str
    code: str


class CreateSuperadminBody(BaseModel):
    email: str
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        return _validate_password_field(v)


class SetSuperadminBody(BaseModel):
    is_superadmin: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    role: str
    workspace_id: str
    is_superadmin: bool = False
    mfa_required: bool | None = None
    mfa_token: str | None = None


class LoginResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str
    mfa_code: str | None = None


class SignupResponse(BaseModel):
    user_id: str
    status: str
    email_verified: bool
    mobile_verified: bool
    email_verification_token: str | None = None
    mobile_verification_token: str | None = None


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    role: str
    country: str | None = None
    plan: str | None = None


class WorkspaceCreateResponse(BaseModel):
    workspace_id: str
    name: str


class MemberResponse(BaseModel):
    user_id: str
    email: str
    role: str


class ChangeRoleResponse(BaseModel):
    user_id: str
    role: str


class InvitationResponse(BaseModel):
    invitation_id: str
    email: str
    role: str
    project_id: str | None = None
    expires_at: str


class InvitationCreateResponse(BaseModel):
    token: str | None = None
    ok: bool | None = None
    expires_at: str


class AcceptInvitationResponse(BaseModel):
    workspace_id: str
    role: str


class AccountSettingsResponse(BaseModel):
    email: str
    phone: str
    org_name: str
    city: str
    dob: str | None = None
    email_verified: bool
    mobile_verified: bool


class MeResponse(BaseModel):
    user_id: str
    workspace_id: str
    role: str
    is_superadmin: bool = False
    email: str
    phone: str
    org_name: str
    city: str
    dob: str | None = None
    email_verified: bool
    mobile_verified: bool


class AdminUserResponse(BaseModel):
    user_id: str
    email: str
    is_superadmin: bool = False
    email_verified: bool
    mobile_verified: bool | None = None


class AdminWorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    owner_id: str
    plan: str | None = None
    country: str | None = None


class OkResponse(BaseModel):
    ok: bool = True


class ForgotPasswordResponse(BaseModel):
    ok: bool = True
    token: str | None = None


_STATUS = {
    "email_taken": 409,
    "phone_taken": 409,
    "password_mismatch": 400,
    "invalid_credentials": 401,
    "invalid_refresh": 401,
    "reuse_detected": 401,
    "no_workspace": 401,
    "seat_limit_exceeded": 402,
    "email_not_verified": 403,
    "mobile_not_verified": 403,
    "no_such_user": 400,
    "no_such_project": 400,
    "bad_role": 400,
    "not_workspace_member": 403,
    "insufficient_role": 403,
    "cannot_manage_self": 400,
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


@router.post("/signup", dependencies=_SIGNUP_LIMIT, response_model=SignupResponse)
def signup(body: SignupBody, request: Request, session: Session = Depends(get_session)):
    return _handle(
        lambda: _service(request, session).signup(
            email=body.email,
            phone=body.phone,
            password=body.password,
            confirm_password=body.confirm_password,
            org_name=body.org_name,
            city=body.city,
            dob=date.fromisoformat(body.dob) if body.dob else None,
        )
    )


@router.post("/login", dependencies=_LOGIN_LIMIT, response_model=LoginResponse)
def login(
    body: LoginBody,
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    return _call_and_issue(
        request, response, session, lambda svc: svc.login(body.email, body.password)
    )


@router.post("/refresh", dependencies=_REFRESH_LIMIT, response_model=TokenResponse)
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


@router.post("/logout", dependencies=_REFRESH_LIMIT, response_model=OkResponse)
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


@router.get("/me", response_model=MeResponse)
def me(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
    if not user:
        raise HTTPException(404, "user_not_found")
    return {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "role": principal.role,
        "is_superadmin": principal.is_superadmin,
        "email_verified": principal.email_verified,
        "mobile_verified": principal.mobile_verified,
        "email": user.email,
        "phone": user.phone,
        "org_name": user.org_name,
        "city": user.city,
        "dob": user.dob.isoformat() if user.dob else None,
    }


@router.post(
    "/forgot-password",
    dependencies=_FORGOT_LIMIT,
    response_model=ForgotPasswordResponse,
    response_model_exclude_none=True,
)
def forgot_password(
    body: ForgotPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).forgot_password(body.email))


@router.post("/reset-password", dependencies=_RESET_LIMIT, response_model=OkResponse)
def reset_password(
    body: ResetPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(
        lambda: _service(request, session).reset_password(body.token, body.new_password)
    )


@router.post("/verify-email", response_model=bool)
def verify_email(
    body: VerifyEmailBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).verify_email(body.token))


@router.post("/verify-mobile", response_model=bool)
def verify_mobile(
    body: VerifyMobileBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).verify_mobile(body.token))


@router.get("/settings", response_model=AccountSettingsResponse)
def get_settings(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
    if not user:
        raise HTTPException(404, "user_not_found")
    return {
        "email": user.email,
        "phone": user.phone,
        "org_name": user.org_name,
        "city": user.city,
        "dob": user.dob.isoformat() if user.dob else None,
        "email_verified": user.email_verified,
        "mobile_verified": user.mobile_verified,
    }


@router.put("/settings", response_model=AccountSettingsResponse)
def update_settings(
    body: AccountSettingsBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    def _do():
        user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
        if not user:
            raise AuthError("no_such_user")
        if body.org_name:
            user.org_name = body.org_name.strip()
        if body.city:
            user.city = body.city.strip()
        if body.dob:
            user.dob = date.fromisoformat(body.dob)
        if body.phone:
            phone = body.phone.strip()
            if phone != user.phone and session.scalar(select(User).where(User.phone == phone)):
                raise AuthError("phone_taken")
            user.phone = phone
            user.mobile_verified = False
            _service(request, session).create_mobile_verification(user.id, phone=user.phone)
        session.commit()
        audit_log.log(
            request,
            session,
            workspace_id=principal.workspace_id,
            actor_user_id=principal.user_id,
            action="account.settings_updated",
            object_type="user",
            object_id=principal.user_id,
            detail={
                "changed": [f for f in ("org_name", "city", "dob", "phone") if getattr(body, f)]
            },
        )

        return {
            "email": user.email,
            "phone": user.phone,
            "org_name": user.org_name,
            "city": user.city,
            "dob": user.dob.isoformat() if user.dob else None,
            "email_verified": user.email_verified,
            "mobile_verified": user.mobile_verified,
        }

    return _handle(_do)


@router.post("/settings/password", response_model=OkResponse)
def change_password(
    body: ChangePasswordBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    def _do():
        svc = _service(request, session)
        user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
        if not user or not user.password_hash or not verify_password(
            body.current_password, user.password_hash
        ):
            raise AuthError("invalid_credentials")
        svc._require_verified_for_login(user)
        validate_password(body.new_password)
        user.password_hash = hash_password(body.new_password)
        session.commit()
        audit_log.log(
            request,
            session,
            workspace_id=principal.workspace_id,
            actor_user_id=principal.user_id,
            action="account.password_changed",
            object_type="user",
            object_id=principal.user_id,
        )
        return {"ok": True}

    return _handle(_do)


@router.post("/export")
def export_account_data(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    """GDPR/DPDP portability export — return every workspace-scoped row the caller
    owns or is a member of, plus user-owned auth rows."""
    return _handle(lambda: _service(request, session).export_account_data(principal.user_id))


@router.delete("/account")
def delete_account(
    body: DeleteAccountBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    """GDPR/DPDP erasure — delete the caller's account and all owned workspace data."""
    if not body.confirm:
        raise HTTPException(400, "confirm_required")

    def _do():
        _service(request, session).delete_account(principal.user_id, body.password)
        session.commit()
        return {"ok": True, "deleted": True}

    return _handle(_do)


# ---- workspaces & projects ---------------------------------------------


@router.post("/workspaces", response_model=WorkspaceCreateResponse)
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


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
    page: PaginationParams = Depends(),
):
    items = _service(request, session).list_workspaces(principal.user_id)
    return paginated_list_response(items, page, response)


@router.post("/workspaces/{workspace_id}/switch", response_model=TokenResponse)
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


@router.post("/workspaces/{workspace_id}/members", response_model=MemberResponse)
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
        lambda: _service(request, session).add_workspace_member(
            workspace_id, body.email, body.role, actor_user_id=principal.user_id
        )
    )


@router.get("/workspaces/{workspace_id}/members", response_model=list[MemberResponse])
def list_workspace_members(
    workspace_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
    page: PaginationParams = Depends(),
):
    def _do():
        items = _service(request, session).list_workspace_members(workspace_id, principal.user_id)
        return paginated_list_response(items, page, response)
    return _handle(_do)


@router.put("/workspaces/{workspace_id}/members/{user_id}", response_model=ChangeRoleResponse)
def change_workspace_member_role(
    workspace_id: str,
    user_id: str,
    body: ChangeRoleBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).change_workspace_member_role(
            workspace_id, user_id, body.role, principal.user_id
        )
    )


@router.delete("/workspaces/{workspace_id}/members/{user_id}", response_model=OkResponse)
def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).remove_workspace_member(
            workspace_id, user_id, principal.user_id
        )
    )


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
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
    page: PaginationParams = Depends(),
):
    items = _service(request, session).list_projects(principal.user_id, workspace_id)
    return paginated_list_response(items, page, response)


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
            principal.workspace_id, project_id, body.email, body.role,
            actor_user_id=principal.user_id,
        )
    )


@router.get("/projects/{project_id}/members")
def list_project_members(
    project_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
    page: PaginationParams = Depends(),
):
    def _do():
        items = _service(request, session).list_project_members(project_id, principal.user_id)
        return paginated_list_response(items, page, response)
    return _handle(_do)


@router.post("/invitations", response_model=InvitationCreateResponse)
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
            principal.workspace_id, body.email, body.role, body.project_id,
            actor_user_id=principal.user_id,
        )
    )


@router.post("/invitations/{token}/accept", response_model=AcceptInvitationResponse)
def accept_invitation(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(lambda: _service(request, session).accept_invitation(principal.user_id, token))


@router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
    page: PaginationParams = Depends(),
):
    def _do():
        items = _service(request, session).list_invitations(
            principal.workspace_id, principal.user_id
        )
        return paginated_list_response(items, page, response)
    return _handle(_do)


@router.delete("/invitations/{invitation_id}", response_model=OkResponse)
def revoke_invitation(
    invitation_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    if not principal_requires_verified(principal):
        raise HTTPException(403, "email_not_verified")
    return _handle(
        lambda: _service(request, session).revoke_invitation(
            invitation_id, principal.user_id
        )
    )


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


@router.post("/mfa/challenge", dependencies=_LOGIN_LIMIT, response_model=TokenResponse)
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


# ---- super-admin (application owner) -------------------------------------


@router.get("/admin/users", response_model=list[AdminUserResponse])
def admin_list_users(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
    page: PaginationParams = Depends(),
):
    items = _service(request, session).list_users()
    return paginated_list_response(items, page, response)


@router.get("/admin/workspaces", response_model=list[AdminWorkspaceResponse])
def admin_list_workspaces(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
    page: PaginationParams = Depends(),
):
    items = _service(request, session).list_all_workspaces()
    return paginated_list_response(items, page, response)


@router.post("/admin/users", response_model=TokenResponse)
def admin_create_superadmin(
    body: CreateSuperadminBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _handle(
        lambda: _service(request, session).create_superadmin(body.email, body.password)
    )


@router.post("/admin/users/{user_id}/superadmin", response_model=AdminUserResponse)
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
