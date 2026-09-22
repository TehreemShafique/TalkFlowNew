"""Tests for STEP 36 — Verifier Presence Expiry."""

from __future__ import annotations

import uuid

import pytest

from app.core.context import UserContext
from app.core.redis import get_redis
from app.modules.realtime.manager import ConnectionManager


async def is_available(verifier_id: uuid.UUID | str) -> bool:
    try:
        redis_client = get_redis()
        key = f"cp:verifier:{verifier_id}:availability"
        val = await redis_client.get(key)
        if val is not None:
            return True
    except Exception:  # noqa: BLE001, S110 - Redis fallback to in-memory presence
        pass
    from app.modules.realtime.manager import _IN_MEMORY_PRESENCE

    return _IN_MEMORY_PRESENCE.get(str(verifier_id)) == "available"


@pytest.mark.asyncio
async def test_closed_browser_becomes_unavailable():
    """Verifier presence key in Redis is deleted upon socket disconnect/close (Step 36)."""
    test_manager = ConnectionManager()
    verifier_id = uuid.uuid4()

    class MockSocket:
        async def send_text(self, data: str):
            pass

    mock_ws = MockSocket()
    session_id = await test_manager.register_socket(mock_ws)  # type: ignore[arg-type]

    verifier_user = UserContext(
        user_id=verifier_id,
        tenant_id=None,
        permissions={"verifier.workspace"},
        role="VERIFIER",
    )
    await test_manager.authenticate_session(session_id, verifier_user)

    # Verifier should be available
    assert await is_available(verifier_id) is True

    # Simulate hard close / disconnect
    await test_manager.unregister_socket(session_id)

    # Verifier availability key deleted
    assert await is_available(verifier_id) is False
