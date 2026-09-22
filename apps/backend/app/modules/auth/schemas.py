"""Auth wire models (port of services/auth-service/app/modules/auth/schema.py).

Rule R7 - `UserPublic` never carries hashes or PINs; only the fields the
dashboard shows.  `status` mirrors the approval lifecycle (PENDING/APPROVED/
REJECTED); `permissions` is derived from the user's roles by the service layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import UserStatus


class LoginRequest(APIBaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class PinLoginRequest(APIBaseModel):
    email: str = Field(min_length=1)
    collaborator_pin: str = Field(min_length=4, max_length=4)


class SignupRequest(APIBaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=6)
    full_name: str | None = Field(default=None, max_length=160)
    username: str | None = Field(default=None, max_length=120)


class UserPublic(APIBaseModel):
    """Public projection of a user - secrets intentionally excluded (Rule R7)."""

    id: uuid.UUID
    username: str | None = None
    email: str
    full_name: str | None = None
    status: UserStatus = UserStatus.PENDING
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True


class TokenResponse(APIBaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class ProfileUpdateResponse(APIBaseModel):
    """PATCH /me result - carries a fresh token when the email changed."""

    access_token: str | None = None
    token_type: str = "bearer"
    user: UserPublic


class MessageResponse(APIBaseModel):
    message: str


class UpdateProfileRequest(APIBaseModel):
    """Editable profile fields.  `password`/`collaborator_pin` are re-hashed."""

    email: str | None = Field(default=None, min_length=3, max_length=254)
    full_name: str | None = Field(default=None, max_length=160)
    password: str | None = Field(default=None, min_length=6, max_length=255)
    collaborator_pin: str | None = Field(default=None, min_length=4, max_length=4)


class UserSessionDTO(APIBaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    token_id: str
    user_agent: str | None = None
    ip_address: str | None = None
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
