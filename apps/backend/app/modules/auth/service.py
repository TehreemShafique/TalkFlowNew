"""Auth domain logic: password/PIN auth, token issue, session tracking, logout.

Port of services/auth-service/app/modules/auth/service.py + account/service.py
(merged: the control plane treats session tracking as part of the auth module).
Every mutating operation commits once at the end so the outbox event and the
state change are one transaction (Rule R8).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import uuid4

import jwt
from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import permissions_for_roles
from app.core.redis import (
    blacklist_token,
    clear_cached_user_roles,
    set_cached_user_roles,
)
from app.core.security import (
    clear_access_token_cookie,
    create_access_token,
    decode_access_token,
    hash_password,
    set_access_token_cookie,
    verify_password,
)
from app.modules.auth.errors import (
    AccountDisabledError,
    AccountPendingError,
    AccountRejectedError,
    EmailConflictError,
)
from app.modules.auth.events import AuthEventType, publish_auth_event
from app.modules.auth.policies import can_login
from app.modules.auth.repository import get_user_by_email
from app.modules.auth.schemas import SignupRequest, UpdateProfileRequest, UserPublic
from app.packages.contracts.enums import UserStatus
from app.packages.db.models import User, UserSession

# Denied-login reason -> exception dispatch (deny by default via fallback).
_LOGIN_FAILURES: dict[str, type[AccountDisabledError | AccountRejectedError]] = {
    "disabled": AccountDisabledError,
    "rejected": AccountRejectedError,
}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.hashed_password:
        return None
    return user if verify_password(password, user.hashed_password) else None


async def authenticate_pin(db: AsyncSession, email: str, pin: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not user.collaborator_pin:
        return None
    return user if verify_password(pin, user.collaborator_pin) else None


def ensure_login_allowed(user: User) -> None:
    """Only fully approved, active accounts may authenticate (Rule R6)."""
    allowed, reason = can_login(user.status, user.is_active)
    if allowed:
        return
    raise _LOGIN_FAILURES.get(reason or "", AccountPendingError)()


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------
async def signup_user(db: AsyncSession, payload: SignupRequest) -> User:
    """Create a PENDING account; administrators approve it later."""
    email = payload.email.strip().lower()
    if await get_user_by_email(db, email) is not None:
        raise EmailConflictError()

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() or None if payload.full_name else None,
        username=payload.username.strip() or None if payload.username else None,
        is_active=True,
        status=UserStatus.PENDING.value,
    )
    db.add(user)
    await db.flush()
    await publish_auth_event(
        db,
        user_id=user.id,
        event_type=AuthEventType.SIGNUP_REQUESTED,
        metadata={"email": email},
    )
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Token issuance / revocation
# ---------------------------------------------------------------------------
async def issue_user_token(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
) -> str:
    """Mint a JWT, record the UserSession, cache roles, bake the cookie."""
    token_id = generate_token_id()
    access_token, _ = create_access_token({"sub": user.email, "jti": token_id})
    set_access_token_cookie(response, access_token)

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    await create_user_session(db, user.id, token_id, user_agent, ip_address)
    await publish_auth_event(
        db,
        user_id=user.id,
        event_type=AuthEventType.SESSION_CREATED,
        metadata={"jti": token_id},
    )
    await db.commit()
    await refresh_user_role_cache(db, user)
    return access_token


async def logout_user(db: AsyncSession, token: str | None, response: Response) -> None:
    """Blacklist the jti, revoke the session, always clear the cookie."""
    clear_access_token_cookie(response)
    if not token:
        return
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return
    jti = payload.get("jti")
    if not jti:
        return
    await blacklist_token(jti)
    was_revoked = await revoke_user_session(db, jti)
    if was_revoked:
        await publish_auth_event(
            db,
            user_id=payload.get("sub"),
            event_type=AuthEventType.SESSION_REVOKED,
            metadata={"jti": jti},
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Profile updates
# ---------------------------------------------------------------------------
async def update_user_profile(
    db: AsyncSession, user: User, payload: UpdateProfileRequest
) -> tuple[User, bool]:
    """Apply editable profile fields; returns ``(user, email_changed)``.

    When the email changes a fresh token is re-issued by the router so the JWT
    (which embeds the old email as ``sub``) stays valid.
    """
    email_changed = False
    if (
        payload.email is not None
        and payload.email.strip().lower() != user.email.lower()
    ):
        new_email = payload.email.strip().lower()
        existing = await get_user_by_email(db, new_email)
        if existing is not None and existing.id != user.id:
            raise EmailConflictError()
        user.email = new_email
        email_changed = True

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None

    if payload.password is not None:
        user.hashed_password = hash_password(payload.password)

    if payload.collaborator_pin is not None:
        user.collaborator_pin = (
            hash_password(payload.collaborator_pin)
            if payload.collaborator_pin
            else None
        )

    await db.commit()
    await db.refresh(user)
    return user, email_changed


# ---------------------------------------------------------------------------
# Role cache & serialization
# ---------------------------------------------------------------------------
async def refresh_user_role_cache(db: AsyncSession, user: User) -> None:
    """Cache the user's current role names (Redis) for fast lookups."""
    role_names = [r.name for r in user.roles] if user.roles else []
    if role_names:
        await set_cached_user_roles(user.id, role_names)
    else:
        await clear_cached_user_roles(user.id)


def serialize_user(user: User) -> UserPublic:
    """Public projection - never hashes/PINs (Rule R7)."""
    role_names = [r.name for r in user.roles] if user.roles else []
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=UserStatus(user.status),
        roles=role_names,
        permissions=sorted(permissions_for_roles(role_names)),
        is_active=user.is_active,
    )


# ---------------------------------------------------------------------------
# Session tracking (port of auth-service account/service.py)
# ---------------------------------------------------------------------------
def generate_token_id() -> str:
    return uuid4().hex


async def create_user_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    token_id: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> UserSession:
    session = UserSession(
        user_id=user_id,
        token_id=token_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    await db.flush()
    return session


async def revoke_user_session(db: AsyncSession, token_id: str) -> bool:
    """Mark a session revoked (commit is the caller's responsibility)."""
    result = await db.execute(
        select(UserSession).where(UserSession.token_id == token_id)
    )
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        return True
    return False


async def touch_session(db: AsyncSession, token_id: str) -> None:
    result = await db.execute(
        select(UserSession).where(UserSession.token_id == token_id)
    )
    session = result.scalar_one_or_none()
    if session is not None:
        session.last_seen_at = datetime.now(UTC)
        await db.commit()


async def list_active_sessions(
    db: AsyncSession, user_id: uuid.UUID
) -> list[UserSession]:
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_seen_at.desc())
    )
    return list(result.scalars().all())


async def revoke_user_session_by_id(
    db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
) -> bool:
    """Revoke a session by session UUID for a given user."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await blacklist_token(session.token_id)
        await db.commit()
        return True
    return False
