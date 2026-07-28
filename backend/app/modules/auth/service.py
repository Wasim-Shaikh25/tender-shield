"""AuthService — orchestrates models + pure security/refresh logic over a DB
session. This is the only place that touches auth tables."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.db import bind_user_context, bind_workspace_context
from app.modules.auth import mfa
from app.modules.auth import refresh as rf
from app.modules.auth import security as sec
from app.modules.auth.apple import AppleClient
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MailMessage:
    """Minimal shape a notifications.sender capability expects. Defined locally
    (not imported from app.modules.notifications) so auth never imports another
    module — cross-module calls go through the registry only (CLAUDE.md §2)."""

    channel: str
    to: str
    subject: str
    body: str


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
        echo_tokens: bool = False,
        notifier=None,
        app_url: str = "",
    ):
        self.s = session
        self.keys = keys
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self._apple = apple_client
        # DEV/TEST ONLY — see core/config.py Settings.dev_echo_tokens (R-002 §A).
        self._echo_tokens = echo_tokens
        self._notifier = notifier
        self._app_url = app_url.rstrip("/")

    def _notify(self, *, channel: str, to: str, subject: str, body: str) -> None:
        if self._notifier is None:
            logger.warning("no notifications sender available — %r to %s not sent", subject, to)
            return
        self._notifier.send(_MailMessage(channel=channel, to=to, subject=subject, body=body))

    def _create_workspace_and_owner(self, user_id, name: str, country: str) -> Workspace:
        """Insert a new Workspace + its owner WorkspaceMember row.

        A brand-new workspace does not exist yet in current_setting('app.workspace_id'),
        so with RLS FORCE + WITH CHECK enabled (R-001 §B) an INSERT into workspaces
        or workspace_members would otherwise be rejected — there is no workspace to
        bind to until this call generates one. Pre-generating the id client-side
        and binding to it before the insert satisfies WITH CHECK; every other
        workspace-creation path (signup, create_workspace, apple_callback) must go
        through this helper rather than constructing Workspace(...) directly.
        """
        workspace = Workspace(id=uuid.uuid4(), owner_id=user_id, name=name, country=country)
        bind_workspace_context(self.s, workspace.id)
        self.s.add(workspace)
        self.s.flush()
        self.s.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role="owner"))
        return workspace

    # ---- registration -----------------------------------------------------
    def signup(
        self, email: str, password: str, workspace_name: str | None = None, country: str = "IN"
    ) -> dict:
        email = email.strip().lower()
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        user = User(email=email, password_hash=sec.hash_password(password))
        self.s.add(user)
        self.s.flush()
        workspace = self._create_workspace_and_owner(user.id, workspace_name or "Personal", country)
        self.s.commit()
        return {"user_id": str(user.id), "workspace_id": str(workspace.id)}

    # ---- login ------------------------------------------------------------
    _LOCKOUT_THRESHOLD = 10
    _LOCKOUT_MAX_MINUTES = 60

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        now = datetime.now(UTC)
        if user and user.locked_until:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=UTC)
            if locked_until > now:
                raise AuthError("account_locked")
        if (
            not user
            or not user.password_hash
            or not sec.verify_password(password, user.password_hash)
        ):
            if user:
                # Capped, time-boxed backoff (R-002 §C.3) — never permanent,
                # which would hand the attacker a denial-of-service for free.
                user.failed_logins += 1
                if user.failed_logins >= self._LOCKOUT_THRESHOLD:
                    over = user.failed_logins - self._LOCKOUT_THRESHOLD
                    minutes = min(2**over, self._LOCKOUT_MAX_MINUTES)
                    user.locked_until = now + timedelta(minutes=minutes)
                self.s.commit()
            raise AuthError("invalid_credentials")
        if user.failed_logins or user.locked_until:
            user.failed_logins = 0
            user.locked_until = None
            self.s.commit()
        # login is unauthenticated — no prior authenticate() call bound this
        # session to anything, so workspace_members' compound RLS policy
        # (R-001 §B.7) would hide the user's OWN membership row without this:
        # neither app.workspace_id nor app.user_id is set yet at this point,
        # and the row is only visible via the user_id branch of that policy.
        bind_user_context(self.s, user.id)
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
        bind_user_context(self.s, row.user_id)  # unauthenticated entry point — see login()
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
            self._create_workspace_and_owner(user.id, workspace_name, "IN")
        else:
            if not user.apple_id:
                user.apple_id = sub
            if email and not user.email:
                user.email = email
            user.email_verified = True

        self.s.commit()
        # Existing-Apple-user sign-in is, like login()/refresh(), an
        # unauthenticated entry point that may be the first query on this
        # session — bind so the compound workspace_members policy (R-001 §B.7)
        # can find the user's own membership row.
        bind_user_context(self.s, user.id)
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
        workspace = self._create_workspace_and_owner(user.id, name, country)
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
        if existing and existing.role == "owner" and role != "owner":
            # The last owner cannot be demoted — that orphans the workspace
            # (nobody left who can manage billing/members/deletion), R-001 §A.4.
            owners = self.s.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == "owner",
                )
            )
            if owners <= 1:
                raise AuthError("last_owner")
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

    def list_project_members(self, workspace_id, project_id) -> list[dict]:
        workspace_id = uuid.UUID(str(workspace_id))
        project_id = uuid.UUID(str(project_id))
        rows = self.s.execute(
            select(ProjectMember, User)
            .join(User, ProjectMember.user_id == User.id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.workspace_id == workspace_id,  # defensive: R-001 §A.3
            )
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
        invitee_email = email.strip().lower()
        invitation = Invitation(
            workspace_id=workspace_id,
            project_id=project_uuid,
            email=invitee_email,
            role=role,
            token=token,
            expires_at=expires_at,
        )
        self.s.add(invitation)
        self.s.commit()
        workspace = self.s.get(Workspace, workspace_id)
        workspace_name = workspace.name if workspace else "a TenderShield workspace"
        self._notify(
            channel="email",
            to=invitee_email,
            subject=f"You've been invited to {workspace_name}",
            body=f"{self._app_url}/invitations/{token}\n\nThis invitation expires in 7 days.",
        )
        result = {"expires_at": expires_at.isoformat()}
        if self._echo_tokens:
            result["token"] = token
        return result

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
    def mfa_enroll(self, user_id, method: str, phone: str | None = None) -> dict:
        if method not in ("totp", "email", "sms"):
            raise AuthError("bad_mfa_method")
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.mfa_method = method
        user.mfa_phone = phone
        user.mfa_totp_secret = mfa.new_secret()
        self.s.commit()
        result: dict = {"method": method, "secret": user.mfa_totp_secret}
        if method == "totp":
            result["otpauth_uri"] = mfa.provisioning_uri(user.mfa_totp_secret, user.email)
        return result

    def mfa_verify(self, user_id, code: str) -> bool:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user or not user.mfa_totp_secret:
            raise AuthError("mfa_not_enrolled")
        return mfa.verify(user.mfa_totp_secret, code)

    # ---- password reset ----------------------------------------------------

    def forgot_password(self, email: str) -> dict:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if not user:
            # Identical response for known and unknown emails — no enumeration.
            return {"ok": True}
        # Invalidate any outstanding reset so a stale link in an old email
        # cannot be replayed after a newer one is issued (R-002 §A.3).
        self.s.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
            .values(used_at=datetime.now(UTC))
        )
        raw, token_hash = rf.new_refresh()
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        self.s.add(PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
        self.s.commit()
        self._notify(
            channel="email",
            to=user.email,
            subject="Reset your TenderShield password",
            body=(
                f"{self._app_url}/reset-password?token={raw}\n\n"
                "This link expires in 15 minutes. If you didn't ask for this, ignore this email."
            ),
        )
        # Returned only in dev/test — see Settings.dev_echo_tokens (R-002 §A).
        return {"ok": True, "token": raw} if self._echo_tokens else {"ok": True}

    def reset_password(self, token: str, new_password: str) -> dict:
        if len(new_password) < 8:
            raise AuthError("password_too_short")
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
        # A password reset must invalidate every session an attacker (or the
        # victim, on another device) might be holding — otherwise a stolen
        # session survives the exact action meant to kill it (TS-093, R-002 §B).
        self._revoke_all_sessions(user.id)
        self.s.commit()
        return {"ok": True}

    def _revoke_all_sessions(self, user_id) -> None:
        self.s.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == uuid.UUID(str(user_id)), RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )

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
