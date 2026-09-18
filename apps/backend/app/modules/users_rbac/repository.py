"""Data access for users, roles, sessions (Rule R3 - module-scoped)."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.packages.contracts.enums import UserStatus
from app.packages.db.models import Role, User, UserSession, user_roles


def _with_roles(stmt):
    return stmt.options(selectinload(User.roles))


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(_with_roles(select(User)).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        _with_roles(select(User)).where(func.lower(User.email) == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def username_exists(db: AsyncSession, username: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(User.id).where(User.username == username)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


async def list_users(
    db: AsyncSession,
    status_filter: UserStatus | str | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    filters = []
    if status_filter is not None:
        status_value = (
            status_filter.value
            if isinstance(status_filter, UserStatus)
            else UserStatus(status_filter).value
        )
        filters.append(User.status == status_value)

    total = (
        await db.execute(
            select(func.count(User.id)).where(and_(*filters))
        )
    ).scalar_one()

    stmt = (
        _with_roles(select(User))
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = list((await db.execute(stmt)).scalars().all())
    return users, total


async def get_role_by_id(db: AsyncSession, role_id: uuid.UUID) -> Role | None:
    result = await db.execute(select(Role).where(Role.id == role_id))
    return result.scalar_one_or_none()


async def get_roles_by_ids(db: AsyncSession, role_ids: list[uuid.UUID]) -> list[Role]:
    if not role_ids:
        return []
    result = await db.execute(select(Role).where(Role.id.in_(role_ids)))
    return list(result.scalars().all())


async def get_roles_by_names(db: AsyncSession, names: list[str]) -> list[Role]:
    if not names:
        return []
    result = await db.execute(select(Role).where(Role.name.in_(names)))
    return list(result.scalars().all())


async def get_all_roles(db: AsyncSession) -> list[Role]:
    result = await db.execute(select(Role).order_by(Role.domain, Role.name))
    return list(result.scalars().all())


async def find_role_by_name(db: AsyncSession, name: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.name == name))
    return result.scalar_one_or_none()


async def user_has_role(db: AsyncSession, user_id: uuid.UUID, role_name: str) -> bool:
    stmt = (
        select(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(User.id == user_id, Role.name == role_name)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def count_other_master_admins(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = (
        select(func.count(User.id))
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.name == "MASTER_ADMIN", User.id != user_id)
    )
    return (await db.execute(stmt)).scalar_one()


async def replace_user_roles(db: AsyncSession, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> None:
    """Replace a user's role membership (single logical operation)."""
    await db.execute(delete(user_roles).where(user_roles.c.user_id == user_id))
    if role_ids:
        await db.execute(
            user_roles.insert().values(
                [{"user_id": user_id, "role_id": role_id} for role_id in role_ids]
            )
        )


async def delete_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(UserSession).where(UserSession.user_id == user_id)
    )


async def hard_delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(delete(User).where(User.id == user_id))