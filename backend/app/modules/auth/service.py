"""AuthService — orchestrates models + pure security/refresh logic over a DB
session. This is the only place that touches auth tables."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth import refresh as rf
from app.modules.auth import security as sec
from app.modules.auth.models import Org, OrgMember, RefreshToken, User
from app.modules.auth.rbac import ROLES


class AuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AuthService:
    def __init__(
        self, session: Session, keys: sec.KeyPair, *, access_ttl_min=15, refresh_ttl_days=30
    ):
        self.s = session
        self.keys = keys
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)

    # ---- registration -----------------------------------------------------
    def signup(self, email: str, password: str, org_name: str, country: str = "IN") -> dict:
        email = email.strip().lower()
        if self.s.scalar(select(User).where(User.email == email)):
            raise AuthError("email_taken")
        user = User(email=email, password_hash=sec.hash_password(password))
        org = Org(name=org_name, country=country)
        self.s.add_all([user, org])
        self.s.flush()
        self.s.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
        self.s.commit()
        return {"user_id": str(user.id), "org_id": str(org.id)}

    # ---- login ------------------------------------------------------------
    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if (
            not user
            or not user.password_hash
            or not sec.verify_password(password, user.password_hash)
        ):
            raise AuthError("invalid_credentials")
        member = self.s.scalar(select(OrgMember).where(OrgMember.user_id == user.id))
        if not member:
            raise AuthError("no_org")
        return self._issue_tokens(user.id, member.org_id, member.role, new_family=True)

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
        member = self.s.scalar(select(OrgMember).where(OrgMember.user_id == row.user_id))
        tokens = self._issue_tokens(
            row.user_id, member.org_id, member.role, family_id=row.family_id
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
    def add_member(self, org_id: uuid.UUID | str, email: str, role: str) -> dict:
        if role not in ROLES:
            raise AuthError("bad_role")
        org_id = uuid.UUID(str(org_id))  # principal.org_id arrives as a JWT string
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if not user:
            raise AuthError("no_such_user")
        self.s.merge(OrgMember(org_id=org_id, user_id=user.id, role=role))
        self.s.commit()
        return {"org_id": str(org_id), "user_id": str(user.id), "role": role}

    # ---- internals --------------------------------------------------------
    def _issue_tokens(self, user_id, org_id, role, *, new_family=False, family_id=None) -> dict:
        access = sec.mint_access(
            self.keys, user_id=str(user_id), org_id=str(org_id), role=role, ttl=self.access_ttl
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
        return {"access_token": access, "refresh_token": raw, "role": role, "org_id": str(org_id)}

    def _revoke_family(self, family_id) -> None:
        for row in self.s.scalars(
            select(RefreshToken).where(RefreshToken.family_id == family_id)
        ):
            row.revoked = True
