"""Security primitives: Argon2id hashing, JWT access tokens, cookies, grants.

Rule R7 / blueprint section 11.4 - no raw secrets or internal paths are ever
serialized to a response model; grants handed to browsers are short-lived signed
tokens or presigned S3 URLs.

Password/pin hashing uses Argon2id via ``argon2-cffi`` (the control plane's
single hashing implementation - port of services/auth-service, which used
bcrypt, is intentionally NOT carried over; see TASK section 2.1).
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast
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
# Refresh tokens (blueprint 11.4 - opaque, hashed, httpOnly, rotated)
# ---------------------------------------------------------------------------
# The refresh cookie is SameSite=Strict per the blueprint.  It is exempt from
# CSRF concerns because it is only ever read by ``POST /auth/refresh``, which
# requires no ambient authority and returns a token rather than acting on one.
_REFRESH_SAMESITE = cast("Literal['strict', 'none']", "strict")


def generate_refresh_token() -> str:
    """Mint an opaque high-entropy refresh token (never a JWT)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex digest - the only representation persisted (blueprint 13.2).

    A fast digest is correct here: the token is 384 bits of CSPRNG output, so
    there is no brute-force surface, and lookups must stay indexable.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def set_refresh_cookie(response: Response, token: str) -> None:
    """Persist the refresh token in an HttpOnly, SameSite=Strict cookie."""
    response.set_cookie(
        key=settings.cookie_refresh_name,
        value=token,
        httponly=True,
        samesite=_REFRESH_SAMESITE,
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire and remove the refresh cookie."""
    response.delete_cookie(
        key=settings.cookie_refresh_name,
        httponly=True,
        samesite=_REFRESH_SAMESITE,
        secure=settings.cookie_secure,
        path="/",
    )


# ---------------------------------------------------------------------------
# Signed capability grants (playback / download)
# ---------------------------------------------------------------------------
def create_signed_grant(
    subject: str,
    *,
    purpose: str,
    ttl_seconds: int,
    claims: Mapping[str, Any] | None = None,
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
    if claims:
        payload.update(
            {key: value for key, value in claims.items() if key not in payload}
        )
    token = jwt.encode(
        payload, settings.jwt_access_secret, algorithm=settings.jwt_algorithm
    )
    return token, jti


def decode_signed_grant(token: str) -> dict:
    """Verify a signed capability grant."""
    payload = jwt.decode(
        token, settings.jwt_access_secret, algorithms=[settings.jwt_algorithm]
    )
    required = {"sub", "purpose", "jti", "exp"}
    if not required.issubset(payload):
        raise jwt.InvalidTokenError("incomplete capability grant")
    return payload


# ---------------------------------------------------------------------------
# PII / PHI masking
# ---------------------------------------------------------------------------
_NON_DIGITS = re.compile(r"\D+")

_PREFERRED_PHONE_MASK = "***-***-****"
_PREFERRED_MBI_MASK = "XXXX-XXXX-XXXX"

PHONE_MASKED = _PREFERRED_PHONE_MASK
MBI_MASKED = _PREFERRED_MBI_MASK
PHI_REDACTED = "[PROTECTED_HEALTH_INFO]"

PHONE_KEYS = frozenset(
    {
        "phone",
        "phone_number",
        "phone_normalized",
        "phone_raw",
        "caller_number",
        "caller_phone",
        "from",
        "to",
    }
)
MBI_KEYS = frozenset(
    {
        "mbi",
        "mbi_number",
        "medicare_beneficiary_id",
        "medicare_beneficiary_identifier",
        "beneficiary_id",
        "beneficiary_number",
    }
)
PHI_KEYS = frozenset(
    {
        "dob",
        "date_of_birth",
        "birth_date",
        "birthdate",
        "health",
        "health_status",
        "health_conditions",
        "conditions",
        "diagnosis",
        "diagnoses",
        "diagnosis_code",
        "icd10",
        "icd_code",
        "medication",
        "medications",
        "prescription",
        "prescriptions",
        "disability",
        "disability_status",
        "ssn",
        "social_security_number",
        "medicare_id",
        "member_id",
    }
)


def mask_phone_last_four(phone: str) -> str:
    """``***-***-1234`` - the area code and subscriber prefix are never kept."""
    if not phone:
        return _PREFERRED_PHONE_MASK
    digits = _NON_DIGITS.sub("", phone)
    if len(digits) < 4:
        return _PREFERRED_PHONE_MASK
    return f"***-***-{digits[-4:]}"


def mask_mbi_last_four(value: str) -> str:
    """``XXXX-XXXX-1234`` - Medicare Beneficiary Identifier last four only."""
    if not value:
        return _PREFERRED_MBI_MASK
    digits = _NON_DIGITS.sub("", value)
    if len(digits) < 4:
        return _PREFERRED_MBI_MASK
    return f"XXXX-XXXX-{digits[-4:]}"


def mask_phone(phone: str) -> str:
    """Mask a phone number, revealing only the final four digits.

    Single masking implementation for the whole control plane (dashboards,
    CSV exports, audit metadata, realtime fanout).
    """
    return mask_phone_last_four(phone)


def mask_mbi(value: str) -> str:
    return mask_mbi_last_four(value)


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def _mask_str_by_kind(norm_key: str, value: str) -> str:
    if norm_key in PHI_KEYS:
        return PHI_REDACTED
    if norm_key in MBI_KEYS:
        return mask_mbi_last_four(value)
    return mask_phone_last_four(value)


def mask_sensitive_payload(value: Any) -> Any:
    """Recursively redact PII/PHI in an event payload (dict / list / scalar)."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and isinstance(item, str) and item:
                norm = _norm_key(key)
                if norm in PHI_KEYS:
                    redacted[key] = PHI_REDACTED
                    continue
                if norm in MBI_KEYS:
                    redacted[key] = mask_mbi_last_four(item)
                    continue
                if norm in PHONE_KEYS or norm == "number":
                    redacted[key] = mask_phone_last_four(item)
                    continue
            redacted[key] = mask_sensitive_payload(item)
        return redacted
    if isinstance(value, list):
        return [mask_sensitive_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(mask_sensitive_payload(item) for item in value)
    return value
