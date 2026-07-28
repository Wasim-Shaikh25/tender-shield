import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_principal, get_session, require
from app.core.ratelimit import Limit, rate_limit
from app.modules.auth.apple import AppleClient
from app.modules.auth.deps import (
    require_project_member,
    require_superadmin,
    require_workspace_member,
)
from app.modules.auth.models import Project, User
from app.modules.auth.rbac import Principal
from app.modules.auth.service import AuthError, AuthService

router = APIRouter()

# R-002 §C — per-IP fixed-window limits on unauthenticated auth endpoints.
# Argon2id makes /login a CPU-exhaustion vector too: each guess costs the
# server far more than the attacker, so this also caps abuse cost, not just
# guess rate. LOGIN_LIMIT is deliberately looser than the per-account lockout
# threshold (10 failures, AuthService._LOCKOUT_THRESHOLD) — lockout is the
# precise defense against a single-account brute force; this IP limit's job
# is blunting a spray attack across many different accounts from one IP.
LOGIN_LIMIT = Limit(times=20, seconds=300)
SIGNUP_LIMIT = Limit(times=20, seconds=3600)
RESET_REQUEST_LIMIT = Limit(times=3, seconds=3600)
RESET_CONFIRM_LIMIT = Limit(times=10, seconds=3600)
MFA_VERIFY_LIMIT = Limit(times=5, seconds=300)


def _project_workspace(session: Session, project_id: str) -> str:
    """The project's OWN workspace, not the caller's active token workspace.

    require_project_member authorizes membership of the project's real
    workspace, which may differ from principal.workspace_id (the caller can be
    a member of several workspaces but only one is baked into their current
    token). Downstream service calls must use the project's workspace or a
    legitimately-authorized cross-workspace admin gets a spurious
    no_such_project (TS-084).
    """
    project = session.scalar(select(Project).where(Project.id == uuid.UUID(str(project_id))))
    if project is None:
        raise HTTPException(404, "not_found")
    return str(project.workspace_id)


def _service(request: Request, session: Session) -> AuthService:
    settings = request.app.state.ctx.settings
    keys = request.app.state.ctx.registry.require("auth.keys")
    apple_client = AppleClient(settings) if settings.apple_services_id else None
    return AuthService(
        session,
        keys,
        access_ttl_min=settings.access_ttl_minutes,
        refresh_ttl_days=settings.refresh_ttl_days,
        apple_client=apple_client,
        echo_tokens=settings.dev_echo_tokens,
        notifier=request.app.state.ctx.registry.get("notifications.sender"),
        app_url=settings.app_url,
        entitlements=request.app.state.ctx.registry.get("billing.entitlements"),
        record_referral_signup=request.app.state.ctx.registry.get("billing.record_referral_signup"),
        resolve_referral_code=request.app.state.ctx.registry.get("billing.resolve_referral_code"),
    )


class SignupBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    workspace_name: str | None = Field(default="Personal", min_length=1)
    country: str = "IN"
    referral_code: str | None = None


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class ForgotPasswordBody(BaseModel):
    email: str


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


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


class CreateSuperadminBody(BaseModel):
    email: str
    password: str = Field(min_length=8)


class SetSuperadminBody(BaseModel):
    is_superadmin: bool


_STATUS = {
    "email_taken": 409,
    "invalid_credentials": 401,
    "account_locked": 423,
    "invalid_refresh": 401,
    "reuse_detected": 401,
    "no_workspace": 401,
    "no_such_user": 400,
    "no_such_project": 400,
    "bad_role": 400,
    "not_workspace_member": 403,
    "apple_not_configured": 503,
    "apple_token_invalid": 401,
    "apple_email_missing": 400,
    "bad_mfa_method": 400,
    "mfa_not_enrolled": 400,
    "invalid_invitation": 400,
    "invitation_used": 400,
    "invitation_email_mismatch": 400,
    "invalid_reset_token": 400,
    "password_too_short": 400,
    "last_owner": 400,
    "seat_limit_reached": 402,  # commercial limit, not an authz failure (R-009 §B.4)
}


def _handle(fn):
    try:
        return fn()
    except AuthError as exc:
        status_code = _STATUS.get(exc.code, 400)
        # Commercial-limit errors carry an upsell payload — same
        # {"code", "upsell"} shape as billing's PaywallError, so the
        # frontend's <Paywall/> renders either without caring which module
        # raised it. Every other AuthError keeps the plain string detail
        # existing clients already parse.
        detail = {"code": exc.code, "upsell": exc.upsell} if exc.upsell is not None else exc.code
        raise HTTPException(status_code, detail) from exc


@router.post("/signup", dependencies=[Depends(rate_limit("auth:signup", SIGNUP_LIMIT))])
def signup(body: SignupBody, request: Request, session: Session = Depends(get_session)):
    return _handle(
        lambda: _service(request, session).signup(
            body.email, body.password, body.workspace_name, body.country, body.referral_code
        )
    )


@router.post("/login", dependencies=[Depends(rate_limit("auth:login", LOGIN_LIMIT))])
def login(body: LoginBody, request: Request, session: Session = Depends(get_session)):
    return _handle(lambda: _service(request, session).login(body.email, body.password))


@router.post("/refresh")
def refresh(body: RefreshBody, request: Request, session: Session = Depends(get_session)):
    return _handle(lambda: _service(request, session).refresh(body.refresh_token))


@router.post("/logout")
def logout(body: RefreshBody, request: Request, session: Session = Depends(get_session)):
    _service(request, session).logout(body.refresh_token)
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(current_principal)):
    return {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "role": principal.role,
        "is_superadmin": principal.is_superadmin,
    }


@router.post(
    "/forgot-password",
    dependencies=[Depends(rate_limit("auth:reset-request", RESET_REQUEST_LIMIT))],
)
def forgot_password(
    body: ForgotPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).forgot_password(body.email))


@router.post(
    "/reset-password",
    dependencies=[Depends(rate_limit("auth:reset-confirm", RESET_CONFIRM_LIMIT))],
)
def reset_password(
    body: ResetPasswordBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(lambda: _service(request, session).reset_password(body.token, body.new_password))


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


@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member(
    workspace_id: str,
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_workspace_member("admin")),
):
    return _handle(
        lambda: _service(request, session).add_workspace_member(workspace_id, body.email, body.role)
    )


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_workspace_member("viewer")),
):
    return _service(request, session).list_workspace_members(workspace_id)


@router.post("/workspaces/{workspace_id}/projects")
def create_project(
    workspace_id: str,
    body: CreateProjectBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_workspace_member("admin")),
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
    principal: Principal = Depends(require_workspace_member("viewer")),
):
    return _service(request, session).list_projects(principal.user_id, workspace_id)


@router.post("/projects/{project_id}/members")
def add_project_member(
    project_id: str,
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_project_member("admin")),
):
    workspace_id = _project_workspace(session, project_id)
    return _handle(
        lambda: _service(request, session).add_project_member(
            workspace_id, project_id, body.email, body.role
        )
    )


@router.get("/projects/{project_id}/members")
def list_project_members(
    project_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_project_member("viewer")),
):
    workspace_id = _project_workspace(session, project_id)
    return _service(request, session).list_project_members(workspace_id, project_id)


@router.post("/invitations")
def create_invitation(
    body: CreateInvitationBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
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


@router.post("/mfa/verify", dependencies=[Depends(rate_limit("auth:mfa-verify", MFA_VERIFY_LIMIT))])
def mfa_verify(
    body: MfaVerifyBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    return _handle(lambda: _service(request, session).mfa_verify(principal.user_id, body.code))


# ---- legacy workspace member route (kept for compatibility) ---------------


@router.post("/members")
def add_member(
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
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


@router.post("/apple/callback")
def apple_callback(
    body: AppleCallbackBody,
    request: Request,
    session: Session = Depends(get_session),
):
    return _handle(
        lambda: _service(request, session).apple_callback(body.id_token, body.code, body.user)
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
    return _handle(lambda: _service(request, session).create_superadmin(body.email, body.password))


@router.post("/admin/users/{user_id}/superadmin")
def admin_set_superadmin(
    user_id: str,
    body: SetSuperadminBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require_superadmin),
):
    return _handle(lambda: _service(request, session).set_superadmin(user_id, body.is_superadmin))
