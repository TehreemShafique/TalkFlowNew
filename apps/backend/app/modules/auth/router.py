"""HTTP surface for the auth module (/api/v1/auth).

Wire format matches the migrated auth-service exactly: login/pin-login return
the token + user as a bare object (the dashboard reads `.accessToken` at the
top level), the session is carried in the HttpOnly ``access_token`` cookie, and
GET/PATCH /me operate on the authenticated principal (Rule R5).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_auth
from app.core.security import create_access_token, set_access_token_cookie
from app.modules.auth import service
from app.modules.auth.errors import AccountPendingError, InvalidCredentialsError
from app.modules.auth.repository import get_user_by_email, get_user_by_id
from app.modules.auth.schemas import (
    LoginRequest,
    MessageResponse,
    PinLoginRequest,
    ProfileUpdateResponse,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserPublic,
    UserSessionDTO,
)
from app.packages.contracts.base import DataResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_security_scheme = HTTPBearer(auto_error=False)

Db = Depends(get_db)
Auth = Depends(require_auth)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Db,
):
    user = await service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise InvalidCredentialsError()
    service.ensure_login_allowed(user)
    access_token = await service.issue_user_token(db, user, request, response)
    fresh = await get_user_by_email(db, user.email)
    return TokenResponse(
        access_token=access_token, user=service.serialize_user(fresh or user)
    )


@router.post("/pin-login", response_model=TokenResponse)
async def pin_login(
    payload: PinLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Db,
):
    user = await service.authenticate_pin(db, payload.email, payload.collaborator_pin)
    if user is None:
        raise InvalidCredentialsError()
    service.ensure_login_allowed(user)
    access_token = await service.issue_user_token(db, user, request, response)
    fresh = await get_user_by_email(db, user.email)
    return TokenResponse(
        access_token=access_token, user=service.serialize_user(fresh or user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Db,
):
    """Rotate the HttpOnly refresh cookie and re-issue the access token.

    Requires no ambient authority: the refresh cookie is the credential and the
    response is a token rather than an action on a resource.
    """
    user, access_token = await service.refresh_session(db, request, response)
    fresh = await get_user_by_id(db, user.id)
    return TokenResponse(
        access_token=access_token, user=service.serialize_user(fresh or user)
    )


@router.post(
    "/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
async def signup(payload: SignupRequest, db: AsyncSession = Db):
    await service.signup_user(db, payload)
    return MessageResponse(
        message="Account created successfully! Your request has been sent to the administrators for approval."
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_security_scheme)
    ] = None,
    db: AsyncSession = Db,
):
    token: str | None = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        token = request.cookies.get(settings.cookie_name)
    # Always clear the cookie - the session ends even if the token already
    # expired (which would otherwise fail the auth dependency).
    await service.logout_user(db, token, response)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserPublic)
async def get_profile(
    current_user=Auth,
    db: AsyncSession = Db,
):
    user = await get_user_by_id(db, current_user.user_id)
    if user is None:
        raise AccountPendingError()  # pragma: no cover - require_auth already resolved
    await service.refresh_user_role_cache(db, user)
    return service.serialize_user(user)


@router.patch("/me", response_model=ProfileUpdateResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    response: Response,
    current_user=Auth,
    db: AsyncSession = Db,
):
    user = await get_user_by_id(db, current_user.user_id)
    if user is None:  # pragma: no cover - require_auth already resolved
        raise AccountPendingError()

    fresh, email_changed = await service.update_user_profile(db, user, payload)
    if email_changed:
        # Re-issue so the JWT's ``sub`` (the old email) keeps resolving.  The
        # session jti is reused deliberately: a fresh jti would have no
        # ``user_sessions`` row and the very next request would 401.
        access_token, _ = create_access_token(
            {"sub": fresh.email, "jti": current_user.session_token_id}
        )
        set_access_token_cookie(response, access_token)
        await service.refresh_user_role_cache(db, fresh)
        return ProfileUpdateResponse(
            access_token=access_token, user=service.serialize_user(fresh)
        )

    await service.refresh_user_role_cache(db, fresh)
    return ProfileUpdateResponse(user=service.serialize_user(fresh))


account_router = APIRouter(prefix="/account", tags=["account"])


@router.get("/sessions", response_model=DataResponse[list[UserSessionDTO]])
@account_router.get(
    "/security/sessions", response_model=DataResponse[list[UserSessionDTO]]
)
async def list_security_sessions(
    current_user=Auth,
    db: AsyncSession = Db,
):
    """List active login sessions for the authenticated user."""
    sessions = await service.list_active_sessions(db, current_user.user_id)
    return DataResponse(
        data=[
            UserSessionDTO(
                id=s.id,
                user_id=s.user_id,
                token_id=s.token_id,
                user_agent=s.user_agent,
                ip_address=s.ip_address,
                last_seen_at=s.last_seen_at,
                revoked_at=s.revoked_at,
            )
            for s in sessions
        ]
    )


@router.post("/sessions/{session_id}/revoke", response_model=MessageResponse)
@account_router.post(
    "/security/sessions/{session_id}/revoke", response_model=MessageResponse
)
async def revoke_security_session(
    session_id: uuid.UUID,
    current_user=Auth,
    db: AsyncSession = Db,
):
    """Revoke a target login session by ID."""
    revoked = await service.revoke_user_session_by_id(
        db, current_user.user_id, session_id
    )
    if not revoked:
        return MessageResponse(message="Session already revoked or not found.")
    return MessageResponse(message="Session revoked successfully.")
