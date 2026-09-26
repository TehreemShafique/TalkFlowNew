"""FastAPI auth dependencies: bearer-or-cookie JWT + permission gates.

`require_auth` re-resolves the principal against the DB on every request (the
JWT carries only the email + jti) and checks the Redis revocation blacklist, so
revoked sessions and status changes take effect immediately.  `require_permissions`
implements Rule R4's explicit gate at the dependency layer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from app.core.permissions import has_permission, permissions_for_roles
from app.core.redis import is_token_blacklisted
from app.core.security import decode_access_token
from app.packages.contracts.enums import UserStatus
from app.packages.contracts.errors import NotAuthenticatedError, PermissionDeniedError
from app.packages.db.models import User, UserSession

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    """Prefer the Authorization header (API clients); fall back to the cookie."""
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return request.cookies.get(settings.cookie_name)


async def fetch_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(func.lower(User.email) == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def require_auth(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
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

    # DB-backed session ledger verification
    session_result = await db.execute(
        select(UserSession).where(UserSession.token_id == jti)
    )
    user_session = session_result.scalar_one_or_none()
    if user_session is None or user_session.revoked_at is not None:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Session has been revoked or expired."
        )

    # Touch last_seen_at if more than 5 minutes have elapsed
    now = datetime.now(UTC)
    last_seen = user_session.last_seen_at
    if (
        last_seen is None
        or (
            last_seen.tzinfo is None
            and now.replace(tzinfo=None) - last_seen > timedelta(minutes=5)
        )
        or (last_seen.tzinfo is not None and now - last_seen > timedelta(minutes=5))
    ):
        user_session.last_seen_at = now
        await db.commit()

    user = await fetch_user_by_email(db, sub)
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
        session_token_id=jti,
    )


AuthDependency = Annotated[UserContext, Depends(require_auth)]


def require_permissions(required_permissions: list[str]):
    """Dependency builder (Rule R4): assert the user holds every permission."""

    async def checker(
        user: Annotated[UserContext, Depends(require_auth)],
    ) -> UserContext:
        missing = [
            p for p in required_permissions if not has_permission(user.permissions, p)
        ]
        if missing:
            raise PermissionDeniedError(
                "auth.permission_denied",
                message=f"Missing permission(s): {', '.join(sorted(missing))}.",
            )
        return user

    return checker


class RequirePermission:
    """Class-based permission gate (Rule R4) for sensitive routes.

    Usage: ``user: Annotated[UserContext, Depends(RequirePermission(PERM))]``.
    Legacy permission spellings are accepted through
    ``permissions.has_permission`` so grants minted before the RP-27 rename
    keep resolving.
    """

    def __init__(self, permission: str) -> None:
        self.permission = permission

    async def __call__(
        self,
        user: Annotated[UserContext, Depends(require_auth)],
    ) -> UserContext:
        if not has_permission(user.permissions, self.permission):
            raise PermissionDeniedError(
                "auth.permission_denied",
                message=f"Missing permission(s): {self.permission}.",
            )
        return user
