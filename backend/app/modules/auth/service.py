"""AuthService — orchestrates models + pure security/refresh logic over a DB
session. This is the only place that touches auth tables."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth import mfa
from app.modules.auth import refresh as rf
from app.modules.auth import security as sec
from app.modules.auth.apple import AppleClient
from app.modules.auth.google import GoogleClient
from app.modules.auth.models import (
    Invitation,
    PasswordReset,
    Project,
    ProjectMember,
    RefreshToken,
    User,
    Workspace,
    WorkspaceMember,
)
from app.modules.auth.rbac import ROLES


class AuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AuthService:
    def __init__(
        self,
        session: Session,
        keys: sec.KeyPair,
        *,
        access_ttl_min=15,
        refresh_ttl_days=30,
        apple_client: AppleClient | None = None,
        google_client: GoogleClient | None = None,
        sender: Any | None = None,
    ):
        self.s = session
        self.keys = keys
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self._apple = apple_client
        self._google = google_client
        self._sender = sender

    # ---- registration -----------------------------------------------------
    def signup(
        self, email: str, password: str, workspace_name: str | None = None, country: str = "IN"
    ) -> dict:
        email = email.strip().lower()
        try:
            sec.validate_password(password)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        user = User(email=email, password_hash=sec.hash_password(password))
        self.s.add(user)
        self.s.flush()
        workspace_name = workspace_name or "Personal"
        workspace = Workspace(owner_id=user.id, name=workspace_name, country=country)
        self.s.add(workspace)
        self.s.flush()
        self.s.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        self.s.commit()
        return {"user_id": str(user.id), "workspace_id": str(workspace.id)}

    def google_login(self, id_token: str) -> dict:
        if not self._google or not self._google.is_configured():
            raise AuthError("google_not_configured")
        try:
            claims = self._google.verify_id_token(id_token)
        except Exception as exc:
            raise AuthError("google_token_invalid") from exc
        google_sub = claims.get("sub")
        email = claims.get("email", "").strip().lower()
        if not google_sub or not email:
            raise AuthError("google_email_missing")
        user = self.s.scalar(select(User).where(User.google_sub == google_sub))
        if not user:
            # First Google sign-in: create user and a personal workspace.
            user = User(
                email=email,
                google_sub=google_sub,
                email_verified=claims.get("email_verified", False),
            )
            self.s.add(user)
            self.s.flush()
            workspace = Workspace(owner_id=user.id, name="Personal", country="IN")
            self.s.add(workspace)
            self.s.flush()
            self.s.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        else:
            user.email_verified = claims.get("email_verified", False)
        self.s.commit()
        return self._issue_tokens(
            user.id,
            self.s.scalar(
                select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
            ),
            "owner",
            is_superadmin=user.is_superadmin,
            new_family=True,
        )

    # ---- login ------------------------------------------------------------
    def login(self, email: str, password: str) -> dict | None:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))

        now = datetime.now(UTC)
        if user and user.locked_until and user.locked_until > now:
            raise AuthError("account_locked")

        if (
            not user
            or not user.password_hash
            or not sec.verify_password(password, user.password_hash)
        ):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    user.failed_login_attempts = 0
                self.s.commit()
            raise AuthError("invalid_credentials")

        # success: clear any lockout/failed-attempt counters
        user.failed_login_attempts = 0
        user.locked_until = None

        member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
        workspace_id = member.workspace_id if member else None
        role = member.role if member else "owner"

        # If MFA is enrolled, do not issue tokens yet.
        if user.mfa_totp_secret or user.mfa_method in ("email", "sms"):
            if user.mfa_method in ("email", "sms"):
                code = mfa.new_otp_code()
                user.mfa_otp_code = code
                user.mfa_otp_expires_at = datetime.now(UTC) + timedelta(
                    seconds=mfa.CODE_TTL_SECONDS
                )
                self.s.commit()
                self._mfa_send_code(user, code, "login code")
            return {
                "mfa_required": True,
                "mfa_token": sec.mint_mfa_token(
                    self.keys,
                    user_id=str(user.id),
                    workspace_id=str(workspace_id) if workspace_id else self._NO_WORKSPACE,
                    role=role,
                    is_superadmin=user.is_superadmin,
                    ttl=timedelta(minutes=5),
                ),
            }

        if not member:
            if user.is_superadmin:
                return self._issue_tokens(
                    user.id, None, "owner", is_superadmin=True, new_family=True
                )
            raise AuthError("no_workspace")
        return self._issue_tokens(
            user.id,
            member.workspace_id,
            member.role,
            is_superadmin=user.is_superadmin,
            new_family=True,
        )

    # ---- refresh rotation + reuse detection -------------------------------
    def refresh(self, raw_token: str) -> dict:
        row = self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(raw_token))
        )
        verdict = rf.evaluate_refresh(row, datetime.now(UTC))
        if verdict == rf.RefreshVerdict.REUSE:
            # replay of an already-used token → whole family is compromised
            self._revoke_family(row.family_id)
            self.s.commit()
            raise AuthError("reuse_detected")
        if verdict == rf.RefreshVerdict.INVALID:
            raise AuthError("invalid_refresh")
        row.used_at = datetime.now(UTC)
        user = self.s.get(User, row.user_id)
        member = self.s.scalar(
            select(WorkspaceMember).where(WorkspaceMember.user_id == row.user_id)
        )
        if not member:
            if user and user.is_superadmin:
                tokens = self._issue_tokens(
                    row.user_id, None, "owner", is_superadmin=True, family_id=row.family_id
                )
            else:
                raise AuthError("no_workspace")
        else:
            tokens = self._issue_tokens(
                row.user_id,
                member.workspace_id,
                member.role,
                is_superadmin=user.is_superadmin if user else False,
                family_id=row.family_id,
            )
        self.s.commit()
        return tokens

    def logout(self, raw_token: str) -> None:
        row = self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(raw_token))
        )
        if row:
            self._revoke_family(row.family_id)
            self.s.commit()

    # ---- org membership ---------------------------------------------------
    def add_member(self, workspace_id: uuid.UUID | str, email: str, role: str) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        workspace_id = uuid.UUID(
            str(workspace_id)
        )  # principal.workspace_id arrives as a JWT string
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if not user:
            raise AuthError("no_such_user")
        self.s.merge(WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role))
        self.s.commit()
        return {"workspace_id": str(workspace_id), "user_id": str(user.id), "role": role}

    # ---- Sign in with Apple -----------------------------------------------
    def apple_callback(self, id_token: str | None, code: str | None, user_json: str | None) -> dict:
        if not self._apple or not self._apple.is_configured():
            raise AuthError("apple_not_configured")

        if code and not id_token:
            token_resp = self._apple.exchange_code(code)
            id_token = token_resp.get("id_token")
        if not id_token:
            raise AuthError("apple_token_invalid")

        try:
            claims = self._apple.verify_id_token(id_token)
        except Exception as exc:
            raise AuthError("apple_token_invalid") from exc

        sub = claims.get("sub")
        email = (claims.get("email") or "").strip().lower()
        email_verified = claims.get("email_verified") in (True, "true", "1")
        if not sub:
            raise AuthError("apple_token_invalid")

        # First look up by Apple subject; otherwise trust verified email.
        user = self.s.scalar(select(User).where(User.apple_id == sub))
        if not user and email and email_verified:
            user = self.s.scalar(select(User).where(User.email == email))

        if not user:
            if not email:
                raise AuthError("apple_email_missing")
            user = User(email=email, email_verified=True, apple_id=sub)
            workspace_name = self._apple_workspace_name(user_json)
            self.s.add(user)
            self.s.flush()
            workspace = Workspace(owner_id=user.id, name=workspace_name, country="IN")
            self.s.add(workspace)
            self.s.flush()
            self.s.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        else:
            if not user.apple_id:
                user.apple_id = sub
            if email and not user.email:
                user.email = email
            user.email_verified = True

        self.s.commit()
        member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
        if not member:
            if user.is_superadmin:
                return self._issue_tokens(
                    user.id, None, "owner", is_superadmin=True, new_family=True
                )
            raise AuthError("no_workspace")
        return self._issue_tokens(
            user.id,
            member.workspace_id,
            member.role,
            is_superadmin=user.is_superadmin,
            new_family=True,
        )

    def _apple_workspace_name(self, user_json: str | None) -> str:
        if not user_json:
            return "Apple User"
        try:
            data = json.loads(user_json)
            name = data.get("name", {})
            first = name.get("firstName", "")
            last = name.get("lastName", "")
            full = f"{first} {last}".strip()
            return full or "Apple User"
        except json.JSONDecodeError:
            return "Apple User"

    # ---- internals --------------------------------------------------------
    _NO_WORKSPACE = "00000000-0000-0000-0000-000000000000"

    def _issue_tokens(
        self, user_id, workspace_id, role, *, is_superadmin=False, new_family=False, family_id=None
    ) -> dict:
        access = sec.mint_access(
            self.keys,
            user_id=str(user_id),
            workspace_id=str(workspace_id) if workspace_id else self._NO_WORKSPACE,
            role=role,
            is_superadmin=is_superadmin,
            ttl=self.access_ttl,
        )
        raw, token_hash = rf.new_refresh()
        fam = uuid.uuid4() if new_family else family_id
        self.s.add(
            RefreshToken(
                user_id=user_id,
                family_id=fam,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + self.refresh_ttl,
            )
        )
        if new_family:
            self.s.commit()
        return {
            "access_token": access,
            "refresh_token": raw,
            "role": role,
            "workspace_id": str(workspace_id) if workspace_id else self._NO_WORKSPACE,
            "is_superadmin": is_superadmin,
        }

    # ---- workspaces & projects ---------------------------------------------
    def create_workspace(self, user_id, name: str, country: str = "IN") -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        workspace = Workspace(owner_id=user.id, name=name, country=country)
        self.s.add(workspace)
        self.s.flush()
        self.s.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
        self.s.commit()
        return {"workspace_id": str(workspace.id), "name": workspace.name}

    def list_workspaces(self, user_id) -> list[dict]:
        rows = self.s.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == uuid.UUID(str(user_id)))
        ).all()
        return [{"workspace_id": str(ws.id), "name": ws.name, "role": m.role} for ws, m in rows]

    def _workspace_member(self, workspace_id, user_id):
        return self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceMember.user_id == uuid.UUID(str(user_id)),
            )
        )

    def add_workspace_member(self, workspace_id, email: str, role: str) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        workspace_id = uuid.UUID(str(workspace_id))
        user = self.s.scalar(select(User).where(User.email == email.strip().lower()))
        if not user:
            raise AuthError("no_such_user")
        existing = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
        if existing:
            existing.role = role
        else:
            self.s.add(WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role))
        self.s.commit()
        return {"workspace_id": str(workspace_id), "user_id": str(user.id), "role": role}

    def list_workspace_members(self, workspace_id) -> list[dict]:
        rows = self.s.execute(
            select(WorkspaceMember, User)
            .join(User, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))
        ).all()
        return [
            {"user_id": str(user.id), "email": user.email, "role": member.role}
            for member, user in rows
        ]

    def create_project(self, user_id, workspace_id, name: str, status: str = "planning") -> dict:
        workspace_id = uuid.UUID(str(workspace_id))
        if not self._workspace_member(workspace_id, user_id):
            raise AuthError("not_workspace_member")
        project = Project(
            workspace_id=workspace_id, owner_id=uuid.UUID(str(user_id)), name=name, status=status
        )
        self.s.add(project)
        self.s.flush()
        self.s.add(
            ProjectMember(
                workspace_id=workspace_id,
                project_id=project.id,
                user_id=uuid.UUID(str(user_id)),
                role="owner",
            )
        )
        self.s.commit()
        return {"project_id": str(project.id), "name": project.name, "status": project.status}

    def list_projects(self, user_id, workspace_id) -> list[dict]:
        workspace_id = uuid.UUID(str(workspace_id))
        rows = self.s.execute(
            select(Project)
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .where(
                Project.workspace_id == workspace_id,
                ProjectMember.user_id == uuid.UUID(str(user_id)),
            )
        ).all()
        return [{"project_id": str(p.id), "name": p.name, "status": p.status} for (p,) in rows]

    def add_project_member(self, workspace_id, project_id, email: str, role: str) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        workspace_id = uuid.UUID(str(workspace_id))
        project_id = uuid.UUID(str(project_id))
        project = self.s.scalar(select(Project).where(Project.id == project_id))
        if not project or project.workspace_id != workspace_id:
            raise AuthError("no_such_project")
        user = self.s.scalar(select(User).where(User.email == email.strip().lower()))
        if not user:
            raise AuthError("no_such_user")
        existing = self.s.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
        if existing:
            existing.role = role
        else:
            self.s.add(
                ProjectMember(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    user_id=user.id,
                    role=role,
                )
            )
        self.s.commit()
        return {"project_id": str(project_id), "user_id": str(user.id), "role": role}

    def list_project_members(self, project_id) -> list[dict]:
        project_id = uuid.UUID(str(project_id))
        rows = self.s.execute(
            select(ProjectMember, User)
            .join(User, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
        ).all()
        return [
            {"user_id": str(user.id), "email": user.email, "role": member.role}
            for member, user in rows
        ]

    def create_invitation(
        self, workspace_id, email: str, role: str, project_id: str | None = None
    ) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        workspace_id = uuid.UUID(str(workspace_id))
        project_uuid = uuid.UUID(str(project_id)) if project_id else None
        token = uuid.uuid4().hex
        expires_at = datetime.now(UTC) + timedelta(days=7)
        invitation = Invitation(
            workspace_id=workspace_id,
            project_id=project_uuid,
            email=email.strip().lower(),
            role=role,
            token=token,
            expires_at=expires_at,
        )
        self.s.add(invitation)
        self.s.commit()
        # TODO: wire email/SMS delivery; for now the token is returned directly.
        return {"token": token, "expires_at": expires_at.isoformat()}

    def accept_invitation(self, user_id, token: str) -> dict:
        user_id = uuid.UUID(str(user_id))
        invitation = self.s.scalar(select(Invitation).where(Invitation.token == token))
        if not invitation:
            raise AuthError("invalid_invitation")
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AuthError("invalid_invitation")
        if invitation.used_at:
            raise AuthError("invitation_used")
        user = self.s.get(User, user_id)
        if not user or user.email != invitation.email:
            raise AuthError("invitation_email_mismatch")
        existing = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == invitation.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if not existing:
            self.s.add(
                WorkspaceMember(
                    workspace_id=invitation.workspace_id,
                    user_id=user_id,
                    role=invitation.role,
                )
            )
        if invitation.project_id:
            existing_project = self.s.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == invitation.project_id,
                    ProjectMember.user_id == user_id,
                )
            )
            if not existing_project:
                self.s.add(
                    ProjectMember(
                        workspace_id=invitation.workspace_id,
                        project_id=invitation.project_id,
                        user_id=user_id,
                        role=invitation.role,
                    )
                )
        invitation.used_at = datetime.now(UTC)
        self.s.commit()
        return {"workspace_id": str(invitation.workspace_id), "role": invitation.role}

    # ---- MFA ---------------------------------------------------------------
    def _mfa_send_code(self, user: User, code: str, purpose: str = "MFA code") -> None:
        """Send an email or SMS one-time code if a sender is configured."""
        if not self._sender:
            return
        if user.mfa_method == "email":
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=user.email,
                    subject=purpose,
                    body=f"Your TenderShield {purpose} is {code}. It expires in 5 minutes.",
                )
            )
        elif user.mfa_method == "sms" and (user.mfa_phone or user.phone):
            self._sender.send(
                SimpleNamespace(
                    channel="sms",
                    to=user.mfa_phone or user.phone,
                    subject=purpose,
                    body=f"TenderShield {purpose}: {code}",
                )
            )

    def _mfa_code_valid(self, user: User, code: str) -> bool:
        now = datetime.now(UTC)
        return bool(
            user.mfa_otp_code
            and user.mfa_otp_code == code
            and user.mfa_otp_expires_at
            and user.mfa_otp_expires_at > now
        )

    def mfa_enroll(self, user_id, method: str, phone: str | None = None) -> dict:
        if method not in ("totp", "email", "sms"):
            raise AuthError("bad_mfa_method")
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.mfa_method = method
        user.mfa_phone = phone
        user.mfa_otp_code = None
        user.mfa_otp_expires_at = None
        if method == "totp":
            user.mfa_totp_secret = mfa.new_secret()
            self.s.commit()
            return {
                "method": method,
                "secret": user.mfa_totp_secret,
                "otpauth_uri": mfa.provisioning_uri(user.mfa_totp_secret, user.email),
            }
        # email/sms: send a one-time code to verify enrolment
        user.mfa_totp_secret = None
        code = mfa.new_otp_code()
        user.mfa_otp_code = code
        user.mfa_otp_expires_at = datetime.now(UTC) + timedelta(seconds=mfa.CODE_TTL_SECONDS)
        self.s.commit()
        self._mfa_send_code(user, code, "MFA enrolment code")
        return {"method": method, "ok": True}

    def mfa_verify(self, user_id, code: str) -> bool:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        if user.mfa_method == "totp":
            if not user.mfa_totp_secret:
                raise AuthError("mfa_not_enrolled")
            return mfa.verify(user.mfa_totp_secret, code)
        if not user.mfa_otp_code:
            raise AuthError("mfa_not_enrolled")
        if not self._mfa_code_valid(user, code):
            raise AuthError("mfa_invalid")
        user.mfa_otp_code = None
        user.mfa_otp_expires_at = None
        self.s.commit()
        return True

    def mfa_challenge(self, mfa_token: str, code: str) -> dict:
        """Complete MFA login with a short-lived token and a TOTP/SMS/Email code."""
        try:
            claims = sec.decode_mfa_token(mfa_token, self.keys.public_pem)
        except sec.AuthError as exc:
            raise AuthError("invalid_mfa_token") from exc
        user_id = uuid.UUID(claims["sub"])
        if claims["workspace"] != self._NO_WORKSPACE:
            workspace_id = uuid.UUID(claims["workspace"])
        else:
            workspace_id = None
        role = claims["role"]
        is_superadmin = claims.get("is_superadmin", False)
        user = self.s.get(User, user_id)
        if not user:
            raise AuthError("no_such_user")
        if user.mfa_method == "totp":
            if not user.mfa_totp_secret or not mfa.verify(user.mfa_totp_secret, code):
                raise AuthError("mfa_invalid")
        else:
            if not self._mfa_code_valid(user, code):
                raise AuthError("mfa_invalid")
            user.mfa_otp_code = None
            user.mfa_otp_expires_at = None
            self.s.commit()
        return self._issue_tokens(
            user_id,
            workspace_id,
            role,
            is_superadmin=is_superadmin,
            new_family=True,
        )

    def switch_workspace(self, user_id, workspace_id: str | uuid.UUID, raw_token: str) -> dict:
        """Rotate the refresh token and issue an access token for a different workspace."""
        row = self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(raw_token))
        )
        verdict = rf.evaluate_refresh(row, datetime.now(UTC))
        if verdict == rf.RefreshVerdict.REUSE:
            self._revoke_family(row.family_id)
            self.s.commit()
            raise AuthError("reuse_detected")
        if verdict == rf.RefreshVerdict.INVALID:
            raise AuthError("invalid_refresh")

        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")

        workspace_uuid = uuid.UUID(str(workspace_id))
        member = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_uuid,
                WorkspaceMember.user_id == user.id,
            )
        )
        if not member and not user.is_superadmin:
            raise AuthError("not_workspace_member")

        row.used_at = datetime.now(UTC)
        return self._issue_tokens(
            user.id,
            workspace_uuid,
            member.role if member else "owner",
            is_superadmin=user.is_superadmin,
            family_id=row.family_id,
        )

    # ---- password reset ----------------------------------------------------

    def forgot_password(self, email: str) -> dict:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if not user:
            return {"ok": True}
        raw, token_hash = rf.new_refresh()
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        self.s.add(PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        self.s.commit()
        if self._sender and self._sender.__class__.__name__ != "ConsoleSender":
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=user.email,
                    subject="Reset your TenderShield password",
                    body=(
                        f"Use this token to reset your password: {raw}\n\n"
                        "It expires in 15 minutes."
                    ),
                )
            )
            return {"ok": True}
        # dev/test fallback: return the token so UI tests can proceed without email
        return {"ok": True, "token": raw}

    def reset_password(self, token: str, new_password: str) -> dict:
        try:
            sec.validate_password(new_password)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc
        row = self.s.scalar(
            select(PasswordReset).where(PasswordReset.token_hash == rf.hash_token(token))
        )
        if not row:
            raise AuthError("invalid_reset_token")
        if row.used_at:
            raise AuthError("invalid_reset_token")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AuthError("invalid_reset_token")
        user = self.s.get(User, row.user_id)
        if not user:
            raise AuthError("no_such_user")
        user.password_hash = sec.hash_password(new_password)
        row.used_at = datetime.now(UTC)
        self.s.commit()
        return {"ok": True}

    # ---- super-admin -------------------------------------------------------
    def list_users(self) -> list[dict]:
        return [
            {
                "user_id": str(u.id),
                "email": u.email,
                "is_superadmin": u.is_superadmin,
                "email_verified": u.email_verified,
            }
            for u in self.s.scalars(select(User)).all()
        ]

    def list_all_workspaces(self) -> list[dict]:
        return [
            {
                "workspace_id": str(w.id),
                "name": w.name,
                "owner_id": str(w.owner_id),
                "plan": w.plan,
            }
            for w in self.s.scalars(select(Workspace)).all()
        ]

    def create_superadmin(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        try:
            sec.validate_password(password)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        user = User(email=email, password_hash=sec.hash_password(password), is_superadmin=True)
        self.s.add(user)
        self.s.commit()
        return {"user_id": str(user.id), "email": user.email, "is_superadmin": True}

    def set_superadmin(self, user_id, is_superadmin: bool) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.is_superadmin = is_superadmin
        self.s.commit()
        return {"user_id": str(user.id), "is_superadmin": user.is_superadmin}

    def _revoke_family(self, family_id) -> None:
        for row in self.s.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)):
            row.revoked = True
