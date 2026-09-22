"""HTTP surface for user & role administration (/api/v1/users, /api/v1/roles).

Every admin endpoint is guarded by an explicit `require_permissions` gate
(Rule R4) using the user.* / role.* permission strings from core.permissions.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import (
    PERM_ROLE_VIEW,
    PERM_USER_APPROVE,
    PERM_USER_DELETE,
    PERM_USER_EDIT,
    PERM_USER_VIEW,
    permissions_for_roles,
)
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import UserPublic
from app.modules.users_rbac import service
from app.modules.users_rbac.schemas import (
    ApproveUserRequest,
    RejectUserRequest,
    RolePublic,
    UpdateUserAdminRequest,
    UserListQuery,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse

router = APIRouter(tags=["users", "roles"])

Db = Depends(get_db)

UserPage = PagedResponse[UserPublic]
UserEnvelope = DataResponse[UserPublic]
MessageEnvelope = DataResponse[dict[str, str]]
RolesEnvelope = DataResponse[list[RolePublic]]
PermissionsEnvelope = DataResponse[list[str]]


@router.get("/users", response_model=UserPage)
async def list_users(
    query: Annotated[UserListQuery, Depends()],
    actor: Annotated[UserContext, Depends(require_permissions([PERM_USER_VIEW]))],
    db: AsyncSession = Db,
):
    users, total = await service.list_users(
        db, query.status, query.page, query.page_size
    )
    total_pages = (total + query.page_size - 1) // query.page_size
    return PagedResponse[UserPublic](
        data=[auth_service.serialize_user(u) for u in users],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.patch("/users/{user_id}/approve", response_model=UserEnvelope)
async def approve_user(
    user_id: uuid.UUID,
    payload: ApproveUserRequest,
    actor: Annotated[UserContext, Depends(require_permissions([PERM_USER_APPROVE]))],
    db: AsyncSession = Db,
):
    user = await service.approve_user(db, actor, user_id, payload.role_ids)
    return DataResponse[UserPublic](data=auth_service.serialize_user(user))


@router.patch("/users/{user_id}/reject", response_model=MessageEnvelope)
async def reject_user(
    user_id: uuid.UUID,
    actor: Annotated[UserContext, Depends(require_permissions([PERM_USER_APPROVE]))],
    payload: RejectUserRequest | None = None,
    db: AsyncSession = Db,
):
    await service.reject_user(db, actor, user_id, payload.reason if payload else None)
    return DataResponse[dict[str, str]](data={"message": "User has been rejected"})


@router.patch("/users/{user_id}", response_model=UserEnvelope)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserAdminRequest,
    actor: Annotated[UserContext, Depends(require_permissions([PERM_USER_EDIT]))],
    db: AsyncSession = Db,
):
    user = await service.update_user_by_admin(db, actor, user_id, payload)
    return DataResponse[UserPublic](data=auth_service.serialize_user(user))


@router.delete("/users/{user_id}", response_model=MessageEnvelope)
async def delete_user(
    user_id: uuid.UUID,
    actor: Annotated[UserContext, Depends(require_permissions([PERM_USER_DELETE]))],
    db: AsyncSession = Db,
):
    await service.delete_user(db, actor, user_id)
    return DataResponse[dict[str, str]](data={"message": "User has been deleted"})


@router.get("/roles", response_model=RolesEnvelope)
async def list_roles(
    actor: Annotated[UserContext, Depends(require_permissions([PERM_ROLE_VIEW]))],
    db: AsyncSession = Db,
):
    roles = await service.get_all_roles(db)
    return DataResponse[list[RolePublic]](
        data=[service.serialize_role(r) for r in roles]
    )


@router.get("/roles/permissions", response_model=PermissionsEnvelope)
async def list_permissions(
    actor: Annotated[UserContext, Depends(require_permissions([PERM_ROLE_VIEW]))],
    db: AsyncSession = Db,
):
    roles = await service.get_all_roles(db)
    flattened = permissions_for_roles([r.name for r in roles])
    return DataResponse[list[str]](data=sorted(flattened))
