"""Admin / RBAC wire models (port of auth-service admin + roles schemas)."""

from __future__ import annotations

import uuid

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import UserStatus


class ApproveUserRequest(APIBaseModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class RejectUserRequest(APIBaseModel):
    reason: str | None = Field(default=None, max_length=255)


class UpdateUserAdminRequest(APIBaseModel):
    username: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    is_active: bool | None = None
    role_names: list[str] | None = None


class RolePublic(APIBaseModel):
    id: uuid.UUID
    name: str
    domain: str
    description: str | None = None
    is_system: bool = False
    permissions: list[str] = Field(default_factory=list)


class UserListQuery(APIBaseModel):
    """Pagination + approval-status filter for GET /users."""

    page: int = 1
    page_size: int = 20
    status: UserStatus | None = None
