"""Tests for STEP 33 — Realtime API & WebSocket Fanout."""

from __future__ import annotations

import uuid

import pytest

from app.core.context import UserContext
from app.modules.realtime.manager import ConnectionManager


@pytest.mark.asyncio
async def test_verifier_cannot_subscribe_to_calls_live():
    """VERIFIER role is forbidden from subscribing to calls.live (Step 33)."""
    test_manager = ConnectionManager()

    class MockSocket:
        async def send_text(self, data: str):
            pass

    mock_ws = MockSocket()
    session_id = await test_manager.register_socket(mock_ws)  # type: ignore[arg-type]

    verifier_user = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=None,
        permissions={"verifier.workspace"},
        role="VERIFIER",
    )
    await test_manager.authenticate_session(session_id, verifier_user)

    allowed, forbidden = await test_manager.subscribe_channels(
        session_id, ["dashboard", "calls.live"]
    )
    assert "calls.live" in forbidden
    assert "calls.live" not in allowed
    assert "dashboard" in allowed


@pytest.mark.asyncio
async def test_fanout_masks_pii_per_subscriber():
    """Fanout masks PII (caller.number) for non-admin subscribers lacking PII permission (Step 33)."""
    test_manager = ConnectionManager()

    admin_user = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=None,
        permissions={"lead.view", "lead.view_full"},
        role="MASTER_ADMIN",
    )
    reporting_user = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=None,
        permissions={"export.create"},
        role="REPORTING_USER",
    )

    masked_admin = test_manager._mask_payload_pii(
        {"caller": {"number": "+13125551234"}, "campaign": "Medicare"}, admin_user
    )
    masked_reporting = test_manager._mask_payload_pii(
        {"caller": {"number": "+13125551234"}, "campaign": "Medicare"}, reporting_user
    )

    assert masked_admin["caller"]["number"] == "+13125551234"
    assert "(312) ***-1234" in masked_reporting["caller"]["number"]
