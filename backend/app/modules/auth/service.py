"""AuthService — orchestrates models + pure security/refresh logic over a DB
session. This is the only place that touches auth tables."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import Base, bind_workspace_context
from app.modules.auth import mfa
from app.modules.auth import refresh as rf
from app.modules.auth import security as sec
from app.modules.auth.models import (
    EmailVerification,
    Invitation,
    MobileVerification,
    PasswordReset,
    Project,
    ProjectMember,
    RefreshToken,
    User,
    Workspace,
    WorkspaceMember,
)
from app.modules.auth.rbac import ROLES, role_at_least

logger = logging.getLogger(__name__)

# Fallback seat limits; billing module provides the canonical mapping via registry.
_SEAT_LIMITS = {"free": 2, "paygo": 3, "pro": 10, "scale": 25}


def _as_utc(dt: datetime | None) -> datetime | None:
    """Make a possibly naive DB datetime UTC-aware for comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


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
        settings=None,
        access_ttl_min=15,
        refresh_ttl_days=30,
        sender: Any | None = None,
        seat_limits: dict[str, int] | None = None,
        audit_factory: Any | None = None,
    ):
        self.s = session
        self.keys = keys
        self.settings = settings
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self._sender = sender
        self._seat_limits = seat_limits or _SEAT_LIMITS
        self._audit_factory = audit_factory

    def _audit(
        self, workspace_id, actor_user_id, action, *,
        object_type=None, object_id=None, detail=None,
    ):
        if self._audit_factory is None:
            return
        try:
            svc = self._audit_factory(self.s)
            svc.audit(
                workspace_id,
                actor=str(actor_user_id) if actor_user_id else None,
                action=action,
                object_type=object_type,
                object_id=str(object_id) if object_id else None,
                detail=detail or {},
            )
        except Exception:
            logger.exception("audit log failed for action %r", action)

    # ---- registration -----------------------------------------------------
    def _mobile_verification_enabled(self) -> bool:
        return bool(self.settings and self.settings.auth_mobile_verification_enabled)

    def _login_otp_enabled(self) -> bool:
        return bool(self.settings and self.settings.auth_login_otp_enabled)

    def _email_otp_enabled(self) -> bool:
        return bool(self.settings and self.settings.auth_email_otp_enabled)

    def _sms_otp_enabled(self) -> bool:
        return bool(self.settings and self.settings.auth_sms_otp_enabled)

    def signup(
        self,
        email: str,
        password: str,
        confirm_password: str,
        org_name: str,
        city: str,
        phone: str | None = None,
        dob: date | None = None,
    ) -> dict:
        email = email.strip().lower()
        phone = (phone or "").strip() or None
        if self._mobile_verification_enabled() and not phone:
            raise AuthError("phone_required")
        if password != confirm_password:
            raise AuthError("password_mismatch")
        try:
            sec.validate_password(password)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        if phone and self.s.scalar(select(User).where(User.phone == phone)):
            raise AuthError("phone_taken")
        user = User(
            email=email,
            phone=phone,
            password_hash=sec.hash_password(password),
            org_name=org_name.strip(),
            city=city.strip(),
            dob=dob,
            mobile_verified=not self._mobile_verification_enabled(),
        )
        self.s.add(user)
        self.s.flush()
        email_token = self.create_email_verification(user.id, email=email)
        mobile_token = None
        if self._mobile_verification_enabled() and phone:
            mobile_token = self.create_mobile_verification(user.id, phone=phone)
        self.s.commit()
        result = {
            "user_id": str(user.id),
            "status": "verification_required",
            "email_verified": False,
            "mobile_verified": user.mobile_verified,
        }
        # In production the tokens are sent by email/SMS; in dev/tests they are returned so
        # verification flows can be exercised without a real mailer.
        if not self.settings or not self.settings.is_prod():
            if email_token:
                result["email_verification_token"] = email_token
            if mobile_token:
                result["mobile_verification_token"] = mobile_token
        return result

    def _require_verified_for_login(self, user: User) -> None:
        if not user.email_verified:
            raise AuthError("email_not_verified")
        if self._mobile_verification_enabled() and not user.mobile_verified:
            raise AuthError("mobile_not_verified")

    def _resolve_identifier_type(self, identifier: str, identifier_type: str) -> str:
        if identifier_type in ("email", "mobile"):
            return identifier_type
        return "email" if "@" in identifier else "mobile"

    def _lookup_user_by_identifier(self, identifier: str, identifier_type: str) -> User | None:
        identifier = identifier.strip().lower()
        if identifier_type == "email":
            return self.s.scalar(select(User).where(User.email == identifier))
        return self.s.scalar(select(User).where(User.phone == identifier))

    # ---- login ------------------------------------------------------------
    def login(
        self,
        identifier: str,
        password: str,
        *,
        method: str = "password",
        identifier_type: str = "auto",
    ) -> dict:
        itype = self._resolve_identifier_type(identifier, identifier_type)
        user = self._lookup_user_by_identifier(identifier, itype)

        now = datetime.now(UTC)
        if user and user.locked_until and user.locked_until > now:
            raise AuthError("account_locked")
        if user and user.suspended_at:
            raise AuthError("account_suspended")

        if method not in ("password", "otp"):
            raise AuthError("bad_login_method")

        if method == "password":
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
        else:  # otp
            if not self._login_otp_enabled():
                raise AuthError("otp_disabled")
            if itype == "email" and not self._email_otp_enabled():
                raise AuthError("email_otp_disabled")
            if itype == "mobile" and not self._sms_otp_enabled():
                raise AuthError("sms_otp_disabled")
            if not user:
                raise AuthError("invalid_credentials")

        # success: clear any lockout/failed-attempt counters
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None

        # An account must be verified before it can log in and access workspaces.
        if not user or not user.email_verified:
            raise AuthError("email_not_verified")
        if self._mobile_verification_enabled() and (not user or not user.mobile_verified):
            raise AuthError("mobile_not_verified")

        # If OTP is globally disabled, password login issues tokens directly.
        if method == "password" and not self._login_otp_enabled():
            return self._issue_tokens(
                user.id,
                self._NO_WORKSPACE,
                "owner",
                is_superadmin=user.is_superadmin,
                new_family=True,
            )

        # Per-login OTP challenge (password path) or passwordless OTP login.
        channel = self._mfa_channel(user) if method == "password" else itype
        code = mfa.new_otp_code()
        user.mfa_otp_code = code
        user.mfa_otp_expires_at = now + timedelta(seconds=mfa.CODE_TTL_SECONDS)
        self.s.commit()
        self._mfa_send_code(user, code, "login code", channel=channel)
        result = {
            "mfa_required": True,
            "mfa_token": sec.mint_mfa_token(
                self.keys,
                user_id=str(user.id),
                workspace_id=self._NO_WORKSPACE,
                role="owner",
                is_superadmin=user.is_superadmin,
                email_verified=user.email_verified,
                mobile_verified=user.mobile_verified,
                ttl=timedelta(minutes=5),
            ),
        }
        # In production the code is sent by email/SMS; in dev/tests it is returned so
        # the login flow can be exercised without a real sender.
        if not self.settings or not self.settings.is_prod():
            result["mfa_code"] = code
        return result

    def _mfa_channel(self, user: User) -> str:
        return user.mfa_method or "email"

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
        # Preserve the workspace from the refresh-token row; fall back to account-level.
        workspace_id = row.workspace_id
        role = "owner"
        if workspace_id:
            member = self.s.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == row.user_id,
                )
            )
            if member:
                role = member.role
            else:
                # Membership was removed; drop to account-level.
                workspace_id = None
        tokens = self._issue_tokens(
            row.user_id,
            workspace_id,
            role,
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

    # ---- internals --------------------------------------------------------
    _NO_WORKSPACE = "00000000-0000-0000-0000-000000000000"

    def _issue_tokens(
        self,
        user_id,
        workspace_id,
        role,
        *,
        is_superadmin=False,
        email_verified: bool | None = None,
        mobile_verified: bool | None = None,
        new_family=False,
        family_id=None,
    ) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if email_verified is None:
            email_verified = user.email_verified if user else False
        if mobile_verified is None:
            mobile_verified = user.mobile_verified if user else False
        # Normalize sentinel/no workspace to None for the DB row; keep the sentinel in the token.
        no_ws = str(workspace_id) == self._NO_WORKSPACE
        ws_uuid = uuid.UUID(str(workspace_id)) if workspace_id and not no_ws else None
        access = sec.mint_access(
            self.keys,
            user_id=str(user_id),
            workspace_id=str(ws_uuid) if ws_uuid else self._NO_WORKSPACE,
            role=role,
            is_superadmin=is_superadmin,
            email_verified=email_verified,
            mobile_verified=mobile_verified,
            ttl=self.access_ttl,
        )
        raw, token_hash = rf.new_refresh()
        fam = uuid.uuid4() if new_family else family_id
        self.s.add(
            RefreshToken(
                user_id=user_id,
                workspace_id=ws_uuid,
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
            "workspace_id": str(ws_uuid) if ws_uuid else self._NO_WORKSPACE,
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
        self._audit(
            workspace.id, user_id, "workspace.created",
            object_type="workspace", object_id=workspace.id,
            detail={"name": workspace.name, "country": workspace.country},
        )
        return {"workspace_id": str(workspace.id), "name": workspace.name}

    def list_workspaces(self, user_id) -> list[dict]:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        plan = user.plan if user else "free"
        rows = self.s.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == uuid.UUID(str(user_id)))
        ).all()
        return [
            {
                "workspace_id": str(ws.id),
                "name": ws.name,
                "role": m.role,
                "country": ws.country,
                "plan": plan,
            }
            for ws, m in rows
        ]

    def _workspace_member(self, workspace_id, user_id):
        return self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceMember.user_id == uuid.UUID(str(user_id)),
            )
        )

    def _seat_limit(self, workspace_id) -> int | None:
        workspace = self.s.get(Workspace, uuid.UUID(str(workspace_id)))
        if not workspace:
            raise AuthError("no_such_workspace")
        owner = self.s.get(User, workspace.owner_id)
        return self._seat_limits.get(owner.plan if owner else "free")

    def _member_count(self, workspace_id) -> int:
        return self.s.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))
        ) or 0

    def _pending_invitation_count(self, workspace_id) -> int:
        return self.s.scalar(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.workspace_id == uuid.UUID(str(workspace_id)),
                Invitation.used_at.is_(None),
                Invitation.expires_at > datetime.now(UTC),
            )
        ) or 0

    def _assert_seats_available(self, workspace_id, count: int = 1) -> None:
        limit = self._seat_limit(workspace_id)
        if limit is None:
            return
        used = self._member_count(workspace_id) + self._pending_invitation_count(workspace_id)
        if used + count > limit:
            raise AuthError("seat_limit_exceeded")

    def add_workspace_member(self, workspace_id, email: str, role: str, actor_user_id=None) -> dict:
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
            old_role = existing.role
            existing.role = role
        else:
            self._assert_seats_available(workspace_id)
            old_role = None
            self.s.add(WorkspaceMember(workspace_id=workspace_id, user_id=user.id, role=role))
        self.s.commit()
        self._audit(
            workspace_id, actor_user_id, "workspace.member_added",
            object_type="workspace", object_id=workspace_id,
            detail={"target_user_id": str(user.id), "role": role, "old_role": old_role},
        )
        return {"workspace_id": str(workspace_id), "user_id": str(user.id), "role": role}

    def list_workspace_members(self, workspace_id, user_id) -> list[dict]:
        workspace_uuid = uuid.UUID(str(workspace_id))
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user or not (user.is_superadmin or self._workspace_member(workspace_uuid, user_id)):
            raise AuthError("not_workspace_member")
        rows = self.s.execute(
            select(WorkspaceMember, User)
            .join(User, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == workspace_uuid)
        ).all()
        return [
            {"user_id": str(user.id), "email": user.email, "role": member.role}
            for member, user in rows
        ]

    def _assert_can_manage_member(
        self,
        workspace_id,
        actor_user_id,
        target_user_id,
        target_role: str | None = None,
    ) -> User:
        workspace_uuid = uuid.UUID(str(workspace_id))
        actor = self.s.get(User, uuid.UUID(str(actor_user_id)))
        if not actor or not (
            actor.is_superadmin or self._workspace_member(workspace_uuid, actor_user_id)
        ):
            raise AuthError("not_workspace_member")
        actor_member = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_uuid,
                WorkspaceMember.user_id == actor.id,
            )
        )
        actor_role = (
            actor_member.role
            if actor_member
            else ("owner" if actor.is_superadmin else "viewer")
        )
        if actor.is_superadmin:
            return actor
        if not role_at_least(actor_role, "admin"):
            raise AuthError("insufficient_role")
        if target_role is not None and not role_at_least(actor_role, target_role):
            raise AuthError("insufficient_role")
        if str(actor_user_id) == str(target_user_id):
            raise AuthError("cannot_manage_self")
        return actor

    def change_workspace_member_role(
        self, workspace_id, member_user_id, new_role: str, actor_user_id
    ) -> dict:
        if new_role not in ROLES:
            raise AuthError("bad_role")
        self._assert_can_manage_member(workspace_id, actor_user_id, member_user_id, new_role)
        workspace_uuid = uuid.UUID(str(workspace_id))
        member = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_uuid,
                WorkspaceMember.user_id == uuid.UUID(str(member_user_id)),
            )
        )
        if not member:
            raise AuthError("no_such_user")
        old_role = member.role
        member.role = new_role
        self.s.commit()
        self._audit(
            workspace_id,
            actor_user_id,
            "workspace.member_role_changed",
            object_type="workspace",
            object_id=workspace_id,
            detail={
                "target_user_id": str(member_user_id),
                "old_role": old_role,
                "new_role": new_role,
            },
        )
        return {"user_id": str(member.user_id), "role": new_role}

    def remove_workspace_member(self, workspace_id, member_user_id, actor_user_id) -> dict:
        self._assert_can_manage_member(workspace_id, actor_user_id, member_user_id)
        workspace_uuid = uuid.UUID(str(workspace_id))
        member = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_uuid,
                WorkspaceMember.user_id == uuid.UUID(str(member_user_id)),
            )
        )
        if not member:
            raise AuthError("no_such_user")
        self.s.delete(member)
        self.s.commit()
        self._audit(
            workspace_id, actor_user_id, "workspace.member_removed",
            object_type="workspace", object_id=workspace_id,
            detail={"target_user_id": str(member_user_id)},
        )
        return {"ok": True}

    def list_invitations(self, workspace_id, actor_user_id) -> list[dict]:
        workspace_uuid = uuid.UUID(str(workspace_id))
        actor = self.s.get(User, uuid.UUID(str(actor_user_id)))
        if not actor or not (
            actor.is_superadmin or self._workspace_member(workspace_uuid, actor_user_id)
        ):
            raise AuthError("not_workspace_member")
        rows = self.s.scalars(
            select(Invitation).where(
                Invitation.workspace_id == workspace_uuid,
                Invitation.used_at.is_(None),
                Invitation.expires_at > datetime.now(UTC),
            )
        ).all()
        return [
            {
                "invitation_id": str(row.id),
                "email": row.email,
                "role": row.role,
                "project_id": str(row.project_id) if row.project_id else None,
                "expires_at": row.expires_at.isoformat(),
            }
            for row in rows
        ]

    def revoke_invitation(self, invitation_id, actor_user_id) -> dict:
        invitation = self.s.get(Invitation, uuid.UUID(str(invitation_id)))
        if not invitation:
            raise AuthError("invalid_invitation")
        actor = self.s.get(User, uuid.UUID(str(actor_user_id)))
        if not actor or not (
            actor.is_superadmin or self._workspace_member(invitation.workspace_id, actor_user_id)
        ):
            raise AuthError("not_workspace_member")
        actor_member = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == invitation.workspace_id,
                WorkspaceMember.user_id == actor.id,
            )
        )
        actor_role = (
            actor_member.role
            if actor_member
            else ("owner" if actor.is_superadmin else "viewer")
        )
        if not actor.is_superadmin and not role_at_least(actor_role, "admin"):
            raise AuthError("insufficient_role")
        self.s.delete(invitation)
        self.s.commit()
        self._audit(
            invitation.workspace_id, actor_user_id, "workspace.invitation_revoked",
            object_type="invitation", object_id=invitation.id,
            detail={"email": invitation.email},
        )
        return {"ok": True}

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
        self._audit(
            workspace_id, user_id, "project.created",
            object_type="project", object_id=project.id,
            detail={"name": project.name, "status": project.status},
        )
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

    def add_project_member(
        self, workspace_id, project_id, email: str, role: str, actor_user_id=None
    ) -> dict:
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
        self._audit(
            workspace_id, actor_user_id, "project.member_added",
            object_type="project", object_id=project_id,
            detail={"target_user_id": str(user.id), "role": role},
        )
        return {"project_id": str(project_id), "user_id": str(user.id), "role": role}

    def list_project_members(self, project_id, user_id) -> list[dict]:
        project_uuid = uuid.UUID(str(project_id))
        project = self.s.get(Project, project_uuid)
        if not project:
            raise AuthError("no_such_project")
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user or not (
            user.is_superadmin or self._workspace_member(project.workspace_id, user_id)
        ):
            raise AuthError("not_workspace_member")
        rows = self.s.execute(
            select(ProjectMember, User)
            .join(User, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_uuid)
        ).all()
        return [
            {"user_id": str(user.id), "email": user.email, "role": member.role}
            for member, user in rows
        ]

    def create_invitation(
        self,
        workspace_id,
        email: str,
        role: str,
        project_id: str | None = None,
        actor_user_id=None,
    ) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        workspace_id = uuid.UUID(str(workspace_id))
        project_uuid = uuid.UUID(str(project_id)) if project_id else None
        if project_uuid:
            project = self.s.get(Project, project_uuid)
            if not project or project.workspace_id != workspace_id:
                raise AuthError("no_such_project")
        self._assert_seats_available(workspace_id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(days=7)
        invitation = Invitation(
            workspace_id=workspace_id,
            project_id=project_uuid,
            email=email.strip().lower(),
            role=role,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.s.add(invitation)
        self.s.commit()
        self._audit(
            workspace_id,
            actor_user_id,
            "workspace.invitation_created",
            object_type="invitation",
            object_id=invitation.id,
            detail={
                "email": invitation.email,
                "role": role,
                "project_id": str(project_uuid) if project_uuid else None,
            },
        )
        if self._sender and self._sender.__class__.__name__ != "ConsoleSender":
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=invitation.email,
                    subject="You have been invited to a TenderShield workspace",
                    body=(
                        f"You have been invited as {role}. Use this invitation token:\n\n"
                        f"{token}\n\nIt expires in 7 days."
                    ),
                )
            )
            return {"ok": True, "expires_at": expires_at.isoformat()}
        # In production invitations must be delivered by email/SMS.
        if self.settings and self.settings.is_prod():
            raise AuthError("email_not_configured")
        # dev/test fallback: return the token so UI tests can proceed without email.
        # Prefix with workspace_id so the accept endpoint can bind RLS before lookup.
        return {"token": f"{workspace_id}:{token}", "expires_at": expires_at.isoformat()}

    def accept_invitation(self, user_id, token: str) -> dict:
        user_id = uuid.UUID(str(user_id))
        raw_token = token
        workspace_id = None
        if ":" in token:
            try:
                workspace_id = uuid.UUID(token.split(":", 1)[0])
                raw_token = token.split(":", 1)[1]
            except ValueError as exc:
                raise AuthError("invalid_invitation") from exc
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        # Bind to the invitation's workspace so RLS allows the lookup and member writes.
        # For legacy tokens we rely on the caller's already-selected workspace context.
        invitation = self.s.scalar(select(Invitation).where(Invitation.token_hash == token_hash))
        if not invitation:
            raise AuthError("invalid_invitation")
        if workspace_id and workspace_id != invitation.workspace_id:
            raise AuthError("invalid_invitation")
        workspace_id = invitation.workspace_id
        bind_workspace_context(self.s, workspace_id, str(user_id))
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
        if invitation.project_id:
            project = self.s.get(Project, invitation.project_id)
            if not project or project.workspace_id != invitation.workspace_id:
                raise AuthError("no_such_project")
        existing = self.s.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == invitation.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if not existing:
            self._assert_seats_available(invitation.workspace_id, count=0)
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
        self._audit(
            invitation.workspace_id,
            user_id,
            "workspace.invitation_accepted",
            object_type="invitation",
            object_id=invitation.id,
            detail={
                "email": invitation.email,
                "role": invitation.role,
                "workspace_id": str(invitation.workspace_id),
            },
        )
        return {"workspace_id": str(invitation.workspace_id), "role": invitation.role}

    # ---- MFA ---------------------------------------------------------------
    def _mfa_send_code(
        self, user: User, code: str, purpose: str = "MFA code", channel: str | None = None
    ) -> None:
        """Send an email or SMS one-time code if a sender is configured."""
        if not self._sender:
            return
        channel = channel or user.mfa_method or "email"
        if channel == "email":
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=user.email,
                    subject=purpose,
                    body=f"Your TenderShield {purpose} is {code}. It expires in 5 minutes.",
                )
            )
        elif channel == "sms" and (user.mfa_phone or user.phone):
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
        expires_at = _as_utc(user.mfa_otp_expires_at)
        return bool(
            user.mfa_otp_code
            and user.mfa_otp_code == code
            and expires_at
            and expires_at > now
        )

    def mfa_enroll(self, user_id, method: str, phone: str | None = None) -> dict:
        if method not in ("totp", "email", "sms"):
            raise AuthError("bad_mfa_method")
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.mfa_phone = phone
        user.mfa_otp_code = None
        user.mfa_otp_expires_at = None
        if method == "totp":
            # Store the secret in a pending state; mfa_verify confirms enrollment.
            user.mfa_totp_pending_secret = mfa.new_secret()
            self.s.commit()
            return {
                "method": method,
                "secret": user.mfa_totp_pending_secret,
                "otpauth_uri": mfa.provisioning_uri(user.mfa_totp_pending_secret, user.email),
            }
        # email/sms: send a one-time code to verify enrolment
        user.mfa_method = method
        user.mfa_totp_secret = None
        user.mfa_totp_pending_secret = None
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
        # Complete a pending TOTP enrollment on first successful verification.
        if user.mfa_totp_pending_secret:
            if not mfa.verify(user.mfa_totp_pending_secret, code):
                raise AuthError("mfa_invalid")
            user.mfa_method = "totp"
            user.mfa_totp_secret = user.mfa_totp_pending_secret
            user.mfa_totp_pending_secret = None
            self.s.commit()
            return True
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
        email_verified = claims.get("email_verified", False)
        mobile_verified = claims.get("mobile_verified", False)
        user = self.s.get(User, user_id)
        if not user:
            raise AuthError("no_such_user")
        # Login flow stores a per-login OTP on the user row. If present, prefer it.
        expires_at = _as_utc(user.mfa_otp_expires_at)
        if user.mfa_otp_code and expires_at and expires_at > datetime.now(UTC):
            if not self._mfa_code_valid(user, code):
                raise AuthError("mfa_invalid")
            user.mfa_otp_code = None
            user.mfa_otp_expires_at = None
            self.s.commit()
        elif user.mfa_method == "totp":
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
            email_verified=email_verified,
            mobile_verified=mobile_verified,
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
        tokens = self._issue_tokens(
            user.id,
            workspace_uuid,
            member.role if member else "owner",
            is_superadmin=user.is_superadmin,
            family_id=row.family_id,
        )
        self.s.commit()
        return tokens

    # ---- email verification ------------------------------------------------

    def create_email_verification(self, user_id, email: str | None = None) -> str | None:
        """Create an email-verification token and send it. Returns the raw token for dev/tests."""
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        if user.email_verified:
            return None
        target_email = (email or user.email).strip().lower()
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=24)
        self.s.add(
            EmailVerification(
                user_id=user.id, token_hash=token_hash, expires_at=expires_at, used_at=None
            )
        )
        self.s.commit()
        if self._sender:
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=target_email,
                    subject="Verify your TenderShield email",
                    body=(
                        "Welcome to TenderShield. "
                        "Please verify your email by posting this token:\n\n"
                        f"{raw}\n\nIt expires in 24 hours."
                    ),
                )
            )
        return raw

    def verify_email(self, token: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = self.s.scalar(
            select(EmailVerification).where(EmailVerification.token_hash == token_hash)
        )
        if not row or row.used_at:
            raise AuthError("invalid_verification_token")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AuthError("invalid_verification_token")
        user = self.s.get(User, row.user_id)
        if not user:
            raise AuthError("no_such_user")
        user.email_verified = True
        row.used_at = datetime.now(UTC)
        self.s.commit()
        return True

    def request_email_change(self, user_id, new_email: str) -> str | None:
        """Request a change to a new email. Returns a raw token for dev/tests."""
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        new_email = new_email.strip().lower()
        if new_email == user.email:
            raise AuthError("same_email")
        if self.s.scalar(select(User).where(User.email == new_email)):
            raise AuthError("email_taken")
        if self.s.scalar(select(User).where(User.pending_email == new_email)):
            raise AuthError("email_taken")
        raw = secrets.token_urlsafe(32)
        user.pending_email = new_email
        user.pending_email_token_hash = hashlib.sha256(raw.encode()).hexdigest()
        self.s.commit()
        if self._sender:
            self._sender.send(
                SimpleNamespace(
                    channel="email",
                    to=new_email,
                    subject="Confirm your TenderShield email change",
                    body=(
                        "Confirm your new TenderShield email by posting this token:\n\n"
                        f"{raw}\n\nIt expires in 24 hours."
                    ),
                )
            )
        return raw

    def verify_email_change(self, token: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        user = self.s.scalar(
            select(User).where(User.pending_email_token_hash == token_hash)
        )
        if not user or not user.pending_email:
            raise AuthError("invalid_verification_token")
        if self.s.scalar(select(User).where(User.email == user.pending_email)):
            raise AuthError("email_taken")
        user.email = user.pending_email
        user.email_verified = True
        user.pending_email = None
        user.pending_email_token_hash = None
        self.s.commit()
        return True

    def create_mobile_verification(self, user_id, phone: str | None = None) -> str | None:
        """Create a mobile-verification token and send it. Returns the raw token for dev/tests."""
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        if user.mobile_verified:
            return None
        target_phone = (phone or user.phone or "").strip()
        if not target_phone:
            return None
        raw = mfa.new_otp_code()
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        self.s.add(
            MobileVerification(
                user_id=user.id, token_hash=token_hash, expires_at=expires_at, used_at=None
            )
        )
        self.s.commit()
        if self._sender:
            self._sender.send(
                SimpleNamespace(
                    channel="sms",
                    to=target_phone,
                    subject="Verify your TenderShield mobile number",
                    body=(
                        f"Your TenderShield mobile verification code is {raw}. "
                        "It expires in 10 minutes."
                    ),
                )
            )
        return raw

    def verify_mobile(self, token: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = self.s.scalar(
            select(MobileVerification).where(MobileVerification.token_hash == token_hash)
        )
        if not row or row.used_at:
            raise AuthError("invalid_verification_token")
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AuthError("invalid_verification_token")
        user = self.s.get(User, row.user_id)
        if not user:
            raise AuthError("no_such_user")
        user.mobile_verified = True
        row.used_at = datetime.now(UTC)
        self.s.commit()
        return True

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
        # In production we must not expose password-reset tokens in API responses.
        if self.settings and self.settings.is_prod():
            raise AuthError("email_not_configured")
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
                "plan": (
                    self.s.get(User, w.owner_id).plan
                    if self.s.get(User, w.owner_id)
                    else "free"
                ),
                "country": w.country,
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
        return {
            "user_id": str(user.id),
            "email": user.email,
            "is_superadmin": user.is_superadmin,
            "email_verified": user.email_verified,
            "mobile_verified": user.mobile_verified,
        }

    # ---- super-admin user/workspace management -----------------------------

    def search_users(self, query: str | None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        stmt = select(User)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(
                    User.email.ilike(like),
                    User.phone.ilike(like),
                    User.org_name.ilike(like),
                )
            )
        total = self.s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        users = list(
            self.s.scalars(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))
        )
        return {"total": total, "items": [self._user_detail(u) for u in users]}

    def get_user(self, user_id) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        return self._user_detail(user)

    def suspend_user(self, user_id, admin_user_id) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.suspended_at = datetime.now(UTC)
        user.suspended_by = uuid.UUID(str(admin_user_id))
        # revoke all refresh tokens for this user
        for row in self.s.scalars(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        ):
            row.revoked = True
        self.s.commit()
        return self._user_summary(user)

    def unsuspend_user(self, user_id) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.suspended_at = None
        user.suspended_by = None
        self.s.commit()
        return self._user_summary(user)

    def admin_delete_user(self, user_id) -> None:
        """Super-admin deletion of a user account."""
        uid = uuid.UUID(str(user_id))
        user = self.s.get(User, uid)
        if not user:
            raise AuthError("no_such_user")
        # reuse the workspace-scoped erasure logic from delete_account
        self._erase_user(user)

    def get_workspace_detail(self, workspace_id) -> dict:
        ws = self.s.get(Workspace, uuid.UUID(str(workspace_id)))
        if not ws:
            raise AuthError("no_such_workspace")
        owner = self.s.get(User, ws.owner_id)
        members = [
            {"user_id": str(m.user_id), "role": m.role}
            for m in self.s.scalars(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
            )
        ]
        return {
            "workspace_id": str(ws.id),
            "name": ws.name,
            "slug": ws.slug,
            "owner_id": str(ws.owner_id),
            "owner_email": owner.email if owner else None,
            "plan": owner.plan if owner else "free",
            "country": ws.country,
            "billing_provider": owner.billing_provider if owner else None,
            "member_count": len(members),
            "members": members,
        }

    def set_workspace_plan(self, workspace_id, plan: str, admin_user_id) -> dict:
        ws = self.s.get(Workspace, uuid.UUID(str(workspace_id)))
        if not ws:
            raise AuthError("no_such_workspace")
        owner = self.s.get(User, ws.owner_id)
        if not owner:
            raise AuthError("no_workspace_owner")
        old = owner.plan
        owner.plan = plan
        self.s.commit()
        self._audit(
            workspace_id=ws.id,
            actor_user_id=admin_user_id,
            action="admin.workspace_plan_changed",
            object_type="workspace",
            object_id=ws.id,
            detail={"old_plan": old, "new_plan": plan, "owner_id": str(owner.id)},
        )
        return self.get_workspace_detail(workspace_id)

    def admin_dashboard(self) -> dict:
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        total_users = self.s.scalar(select(func.count(User.id)))
        suspended_users = self.s.scalar(
            select(func.count(User.id)).where(User.suspended_at.isnot(None))
        )
        active_workspaces = self.s.scalar(select(func.count(Workspace.id)))
        pending_verifications = self.s.scalar(
            select(func.count(User.id)).where(
                or_(User.email_verified.is_(False), User.mobile_verified.is_(False))
            )
        )
        recent_signups = self.s.scalar(
            select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
        )
        return {
            "total_users": total_users or 0,
            "suspended_users": suspended_users or 0,
            "active_workspaces": active_workspaces or 0,
            "pending_verifications": pending_verifications or 0,
            "recent_signups": recent_signups or 0,
        }

    def _user_summary(self, user: User) -> dict:
        return {
            "user_id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "org_name": user.org_name,
            "city": user.city,
            "email_verified": user.email_verified,
            "mobile_verified": user.mobile_verified,
            "is_superadmin": user.is_superadmin,
            "plan": user.plan,
            "suspended_at": user.suspended_at.isoformat() if user.suspended_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    def _user_detail(self, user: User) -> dict:
        seen: set[uuid.UUID] = set()
        workspaces = []
        for w in self.s.scalars(select(Workspace).where(Workspace.owner_id == user.id)):
            seen.add(w.id)
            workspaces.append(
                {"workspace_id": str(w.id), "name": w.name, "role": "owner", "plan": user.plan}
            )
        for m in self.s.scalars(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
        ):
            if m.workspace_id in seen:
                continue
            ws = self.s.get(Workspace, m.workspace_id)
            if ws:
                seen.add(ws.id)
                owner = self.s.get(User, ws.owner_id)
                workspaces.append(
                    {
                        "workspace_id": str(ws.id),
                        "name": ws.name,
                        "role": m.role,
                        "plan": owner.plan if owner else "free",
                    }
                )
        return {
            **self._user_summary(user),
            "dob": user.dob.isoformat() if user.dob else None,
            "workspaces": workspaces,
        }

    def _revoke_family(self, family_id) -> None:
        for row in self.s.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)):
            row.revoked = True

    # ---- data export / erasure (GDPR/DPDP) ----------------------------------

    def _user_workspaces(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """All workspace IDs this user owns or is a member of."""
        ws_ids: set[uuid.UUID] = set()
        for w in self.s.scalars(select(Workspace).where(Workspace.owner_id == user_id)):
            ws_ids.add(w.id)
        for m in self.s.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)):
            ws_ids.add(m.workspace_id)
        for m in self.s.scalars(select(ProjectMember).where(ProjectMember.user_id == user_id)):
            ws_ids.add(m.workspace_id)
        return ws_ids

    def _export_value(self, value):
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    def export_account_data(self, user_id: str) -> dict:
        """Return a machine-readable account export for GDPR/DPDP portability."""
        uid = uuid.UUID(str(user_id))
        user = self.s.get(User, uid)
        if not user:
            raise AuthError("user_not_found")

        export = {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "org_name": user.org_name,
                "dob": user.dob.isoformat() if user.dob else None,
                "city": user.city,
                "email_verified": user.email_verified,
                "mobile_verified": user.mobile_verified,
                "is_superadmin": user.is_superadmin,
                "created_at": user.created_at.isoformat(),
            },
            "tables": {},
        }

        ws_ids = list(self._user_workspaces(uid))

        for name, table in Base.metadata.tables.items():
            if name == "users":
                continue
            rows: list[dict] = []
            if "workspace_id" in table.columns:
                stmt = select(table).where(table.c.workspace_id.in_(ws_ids))
                for row in self.s.execute(stmt).mappings():
                    rows.append({k: self._export_value(v) for k, v in row.items()})
            if "user_id" in table.columns and name not in (
                "workspace_members",
                "project_members",
            ):
                stmt = select(table).where(table.c.user_id == uid)
                for row in self.s.execute(stmt).mappings():
                    rows.append({k: self._export_value(v) for k, v in row.items()})
            if rows:
                export["tables"][name] = rows

        export["workspaces"] = [str(w) for w in ws_ids]
        return export

    def delete_account(self, user_id: str, password: str) -> None:
        """Erase an account and all workspace-scoped data the user owns or can access.

        Raises `AuthError("invalid_password")` if the password is wrong.
        """
        uid = uuid.UUID(str(user_id))
        user = self.s.get(User, uid)
        if not user:
            raise AuthError("user_not_found")
        if not sec.verify_password(password, user.password_hash):
            raise AuthError("invalid_password")
        self._erase_user(user)

    def _erase_user(self, user: User) -> None:
        """Internal account erasure; used by self-service and super-admin deletion."""
        uid = user.id
        ws_ids = self._user_workspaces(uid)
        if ws_ids:
            # Nullify self-referential foreign keys inside the workspace tables to avoid
            # FK violations (e.g. documents.supersedes references another document).
            for _name, table in Base.metadata.tables.items():
                if "workspace_id" not in table.columns:
                    continue
                self_fks = [
                    fk for fk in table.foreign_key_constraints
                    if fk.referred_table is table
                ]
                for fk in self_fks:
                    for col in fk.columns:
                        self.s.execute(
                            table.update()
                            .where(table.c.workspace_id.in_(list(ws_ids)))
                            .values({col.name: None})
                        )

            # RLS is workspace-scoped; set each workspace context and delete its rows.
            for ws_id in ws_ids:
                bind_workspace_context(self.s, ws_id, uid)
                for _name, table in Base.metadata.tables.items():
                    if "workspace_id" not in table.columns:
                        continue
                    self.s.execute(
                        delete(table).where(table.c.workspace_id == ws_id)
                    )

        # The auth tables have ON DELETE CASCADE to users. Deleting the user row
        # removes workspaces, projects, memberships, refresh tokens, etc.
        self.s.delete(user)
        self.s.commit()
