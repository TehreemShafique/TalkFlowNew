"""Tests for STEP 34 — Live Transfers Engine & Offer Reservation Race."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.transfers.service import reserve_verifier_offer, watchdog
from app.packages.contracts.enums import TransferStatus
from app.packages.db.models import Transfer, outbox_table


@pytest.mark.asyncio
async def test_two_verifiers_one_offer():
    """Offer reservation race condition: only ONE verifier wins the offer (Step 34)."""
    verifier_a = f"ver_a_{uuid.uuid4().hex[:6]}"
    transfer_id = uuid.uuid4()

    # Two verifiers attempting to reserve the SAME offer simultaneously
    res_a, res_b = await asyncio.gather(
        reserve_verifier_offer(verifier_a, transfer_id, ring_timeout_seconds=10),
        reserve_verifier_offer(verifier_a, transfer_id, ring_timeout_seconds=10),
    )

    results = [res_a, res_b]
    # Exactly one True (winner) and one False (loser)
    assert results.count(True) == 1
    assert results.count(False) == 1


@pytest.mark.asyncio
async def test_watchdog_recovers_stuck_transfer(seeded):
    """Stuck transfer watchdog recovers ringing transfer exceeding timeout to failed_timeout (Step 34)."""
    transfer_id = uuid.uuid4()
    old_time = datetime.now(UTC) - timedelta(minutes=5)

    async with seeded["factory"]() as session:
        stuck = Transfer(
            id=transfer_id,
            status=TransferStatus.RINGING_VERIFIER.value,
            ring_timeout_seconds=20,
            initiated_at=old_time,
            created_at=old_time,
            updated_at=old_time,
        )
        session.add(stuck)
        await session.commit()

    # Run watchdog tick
    async with seeded["factory"]() as session:
        recovered = await watchdog.tick(session)
        assert recovered >= 1

    # Verify status changed to failed_timeout in DB
    async with seeded["factory"]() as session:
        updated = (
            await session.execute(select(Transfer).where(Transfer.id == transfer_id))
        ).scalar_one()
        assert updated.status == TransferStatus.FAILED_TIMEOUT.value
        assert updated.failure_reason == "ring_timeout_exceeded"

        # Verify outbox event emitted
        outbox_event = (
            (
                await session.execute(
                    select(outbox_table).where(
                        outbox_table.c.aggregate_id == str(transfer_id)
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        assert outbox_event is not None
        assert outbox_event["event_type"] == "transfer.failed_timeout"
