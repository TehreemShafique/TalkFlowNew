"""Auth domain logic: password/PIN auth, token issue, session tracking, logout.

Port of services/auth-service/app/modules/auth/service.py + account/service.py
(merged: the control plane treats session tracking as part of the auth module).
Every mutating operation commits once at the end so the outbox event and the
state change are one transaction (Rule R8).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import permissions_for_roles
from app.core.redis import (
    blacklist_token,
    clear_cached_user_roles,
    set_cached_user_roles,
)
from app.core.security import (
    clear_access_token_cookie,
    clear_refresh_cookie,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    set_access_token_cookie,
    set_refresh_cookie,
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
from app.modules.auth.repository import get_user_by_email, get_user_by_id
from app.modules.auth.schemas import SignupRequest, UpdateProfileRequest, UserPublic
from app.packages.contracts.enums import UserStatus
from app.packages.contracts.errors import NotAuthenticatedError
from app.packages.db.models import RefreshToken, User, UserSession

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
    """Mint a JWT, record the UserSession, cache roles, bake the cookie.

    A short-lived access JWT (blueprint 11.4) is paired with an opaque refresh
    token; both are delivered as HttpOnly cookies so the browser holds no
    JavaScript-readable credential.
    """
    token_id = generate_token_id()
    access_token, _ = create_access_token({"sub": user.email, "jti": token_id})
    set_access_token_cookie(response, access_token)

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    await create_user_session(db, user.id, token_id, user_agent, ip_address)
    await issue_refresh_token(db, user.id, token_id, user_agent, ip_address, response)
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
    """Blacklist the jti, revoke the session, always clear the cookies."""
    clear_access_token_cookie(response)
    clear_refresh_cookie(response)
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
    await revoke_refresh_tokens_for_session(db, jti)
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
        # Killing the session must also kill its refresh lineage, otherwise the
        # browser could mint a fresh access token from a "revoked" login.
        await revoke_refresh_tokens_for_session(db, session.token_id)
        await db.commit()
        return True
    return False


# ---------------------------------------------------------------------------
# Refresh tokens (blueprint 11.4 / 13.2 - opaque, hashed, rotated, reuse-detected)
# ---------------------------------------------------------------------------
async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_token_id: str,
    user_agent: str | None,
    ip_address: str | None,
    response: Response,
    family_id: uuid.UUID | None = None,
) -> RefreshToken:
    """Mint, persist (hashed) and cookie a refresh token for a new family.

    ``family_id`` is supplied only when continuing an existing lineage during
    rotation; a fresh login always starts a new family.
    """
    raw_token = generate_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id or uuid4(),
        session_token_id=session_token_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        user_agent=user_agent,
        ip=ip_address,
    )
    db.add(record)
    await db.flush()
    set_refresh_cookie(response, raw_token)
    return record


async def revoke_refresh_tokens_for_session(
    db: AsyncSession, session_token_id: str
) -> int:
    """Revoke every live refresh token bound to one session jti."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.session_token_id == session_token_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    revoked = 0
    for record in result.scalars().all():
        record.revoked_at = now
        revoked += 1
    return revoked


async def revoke_token_family(db: AsyncSession, family_id: uuid.UUID) -> int:
    """Revoke every live token in a family - the reuse-detection response."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    revoked = 0
    for record in result.scalars().all():
        record.revoked_at = now
        revoked += 1
    return revoked


async def refresh_session(
    db: AsyncSession, request: Request, response: Response
) -> tuple[User, str]:
    """Rotate a refresh token and re-mint its access token.

    Returns ``(user, access_token)``.  Rotation keeps the session's original
    ``jti`` so ``core.dependencies.require_auth`` continues to resolve the same
    ``user_sessions`` row.  Presenting a token that was already rotated out is
    treated as compromise: the whole family is revoked before the 401.
    """
    presented = request.cookies.get(settings.cookie_refresh_name)
    if not presented:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Refresh token is missing."
        )

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(presented)
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Refresh token is not recognized."
        )

    now = datetime.now(UTC)
    if record.revoked_at is not None:
        await revoke_token_family(db, record.family_id)
        await publish_auth_event(
            db,
            user_id=record.user_id,
            event_type=AuthEventType.SESSION_REVOKED,
            metadata={
                "family_id": str(record.family_id),
                "reason": "refresh_token_reuse",
            },
        )
        await db.commit()
        raise NotAuthenticatedError(
            "auth.not_authenticated",
            message="Refresh token reuse detected; session family revoked.",
        )

    if record.expires_at <= now:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Refresh token has expired."
        )

    user = await get_user_by_id(db, record.user_id)
    if user is None:
        raise NotAuthenticatedError(
            "auth.not_authenticated", message="Refresh token owner no longer exists."
        )
    # A refresh must not outlive an account that was disabled or un-approved.
    ensure_login_allowed(user)

    successor = await issue_refresh_token(
        db,
        user.id,
        record.session_token_id,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
        response,
        family_id=record.family_id,
    )
    record.revoked_at = now
    record.replaced_by = successor.id

    access_token, _ = create_access_token(
        {"sub": user.email, "jti": record.session_token_id}
    )
    set_access_token_cookie(response, access_token)

    await publish_auth_event(
        db,
        user_id=user.id,
        event_type=AuthEventType.SESSION_REFRESHED,
        metadata={"family_id": str(record.family_id)},
    )
    await db.commit()
    await refresh_user_role_cache(db, user)
    return user, access_token
