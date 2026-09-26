"""Idempotency guards for external webhooks (BACKEND-8a).

External systems (VICIdial) retry acknowledged requests; without a guard a
duplicate ``start-call`` / ``dispo-call`` webhook would create duplicate call
logs.  The guard uses a Redis ``SET NX EX`` key - the atomic check-and-acquire
means two racing requests for the same ``(lead_id, call_id)`` can only ever
produce one processing pass.

Key layout: ``idempotency:vicidial_webhook:{lead_id}:{call_id}`` for VICIdial
webhooks.
Requests whose Redis write fails (Redis down) degrade to a 24h in-DB memory map
so the guard still holds within a single process.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.core.redis import get_redis

log = get_logger("core.idempotency")

# The spec'd lock lifetime is 24 hours: VICIdial replays a webhook within the
# same business day at most; anything older is a genuinely new call.
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

_VICIDIAL_PREFIX = "idempotency:vicidial_webhook"


def build_vicidial_key(lead_id: str | int, call_id: str | int) -> str:
    """Return the Redis key guarding one VICIdial ``(lead, call)`` pair."""
    return f"{_VICIDIAL_PREFIX}:{lead_id}:{call_id}"


class InProcessIdempotencyMap:
    """Process-local fallback used when Redis is unavailable.

    Not shared across workers - it only buys the guarantee while a Redis outage
    lasts, and entries expire after the same 24h window.
    """

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._seen: dict[str, float] = {}

    def is_new(self, key: str) -> bool:
        now = time.monotonic()
        expired = [k for k, ts in self._seen.items() if now - ts > self._ttl]
        for k in expired:
            self._seen.pop(k, None)
        if key in self._seen:
            return False
        self._seen[key] = now
        return True


class VicidialIdempotencyGuard:
    """Atomic idempotency guard for VICIdial webhook processing."""

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._fallback = InProcessIdempotencyMap(ttl_seconds)

    async def try_acquire(
        self,
        lead_id: str | int,
        call_id: str | int,
        *,
        client: Any = None,
    ) -> bool:
        """Atomically claim ``(lead_id, call_id)``.

        Returns ``True`` for the first (winning) request, ``False`` for every
        duplicate - duplicates MUST be ignored by the caller.  ``client`` is
        injectable for tests; it defaults to the shared Redis client.
        """
        key = build_vicidial_key(lead_id, call_id)
        redis_client = client or get_redis()
        try:
            result = await redis_client.set(key, "processing", nx=True, ex=self._ttl)
            return result is True
        except Exception as exc:  # noqa: BLE001 - Redis outage falls back locally
            log.warning(
                "redis unavailable; using local idempotency map", error=str(exc)
            )
            return self._fallback.is_new(key)


def get_vicidial_idempotency_guard() -> VicidialIdempotencyGuard:
    """Return a singleton guard (cached module-level instance)."""
    return VicidialIdempotencyGuard()
