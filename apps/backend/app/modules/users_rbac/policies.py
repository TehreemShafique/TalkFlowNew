"""Role-assignment policy gates for user administration (Rule R4)."""
from __future__ import annotations

from app.core.permissions import APPROVABLE_ROLE_NAMES


def is_approvable_role(role_name: str) -> bool:
    """Only DEVOPS_IT / CAMPAIGN_MANAGER / QA / VIEWER are public approvable."""
    return role_name in APPROVABLE_ROLE_NAMES


def can_assign_roles(caller_roles: list[str], target_roles: list[str]) -> bool:
    """Restrict granting MASTER_ADMIN to users who already hold it."""
    if "MASTER_ADMIN" not in target_roles:
        return True
    return "MASTER_ADMIN" in caller_roles


def is_master(role_names: list[str]) -> bool:
    return "MASTER_ADMIN" in role_names