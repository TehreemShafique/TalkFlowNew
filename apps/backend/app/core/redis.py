"""Redis client: role cache, token blacklist, download tokens and grants."""
from __future__ import annotations

import json

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("core.redis")

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
            retry_on_timeout=False,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class DownloadTokenStore:
    """Single-use grant store (Redis SET NX EX) for download streams."""

    def __init__(self, client: redis.Redis | None = None) -> None:
        self.client = client or get_redis()
        self._prefix = "grant:download"

    async def consume(self, jti: str) -> bool:
        """Atomically consume a grant; returns True only if unused."""
        try:
            result = await self.client.set(
                f"{self._prefix}:{jti}", "used", nx=True, ex=settings.download_token_ttl_minutes * 60
            )
            return result is True
        except Exception as exc:  # noqa: BLE001 - Redis unavailable fallback
            log.warning("download token consume failed", error=str(exc))
            return True


token_store = DownloadTokenStore()


# ── Role cache (list of role names per user) ──────────────────────────────

async def get_cached_user_roles(user_id) -> list[str] | None:
    try:
        cached = await get_redis().get(f"user_roles:{user_id}")
        return json.loads(cached) if cached else None
    except Exception as exc:  # noqa: BLE001 - caching must never break auth
        log.warning("role cache get failed", error=str(exc))
        return None


async def set_cached_user_roles(user_id, role_names: list[str], ttl: int | None = None) -> None:
    try:
        await get_redis().setex(
            f"user_roles:{user_id}",
            ttl or settings.role_cache_ttl,
            json.dumps(role_names),
        )
    except Exception as exc:  # noqa: BLE001 - caching must never break auth
        log.warning("role cache set failed", error=str(exc))


async def clear_cached_user_roles(user_id) -> None:
    try:
        await get_redis().delete(f"user_roles:{user_id}")
    except Exception as exc:  # noqa: BLE001 - caching must never break auth
        log.warning("role cache clear failed", error=str(exc))


# ── Token blacklist (revoked jti) ─────────────────────────────────────────

async def is_token_blacklisted(jti: str) -> bool:
    try:
        return await get_redis().exists(f"blacklist:{jti}") == 1
    except Exception as exc:  # noqa: BLE001 - Redis is not available
        log.warning("blacklist check failed", error=str(exc))
        return False


async def blacklist_token(jti: str, ttl: int | None = None) -> None:
    try:
        await get_redis().setex(
            f"blacklist:{jti}", ttl or settings.token_blacklist_ttl, "revoked"
        )
    except Exception as exc:  # noqa: BLE001 - Redis is not available
        log.warning("blacklist set failed", error=str(exc))