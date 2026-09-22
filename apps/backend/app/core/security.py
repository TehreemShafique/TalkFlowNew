"""Security primitives: Argon2id hashing, JWT access tokens, cookies, grants.

Rule R7 / blueprint section 11.4 - no raw secrets or internal paths are ever
serialized to a response model; grants handed to browsers are short-lived signed
tokens or presigned S3 URLs.

Password/pin hashing uses Argon2id via ``argon2-cffi`` (the control plane's
single hashing implementation - port of services/auth-service, which used
bcrypt, is intentionally NOT carried over; see TASK section 2.1).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Response

from app.core.config import settings

_PASSWORD_HASHER = PasswordHasher()

_SAMESITE = cast("Literal['lax', 'strict', 'none'] | None", settings.cookie_samesite)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Password / PIN hashing (Argon2id)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash a password or collaborator PIN with Argon2id."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password/PIN against its Argon2id hash.  Never raises."""
    try:
        return _PASSWORD_HASHER.verify(hashed_password, plain_password)
    except (
        VerifyMismatchError,
        InvalidHashError,
        AttributeError,
        TypeError,
        ValueError,
    ):
        return False


# ---------------------------------------------------------------------------
# Access-token JWT (sub = email, jti = session id)
# ---------------------------------------------------------------------------
def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> tuple[str, str]:
    """Mint a session JWT; returns ``(token, jti)`` (port of auth-service).

    ``data`` may already contain a ``jti`` (e.g. an admin kill-session); a
    fresh one is generated otherwise.  ``sub`` is the user's email - the JWT
    alone is not enough to authorize, the principal is always re-resolved
    against the DB by ``core.dependencies.require_auth``.
    """
    to_encode = {**data}
    expire = _utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    jti = to_encode.setdefault("jti", uuid4().hex)
    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return token, jti


def decode_access_token(token: str) -> dict:
    """Decode and verify a session JWT.  Raises jwt.PyJWTError on any failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# ---------------------------------------------------------------------------
# HTTP cookie helpers
# ---------------------------------------------------------------------------
def set_access_token_cookie(response: Response, token: str) -> None:
    """Persist the JWT in an HttpOnly, SameSite=Lax cookie for the browser."""
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite=_SAMESITE,
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    """Expire and remove the access_token cookie."""
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        samesite=_SAMESITE,
        secure=settings.cookie_secure,
        path="/",
    )


# ---------------------------------------------------------------------------
# Signed capability grants (playback / download)
# ---------------------------------------------------------------------------
def create_signed_grant(
    subject: str, *, purpose: str, ttl_seconds: int
) -> tuple[str, str]:
    """Mint a capability grant (playback/download) - returns (token, jti)."""
    jti = uuid4().hex
    now = _utcnow()
    payload = {
        "sub": str(subject),
        "purpose": purpose,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    token = jwt.encode(
        payload, settings.jwt_access_secret, algorithm=settings.jwt_algorithm
    )
    return token, jti


def decode_signed_grant(token: str) -> dict:
    """Verify a signed capability grant."""
    return jwt.decode(
        token, settings.jwt_access_secret, algorithms=[settings.jwt_algorithm]
    )


# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------
_NON_DIGITS = re.compile(r"\D+")

_PREFERRED_MASK = "(XXX) ***-XXXX"


def mask_phone(phone: str) -> str:
    """Mask a phone number, keeping the area code and the last four digits.

    Built for the dashboard's display format, e.g. ``(850) ***-4586``.  This is
    the *only* phone masking implementation in the control plane.
    """
    if not phone:
        return _PREFERRED_MASK
    digits = _NON_DIGITS.sub("", phone)
    if len(digits) < 4:
        return "***-" + digits if digits else "* masked *"
    last4 = digits[-4:]
    if len(digits) >= 10:
        area = digits[-10:-7]
        return f"({area}) ***-{last4}"
    return f"***-{last4}"
