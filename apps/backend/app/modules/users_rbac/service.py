"""User & role administration service (port of auth-service admin + roles).

Every state-changing operation writes an ``audit_log`` row in the same
transaction (blueprint section 10) and clears the Redis role cache so live
sessions pick up the new permissions immediately.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import settings
from app.core.context import UserContext
from app.core.permissions import ROLE_PERMISSIONS
from app.core.redis import clear_cached_user_roles
from app.core.security import hash_password
from app.modules.users_rbac import repository as repo
from app.modules.users_rbac.errors import (
    AlreadyApprovedError,
    AlreadyRejectedError,
    EmailConflictError,
    MasterRemovalError,
    MasterRestrictedError,
    RoleNotAssignableError,
    SelfDeleteError,
    SingleMasterError,
    UnknownRoleError,
    UsernameConflictError,
    UserNotFoundError,
)
from app.modules.users_rbac.events import (
    UserManagementEventType,
    publish_user_event,
)
from app.modules.users_rbac.policies import (
    can_assign_roles,
    is_approvable_role,
    is_master,
)
from app.modules.users_rbac.schemas import RolePublic, UpdateUserAdminRequest
from app.packages.contracts.enums import AuditResult, RoleDomain, UserStatus
from app.packages.db.models import Role, User

ROLE_SEED: list[dict] = [
    {
        "name": "MASTER_ADMIN",
        "domain": RoleDomain.SYSTEM.value,
        "description": "System administration, global settings, & full administrative privileges.",
        "is_system": True,
    },
    {
        "name": "DEVOPS_IT",
        "domain": RoleDomain.SYSTEM.value,
        "description": "Technical infrastructure, telephony integrations & developer operations.",
        "is_system": True,
    },
    {
        "name": "CAMPAIGN_MANAGER",
        "domain": RoleDomain.OPERATIONS.value,
        "description": "Dialer campaigns, lead routing, schedules & outbound lists.",
        "is_system": True,
    },
    {
        "name": "QA",
        "domain": RoleDomain.QUALITY.value,
        "description": "Quality assurance audits, call evaluation & compliance scoring.",
        "is_system": True,
    },
    {
        "name": "VIEWER",
        "domain": RoleDomain.VERIFICATION.value,
        "description": "Medicare verifiers, licensed call agents & customer verification.",
        "is_system": True,
    },
    {
        "name": "REPORTING_USER",
        "domain": RoleDomain.REPORTING.value,
        "description": "Call performance metrics, report generation & analytics access.",
        "is_system": True,
    },
    {
        "name": "COMPLIANCE_OFFICER",
        "domain": RoleDomain.QUALITY.value,
        "description": "Compliance review of recorded audio with privileged PHI access.",
        "is_system": True,
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
async def seed_roles(db: AsyncSession) -> None:
    """Create the system roles if absent (idempotent; migration seeds them too)."""
    for seed in ROLE_SEED:
        if await repo.find_role_by_name(db, seed["name"]) is None:
            db.add(Role(**seed))
    await db.commit()


async def seed_super_admin(db: AsyncSession) -> None:
    """Ensure the .env super-admin exists, is APPROVED, and holds MASTER_ADMIN."""
    master_role = await repo.find_role_by_name(db, "MASTER_ADMIN")
    if master_role is None:
        return

    existing = await repo.get_user_by_email(db, settings.seed_admin_email)
    if existing is None:
        user = User(
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            full_name=settings.seed_admin_full_name,
            username="admin",
            extension="Not assigned",
            is_active=True,
            status=UserStatus.APPROVED.value,
        )
        db.add(user)
        await db.flush()
        await repo.replace_user_roles(db, user.id, [master_role.id])
        await db.commit()
        return

    if existing.status != UserStatus.APPROVED.value:
        existing.status = UserStatus.APPROVED.value
    if not await repo.user_has_role(db, existing.id, "MASTER_ADMIN"):
        await repo.replace_user_roles(
            db, existing.id, [r.id for r in existing.roles] + [master_role.id]
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
def serialize_role(role: Role) -> RolePublic:
    return RolePublic(
        id=role.id,
        name=role.name,
        domain=role.domain,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(ROLE_PERMISSIONS.get(role.name.upper(), ())),
    )


async def get_role_domains(db: AsyncSession) -> list[dict]:
    """Roles grouped by domain - drives the admin role picker."""
    roles = await repo.get_all_roles(db)
    grouped: dict[str, list[str]] = {}
    for role in roles:
        grouped.setdefault(role.domain, []).append(role.name)
    return [
        {"domain": domain, "roles": names} for domain, names in sorted(grouped.items())
    ]


async def get_all_roles(db: AsyncSession) -> list[Role]:
    return await repo.get_all_roles(db)


# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------
async def _reload_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    db.expire_all()
    user = await repo.get_user(db, user_id)
    if user is None:  # pragma: no cover - checked before the mutation
        raise UserNotFoundError()
    return user


def _role_names(user: User) -> list[str]:
    return [r.name for r in user.roles] if user.roles else []


async def approve_user(
    db: AsyncSession,
    actor: UserContext,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> User:
    user = await repo.get_user(db, user_id)
    if user is None:
        raise UserNotFoundError()
    if user.status == UserStatus.APPROVED.value:
        raise AlreadyApprovedError()

    roles = await repo.get_roles_by_ids(db, role_ids)
    if len(roles) != len(role_ids):
        raise UnknownRoleError()
    disallowed = [r.name for r in roles if not is_approvable_role(r.name)]
    if disallowed:
        raise RoleNotAssignableError(disallowed)
    if not can_assign_roles(_role_names(user), [r.name for r in roles]):
        raise MasterRestrictedError()

    user.status = UserStatus.APPROVED.value
    await repo.replace_user_roles(db, user.id, role_ids)
    await publish_user_event(
        db,
        user_id=user.id,
        event_type=UserManagementEventType.USER_APPROVED,
        metadata={"role_ids": [str(r) for r in role_ids]},
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="user.approved",
        resource_type="user",
        resource_id=str(user.id),
        result=AuditResult.SUCCESS,
        details={"role_ids": [str(r) for r in role_ids]},
    )
    await db.commit()
    await clear_cached_user_roles(user.id)
    return await _reload_user(db, user.id)


async def reject_user(
    db: AsyncSession,
    actor: UserContext,
    user_id: uuid.UUID,
    reason: str | None = None,
) -> None:
    user = await repo.get_user(db, user_id)
    if user is None:
        raise UserNotFoundError()
    if user.status == UserStatus.REJECTED.value:
        raise AlreadyRejectedError()

    user.status = UserStatus.REJECTED.value
    await publish_user_event(
        db,
        user_id=user.id,
        event_type=UserManagementEventType.USER_REJECTED,
        metadata={"reason": reason},
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="user.rejected",
        resource_type="user",
        resource_id=str(user.id),
        result=AuditResult.SUCCESS,
        details={"reason": reason},
    )
    await db.commit()
    await clear_cached_user_roles(user.id)


async def list_users(
    db: AsyncSession,
    status_filter: UserStatus | str | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    return await repo.list_users(db, status_filter, page, page_size)


async def update_user_by_admin(
    db: AsyncSession,
    actor: UserContext,
    user_id: uuid.UUID,
    payload: UpdateUserAdminRequest,
) -> User:
    user = await repo.get_user(db, user_id)
    if user is None:
        raise UserNotFoundError()

    # Resolve the caller's real role set for MASTER_ADMIN gates.
    admin = await repo.get_user(db, actor.user_id)
    caller_role_names = _role_names(admin) if admin else []
    caller_is_master = is_master(caller_role_names)

    # --- validate every change first: no partial mutation if any guard fails ---
    new_username = payload.username
    if (
        new_username is not None
        and new_username != user.username
        and await repo.username_exists(db, new_username, exclude_id=user.id)
    ):
        raise UsernameConflictError()

    new_email = payload.email.strip().lower() if payload.email is not None else None
    if (
        new_email is not None
        and new_email != (user.email or "").lower()
        and await repo.get_user_by_email(db, new_email) is not None
    ):
        raise EmailConflictError()

    new_role_ids: list[uuid.UUID] = []
    if payload.role_names is not None:
        new_names = list(dict.fromkeys(payload.role_names))
        roles = await repo.get_roles_by_names(db, new_names)
        valid_names = {r.name for r in roles}
        missing = [n for n in new_names if n not in valid_names]
        if missing:
            raise UnknownRoleError()

        current_names = _role_names(user)
        if "MASTER_ADMIN" in new_names and not caller_is_master:
            raise MasterRestrictedError()
        if is_master(current_names) and "MASTER_ADMIN" not in new_names:
            raise MasterRemovalError()
        if (
            "MASTER_ADMIN" in new_names
            and not is_master(current_names)
            and await repo.count_other_master_admins(db, user.id) > 0
        ):
            raise SingleMasterError()

        new_role_ids = [r.id for r in roles]

    # --- all guards passed: apply the mutations in one place ---
    if new_username is not None and new_username != user.username:
        user.username = new_username
    if new_email is not None and new_email != (user.email or "").lower():
        user.email = new_email
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role_names is not None:
        await repo.replace_user_roles(db, user.id, new_role_ids)

    await publish_user_event(
        db,
        user_id=user.id,
        event_type=UserManagementEventType.USER_UPDATED,
        metadata={"updated_by": str(actor.user_id)},
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="user.updated",
        resource_type="user",
        resource_id=str(user.id),
        result=AuditResult.SUCCESS,
        details={"role_names": payload.role_names, "is_active": payload.is_active},
    )
    await db.commit()
    await clear_cached_user_roles(user.id)
    return await _reload_user(db, user.id)


async def delete_user(
    db: AsyncSession,
    actor: UserContext,
    user_id: uuid.UUID,
) -> None:
    if actor.user_id == user_id:
        raise SelfDeleteError()

    user = await repo.get_user(db, user_id)
    if user is None:
        raise UserNotFoundError()

    await repo.delete_user_sessions(db, user.id)
    await repo.replace_user_roles(db, user.id, [])
    await repo.hard_delete_user(db, user.id)
    await publish_user_event(
        db,
        user_id=user_id,
        event_type=UserManagementEventType.USER_DELETED,
        metadata={"deleted_by": str(actor.user_id)},
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="user.deleted",
        resource_type="user",
        resource_id=str(user_id),
        result=AuditResult.SUCCESS,
    )
    await db.commit()
    await clear_cached_user_roles(user_id)
