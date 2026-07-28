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
    def __init__(self, code: str, *, upsell: dict | None = None):
        super().__init__(code)
        self.code = code
        # Set only for commercial-limit errors (e.g. seat_limit_reached,
        # R-009 §B.3) so the router can send the same {"code", "upsell"}
        # shape billing's PaywallError uses — the frontend's <Paywall/>
        # renders both without caring which module raised it.
        self.upsell = upsell


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
        entitlements=None,
        record_referral_signup=None,
        resolve_referral_code=None,
    ):
        self.s = session
        self.keys = keys
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self._apple = apple_client
        # DEV/TEST ONLY — see core/config.py Settings.dev_echo_tokens (R-002 §A).
        self._echo_tokens = echo_tokens
        self._notifier = notifier
        # Callable[[session, workspace_id, seats_used], Entitlements] — the
        # `billing.entitlements` capability, resolved by name (CLAUDE.md §2:
        # auth may not import billing). None when billing is disabled, in
        # which case seats are unlimited (spec core B2 — the app still boots
        # with any module subset).
        self._entitlements = entitlements
        # Callable[[session, referrer_workspace_id, referred_workspace_id,
        # code]] — the `billing.record_referral_signup` capability (R-006
        # §B.7). Absent when billing is disabled: a referral code still
        # works for signup, it just never earns a reward.
        self._record_referral_signup = record_referral_signup
        # Callable[[session, code], dict | None] — the `billing.
        # resolve_referral_code` capability. Resolves through billing's own
        # non-RLS `referral_codes` pointer table, NOT a `Workspace` query:
        # the signing-up caller is not yet a member of any workspace, so
        # RLS's compound predicate would hide the referrer's `workspaces` row
        # (found via an e2e run against real Postgres with FORCE RLS live —
        # a prior version of this used WorkspaceAdmin.find_by_referral_code,
        # which silently resolved nothing for every cross-tenant signup).
        self._resolve_referral_code = resolve_referral_code
        self._app_url = app_url.rstrip("/")

    def _notify(self, *, channel: str, to: str, subject: str, body: str) -> None:
        if self._notifier is None:
            logger.warning("no notifications sender available — %r to %s not sent", subject, to)
            return
        self._notifier.send(_MailMessage(channel=channel, to=to, subject=subject, body=body))

    def seats_used(self, workspace_id, *, excluding_invitation_id=None) -> int:
        """Accepted members plus LIVE pending invitations (R-009 §B.3) — an
        invitation that can never be accepted because the seat was already
        promised to someone else is a bad experience, so pending invites
        count toward the total, not just accepted members.

        `excluding_invitation_id` is for `accept_invitation`: that invitation
        already reserved its own seat when it was CREATED, so re-checking
        capacity at acceptance time must not double-count it — otherwise a
        workspace sitting exactly at capacity could never accept the very
        invitation that reservation was for.
        """
        workspace_id = uuid.UUID(str(workspace_id))
        members = (
            self.s.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(WorkspaceMember.workspace_id == workspace_id)
            )
            or 0
        )
        pending_query = select(func.count()).select_from(Invitation).where(
            Invitation.workspace_id == workspace_id,
            Invitation.used_at.is_(None),
            Invitation.expires_at > func.now(),
        )
        if excluding_invitation_id is not None:
            pending_query = pending_query.where(
                Invitation.id != uuid.UUID(str(excluding_invitation_id))
            )
        pending = self.s.scalar(pending_query) or 0
        return members + pending

    def _check_seat_available(self, workspace_id, *, excluding_invitation_id=None) -> None:
        """Raises AuthError("seat_limit_reached") — mapped to 402 with an
        upsell payload by the router, not 403: this is a commercial limit
        with an upgrade path, not an authorization failure (R-009 §B.3/B4).
        With billing disabled, no capability is published and the limit is
        simply absent (spec core B2 — the app still boots with any module
        subset)."""
        if self._entitlements is None:
            return
        seats_used = self.seats_used(workspace_id, excluding_invitation_id=excluding_invitation_id)
        e = self._entitlements(self.s, workspace_id, seats_used)
        if e.seats_remaining <= 0:
            raise AuthError(
                "seat_limit_reached",
                upsell={"seats_included": e.seats_included, "seats_used": e.seats_used},
            )

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
        self,
        email: str,
        password: str,
        workspace_name: str | None = None,
        country: str = "IN",
        referral_code: str | None = None,
    ) -> dict:
        email = email.strip().lower()
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        user = User(email=email, password_hash=sec.hash_password(password))
        self.s.add(user)
        self.s.flush()
        workspace = self._create_workspace_and_owner(user.id, workspace_name or "Personal", country)
        self._apply_referral(
            referral_code, referred_workspace_id=workspace.id, referred_email=email
        )
        self.s.commit()
        return {"user_id": str(user.id), "workspace_id": str(workspace.id)}

    def _apply_referral(self, referral_code, *, referred_workspace_id, referred_email) -> None:
        """Records a referral relationship at signup (R-006 §B.7) — the
        REWARD is credited later, on the referred workspace's first paid
        purchase (billing's own code, since Credit is billing-owned). Blocked
        silently (signup still succeeds) rather than erroring, for two
        reasons: an invalid/unknown code shouldn't block someone from signing
        up, and self-referral shouldn't tip the referrer off that their
        attempt was detected.
        """
        if (
            not referral_code
            or self._record_referral_signup is None
            or self._resolve_referral_code is None
        ):
            return
        # Resolved via billing's non-RLS `referral_codes` table, not a
        # `Workspace` query — the referred user isn't a member of the
        # referrer's workspace (or any workspace) yet, so RLS would hide it.
        referrer = self._resolve_referral_code(self.s, referral_code)
        if referrer is None or str(referrer["workspace_id"]) == str(referred_workspace_id):
            return
        referrer_domain = referrer.get("owner_email_domain")
        referred_domain = (
            referred_email.rsplit("@", 1)[1].lower() if "@" in referred_email else None
        )
        if referrer_domain and referred_domain and referrer_domain == referred_domain:
            return  # self-referral (R-006 §A9): same employer domain on both sides
        self._record_referral_signup(
            self.s, referrer["workspace_id"], referred_workspace_id, referral_code.upper()
        )

    # ---- login ------------------------------------------------------------
    _LOCKOUT_THRESHOLD = 10
    _LOCKOUT_MAX_MINUTES = 60

    def _resolve_login_workspace(self, user: User) -> WorkspaceMember | None:
        """Pick the workspace to sign into, deterministically (R-011 §B.1).

        Order: explicit default -> last used -> oldest membership. Without
        this, the same user could land in a different workspace between
        logins depending on what the database happened to return first for
        an unordered `WorkspaceMember` query — a genuinely confusing bug to
        report and to debug, and the reason this method exists at all.
        Falls through past a candidate the user is no longer a member of
        (membership can be revoked after a workspace was set as default/last
        used — that is a normal state, not a data-integrity error).
        """
        for candidate in (user.default_workspace_id, user.last_workspace_id):
            if candidate:
                member = self._workspace_member(candidate, user.id)
                if member:
                    return member
        return self.s.scalar(
            select(WorkspaceMember)
            .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(Workspace.created_at.asc())
            .limit(1)
        )

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
        member = self._resolve_login_workspace(user)
        if not member:
            # A user with zero memberships gets a workspace-less token
            # instead of being locked out (R-011 §B.6) — the frontend routes
            # this to /workspaces/new rather than a dead-end 401. Role is a
            # placeholder ("owner") since RBAC only applies within a
            # workspace; matches the pre-existing superadmin-with-no-
            # workspace case this generalizes.
            return self._issue_tokens(
                user.id, None, "owner", is_superadmin=user.is_superadmin, new_family=True
            )
        user.last_workspace_id = member.workspace_id
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
        # Same deterministic resolution as login() (R-011 §B.1) — a naive
        # unordered WorkspaceMember query here had the identical bug: a
        # refresh could re-mint an access token scoped to a DIFFERENT
        # workspace than the one the session started in, purely because of
        # row ordering. Doesn't touch last_workspace_id itself — a refresh
        # is a transparent continuation, not a fresh workspace choice; only
        # login and switch_workspace update it.
        member = self._resolve_login_workspace(user) if user else None
        if not member:
            tokens = self._issue_tokens(
                row.user_id,
                None,
                "owner",
                is_superadmin=user.is_superadmin if user else False,
                family_id=row.family_id,
            )
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
        member = self._resolve_login_workspace(user)
        if not member:
            # R-011 §B.6 — see login()'s identical branch.
            return self._issue_tokens(
                user.id, None, "owner", is_superadmin=user.is_superadmin, new_family=True
            )
        user.last_workspace_id = member.workspace_id
        self.s.commit()
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

    def list_workspaces(self, user_id, *, current_workspace_id=None) -> list[dict]:
        rows = self.s.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == uuid.UUID(str(user_id)))
        ).all()
        current = str(current_workspace_id) if current_workspace_id else None
        return [
            {
                "workspace_id": str(ws.id),
                "name": ws.name,
                "role": m.role,
                "plan": ws.plan,
                "is_current": str(ws.id) == current,
            }
            for ws, m in rows
        ]

    def switch_workspace(self, user_id, workspace_id, *, refresh_token: str | None = None) -> dict:
        """Re-issue tokens scoped to another workspace the caller belongs to
        (R-011 §B.2). Membership is verified server-side — the client cannot
        select a workspace by editing a token, since the workspace claim is
        what RLS binds to (auth/deps.py's authenticate()).

        Retires the previous refresh-token family: one active session per
        user at a time (assumption, R-011) keeps the reuse-detection model in
        `refresh()` simple and means a switch can never leave a stale token
        scoped to the OLD workspace still valid. The trade-off is that a user
        cannot hold two workspaces open in two tabs simultaneously.
        """
        member = self._workspace_member(workspace_id, user_id)
        if not member:
            raise AuthError("not_workspace_member")  # -> 404, per R-001 §B2
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if not user:
            raise AuthError("no_such_user")
        user.last_workspace_id = member.workspace_id
        if refresh_token:
            old = self.s.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == rf.hash_token(refresh_token))
            )
            if old:
                self._revoke_family(old.family_id)
        tokens = self._issue_tokens(
            user.id,
            member.workspace_id,
            member.role,
            is_superadmin=user.is_superadmin,
            new_family=True,
        )
        return tokens

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
            # A role change for an existing member consumes no new seat —
            # only check when this is a genuinely NEW member (R-009 §B.3).
            self._check_seat_available(workspace_id)
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
        # A pending invitation counts toward the seat total (R-009 §B.3) —
        # checked before creating it, not after, so an over-limit invite is
        # never sent at all.
        self._check_seat_available(workspace_id)
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
            # Re-checked at acceptance, not just at invite-creation time
            # (R-009 §B.3) — seats may have filled up in between; excluding
            # THIS invitation avoids double-counting the seat it already
            # reserved when created.
            self._check_seat_available(
                invitation.workspace_id, excluding_invitation_id=invitation.id
            )
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
