"""AuthService — orchestrates models + pure security/refresh logic over a DB
session. This is the only place that touches auth tables."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth import refresh as rf
from app.modules.auth import security as sec
from app.modules.auth.apple import AppleClient
from app.modules.auth.models import Org, OrgMember, RefreshToken, User
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
    ):
        self.s = session
        self.keys = keys
        self.access_ttl = timedelta(minutes=access_ttl_min)
        self.refresh_ttl = timedelta(days=refresh_ttl_days)
        self._apple = apple_client

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
            org_name = self._apple_org_name(user_json)
            org = Org(name=org_name, country="IN")
            self.s.add_all([user, org])
            self.s.flush()
            self.s.add(OrgMember(org_id=org.id, user_id=user.id, role="owner"))
        else:
            if not user.apple_id:
                user.apple_id = sub
            if email and not user.email:
                user.email = email
            user.email_verified = True

        self.s.commit()
        member = self.s.scalar(select(OrgMember).where(OrgMember.user_id == user.id))
        if not member:
            raise AuthError("no_org")
        return self._issue_tokens(user.id, member.org_id, member.role, new_family=True)

    def _apple_org_name(self, user_json: str | None) -> str:
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
