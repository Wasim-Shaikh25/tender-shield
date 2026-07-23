from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_principal, get_session, require
from app.modules.auth import mfa
from app.modules.auth.models import User
from app.modules.auth.rbac import Principal
from app.modules.auth.service import AuthError, AuthService

router = APIRouter()


def _service(request: Request, session: Session) -> AuthService:
    settings = request.app.state.ctx.settings
    keys = request.app.state.ctx.registry.require("auth.keys")
    return AuthService(
        session,
        keys,
        access_ttl_min=settings.access_ttl_minutes,
        refresh_ttl_days=settings.refresh_ttl_days,
    )


class SignupBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    org_name: str = Field(min_length=1)
    country: str = "IN"


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class AddMemberBody(BaseModel):
    email: str
    role: str


_STATUS = {
    "email_taken": 409,
    "invalid_credentials": 401,
    "invalid_refresh": 401,
    "reuse_detected": 401,
    "no_org": 401,
}


def _handle(fn):
    try:
        return fn()
    except AuthError as exc:
        raise HTTPException(_STATUS.get(exc.code, 400), exc.code) from exc


@router.post("/signup")
def signup(body: SignupBody, request: Request, session: Session = Depends(get_session)):
    return _handle(
        lambda: _service(request, session).signup(
            body.email, body.password, body.org_name, body.country
        )
    )


@router.post("/login")
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
    return {"user_id": principal.user_id, "org_id": principal.org_id, "role": principal.role}


class MfaVerifyBody(BaseModel):
    code: str


def _user(session: Session, principal: Principal) -> User:
    import uuid

    user = session.scalar(select(User).where(User.id == uuid.UUID(principal.user_id)))
    if not user:
        raise HTTPException(404, "user_not_found")
    return user


@router.post("/mfa/enroll")
def mfa_enroll(
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    """Generate + store a TOTP secret; return the otpauth URI for the QR code."""
    user = _user(session, principal)
    secret = mfa.new_secret()
    user.mfa_totp_secret = secret
    session.commit()
    return {"secret": secret, "otpauth_uri": mfa.provisioning_uri(secret, user.email)}


@router.post("/mfa/verify")
def mfa_verify(
    body: MfaVerifyBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(current_principal),
):
    user = _user(session, principal)
    ok = mfa.verify(user.mfa_totp_secret or "", body.code)
    if not ok:
        raise HTTPException(400, "invalid_code")
    return {"verified": True}


@router.post("/members")
def add_member(
    body: AddMemberBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Principal = Depends(require("admin")),
):
    return _handle(
        lambda: _service(request, session).add_member(principal.org_id, body.email, body.role)
    )
