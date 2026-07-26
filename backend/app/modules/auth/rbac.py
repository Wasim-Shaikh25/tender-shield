"""Roles and the authenticated principal (Doc §5). Pure, DB-free."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_RANK = {"viewer": 0, "reviewer": 1, "estimator": 2, "admin": 3, "owner": 4}
ROLES = tuple(ROLE_RANK)


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    role: str
    is_superadmin: bool = False


def role_at_least(role: str, min_role: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[min_role]
