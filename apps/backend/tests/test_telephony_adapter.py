"""Tests for STEP 31 — Telephony Adapter Seam."""

from __future__ import annotations

import pytest

from app.packages.telephony import (
    ExternalLeadRef,
    ManualDialAdapter,
    TelephonyAdapter,
    TelephonyLead,
    build_adapter,
)


@pytest.mark.asyncio
async def test_manual_dial_adapter_returns_external_lead_ref():
    """ManualDialAdapter logs dial request and returns ExternalLeadRef with system='manual'."""
    adapter = build_adapter("manual")
    assert isinstance(adapter, TelephonyAdapter)
    assert isinstance(adapter, ManualDialAdapter)

    lead = TelephonyLead(
        id="lead-123",
        phone_normalized="18005550100",
        external_key="vk_test123456",
        first_name="Jane",
        last_name="Doe",
    )
    ref = await adapter.dial(lead)
    assert isinstance(ref, ExternalLeadRef)
    assert ref.system == "manual"
    assert ref.external_id == "vk_test123456"

    hung_up = await adapter.hangup("call-456")
    assert hung_up is True
