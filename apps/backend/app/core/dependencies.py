"""FastAPI auth dependencies: bearer-or-cookie JWT + permission gates.

`require_auth` re-resolves the principal against the DB on every request (the
JWT carries only the email + jti) and checks the Redis revocation blacklist, so
revoked sessions and status changes take effect immediately.  `require_permissions`
implements Rule R4's explicit gate at the dependency layer.
"""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.context import UserContext
from app.core.database import get_db
from app.core.permissions import permissions_for_roles
from app.core.redis import is_token_blacklisted
from app.core.security import decode_access_token
from app.packages.contracts.enums import UserStatus
from app.packages.contracts.errors import NotAuthenticatedError, PermissionDeniedError
from app.packages.db.models import User

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """Prefer the Authorization header (API clients); fall back to the cookie."""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return request.cookies.get(settings.cookie_name)


async def _fetch_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(func.lower(User.email) == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def require_auth(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> UserContext:
    """Authenticate the principal; raise 401 when missing/invalid/revoked."""
    token = _extract_token(request, credentials)
    if not token:
        raise NotAuthenticatedError("auth.not_authenticated")

    try:
        payload = decode_access_token(token)
        sub: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if not sub or not jti:
            raise NotAuthenticatedError(
                "auth.not_authenticated", message="Invalid token payload."
            )
    except jwt.PyJWTError:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Token has expired or is invalid."
        ) from None

    if await is_token_blacklisted(jti):
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Session has been revoked."
        )

    user = await _fetch_user_by_email(db, sub)
    if not user or not user.is_active:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="User inactive or not found."
        )
    if user.status != UserStatus.APPROVED:
        raise PermissionDeniedError(
            "auth.permission_denied", message="Account is not approved."
        )

    role_names = [r.name for r in user.roles] if user.roles else []
    permissions = permissions_for_roles(role_names)
    role = role_names[0] if role_names else "agent"
    return UserContext.from_principal(
        user_id=user.id,
        role=role,
        permissions=permissions,
        issued_at=payload.get("iat"),
    )


AuthDependency = Annotated[UserContext, Depends(require_auth)]


def require_permissions(required_permissions: list[str]):
    """Dependency builder (Rule R4): assert the user holds every permission."""

    async def checker(user: Annotated[UserContext, Depends(require_auth)]) -> UserContext:
        missing = [p for p in required_permissions if p not in user.permissions]
        if missing:
            raise PermissionDeniedError(
                "auth.permission_denied",
                message=f"Missing permission(s): {', '.join(sorted(missing))}.",
            )
        return user

    return checker