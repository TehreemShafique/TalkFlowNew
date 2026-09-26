"""Transport security: TLS version floor, HTTPS enforcement, storage TLS.

RP-27 - PHI (call audio, transcripts, Medicare identifiers) may only travel
over TLS 1.3+ and object storage endpoints must be HTTPS with server-side
encryption.  The helpers here are pure functions so they can be asserted in
tests without booting the app; ``TLSEnforcementMiddleware`` is the HTTP edge.
"""

from __future__ import annotations

import ipaddress
import urllib.parse
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

log = structlog.get_logger("core.tls")

TLS_VERSION_ORDER: dict[str, int] = {
    "TLSV1": 1,
    "TLSV1.1": 1,
    "TLSV1.2": 2,
    "TLSV1.3": 3,
}
_SUPPORTED_TLS = ("TLSv1.2", "TLSv1.3")
_LOOPBACK_HOSTS = frozenset({"localhost", "testserver", "test", "::1", "0.0.0.0"})
_TLS_QUERY_KEYS = ("ssl", "sslmode", "ssl-mode")


class TLSPolicyError(RuntimeError):
    """Raised when the configured transport posture is unsafe."""


def normalize_tls_version(version: str | None) -> str:
    if not version:
        return ""
    return version.strip().upper().replace(" ", "")


def is_tls_version_acceptable(version: str | None) -> bool:
    """True when ``version`` meets the configured minimum (default TLSv1.3)."""
    normalized = normalize_tls_version(version)
    if normalized not in TLS_VERSION_ORDER:
        return False
    minimum = normalize_tls_version(settings.tls_min_version) or "TLSV1.3"
    return TLS_VERSION_ORDER[normalized] >= TLS_VERSION_ORDER.get(minimum, 3)


def assert_tls_version(version: str | None) -> None:
    if not is_tls_version_acceptable(version):
        raise TLSPolicyError(
            f"negotiated TLS {version or 'unknown'} is below the required "
            f"{settings.tls_min_version} floor"
        )


def _host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def is_loopback_url(url: str) -> bool:
    host = _host_of(url)
    if not host:
        return False
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return True
    cleaned = host.strip().strip("[]").lower()
    if cleaned in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(cleaned).is_loopback
    except ValueError:
        return False


def database_tls_enabled(url: str | None = None) -> bool:
    """True when the DSN demands TLS (``ssl=require`` / ``sslmode=require``)."""
    dsn = (url or settings.database_url).lower()
    if not dsn.startswith(("postgres://", "postgresql://", "postgresql+")):
        return False
    for key in _TLS_QUERY_KEYS:
        for value in urllib.parse.parse_qs(
            urllib.parse.urlsplit(dsn).query, keep_blank_values=True
        ).get(key, []):
            if value in ("require", "verify-ca", "verify-full", "true", "1"):
                return True
    return False


def server_side_encryption_enabled() -> bool:
    algorithm = (settings.storage_s3_server_side_encryption or "").strip()
    if not algorithm:
        return False
    if algorithm in ("aws:kms", "aws:kms:dsse"):
        return bool(settings.storage_s3_kms_key_id)
    return True


def assert_encrypted_endpoint(url: str, *, label: str) -> None:
    """Reject plaintext object-storage endpoints outside local development."""
    if not url:
        return
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme in ("https", "wss"):
        return
    if scheme not in ("http", "ws") or not is_loopback_url(url):
        raise TLSPolicyError(f"{label} must use TLS (https), got {url!r}")


PRODUCTION_ENVS = frozenset({"production", "prod", "staging"})


def is_production(app_env: str | None = None) -> bool:
    return (app_env or settings.app_env).strip().lower() in PRODUCTION_ENVS


def validate_transport_security(*, strict: bool | None = None) -> None:
    """Startup posture check - never boot with PHI on a plaintext transport.

    ``strict`` defaults to "is this a production posture?".  Data-at-rest
    encryption is always required for S3/MinIO; transport warnings for a local
    development database are logged instead of raised.
    """
    strict_env = is_production() if strict is None else strict

    if settings.storage_provider in ("s3", "minio"):
        assert_encrypted_endpoint(
            settings.storage_s3_endpoint, label="storage endpoint"
        )
        if not server_side_encryption_enabled():
            raise TLSPolicyError(
                "S3/MinIO storage requires storage_s3_server_side_encryption "
                "(AES256 or aws:kms with a key id)"
            )

    if settings.database_require_tls and not database_tls_enabled():
        message = (
            "database_require_tls is enabled but DATABASE_URL does not enforce TLS"
        )
        if strict_env:
            raise TLSPolicyError(message)
        log.warning("security.tls_degraded", reason=message)

    if strict_env:
        assert_encrypted_endpoint(
            settings.storage_public_base_url, label="public base url"
        )
        if not settings.cookie_secure:
            raise TLSPolicyError("cookie_secure must be enabled in production")
        if not settings.enforce_https:
            raise TLSPolicyError("enforce_https must stay enabled in production")


def request_is_secure(request: Request) -> bool:
    """True when the request reached us over TLS (directly or via a proxy)."""
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() in ("https", "wss")
    return request.url.scheme.lower() in ("https", "wss")


def request_is_exempt(request: Request) -> bool:
    """Loopback callers (local dev proxy, in-process ASGI tests) skip the gate."""
    client = request.client
    if client is not None and is_loopback_host(client.host):
        return True
    return is_loopback_host(request.headers.get("host", "").split(":")[0] or None)


def websocket_is_secure(websocket: Any) -> bool:
    """True when the WebSocket handshake arrived over ``wss`` (or a TLS proxy)."""
    forwarded_proto = websocket.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip().lower() in ("https", "wss")
    return websocket.url.scheme.lower() == "wss"


def websocket_is_exempt(websocket: Any) -> bool:
    client = websocket.client
    if client is not None and is_loopback_host(client.host):
        return True
    return is_loopback_host(websocket.headers.get("host", "").split(":")[0] or None)


class TLSEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject plaintext HTTP for PHI-bearing traffic outside loopback."""

    async def dispatch(self, request: Request, call_next: Callable):
        if (
            settings.enforce_https
            and not request_is_secure(request)
            and not request_is_exempt(request)
        ):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "security.tls_required",
                        "message": (
                            f"TLS {settings.tls_min_version} is required for this endpoint."
                        ),
                        "status": status.HTTP_400_BAD_REQUEST,
                        "details": None,
                        "traceId": getattr(request.state, "trace_id", ""),
                    }
                },
            )
        return await call_next(request)
