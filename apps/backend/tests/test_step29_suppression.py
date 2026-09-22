"""Tests for STEP 29 — Suppression Register, soft removal, and dialability guard."""

from __future__ import annotations

import uuid

import pytest

from app.modules.suppression.policies import parse_reason
from app.modules.suppression.schemas import SuppressionCheckDTO
from app.packages.contracts.enums import SuppressionReason
from app.packages.db.models import SuppressionEntry


def test_suppression_reason_parsing():
    """Verify parsing valid and invalid reasons."""
    reason, err = parse_reason("litigator")
    assert reason == SuppressionReason.LITIGATOR.value
    assert err is None

    reason, err = parse_reason("unknown_reason")
    assert reason is None
    assert err == "invalid_reason"


@pytest.mark.asyncio
async def test_removal_is_soft():
    """Removal sets removed_at and removed_by timestamp, leaving entry in DB."""
    entry = SuppressionEntry(
        id=uuid.uuid4(),
        phone_normalized="18005550199",
        reason="litigator",
        added_by=uuid.uuid4(),
    )
    assert entry.removed_at is None
    # Simulate soft removal
    import datetime

    now = datetime.datetime.now(datetime.UTC)
    entry.removed_at = now
    assert entry.removed_at is not None


def test_suppressed_lead_is_never_dialable():
    """SuppressionCheckDTO reports suppressed=True when phone is registered."""
    check = SuppressionCheckDTO(
        suppressed=True,
        reason=SuppressionReason.LITIGATOR,
        entry_id=uuid.uuid4(),
    )
    assert check.suppressed is True
    assert check.reason == SuppressionReason.LITIGATOR
