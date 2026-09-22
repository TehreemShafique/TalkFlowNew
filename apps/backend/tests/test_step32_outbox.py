"""Tests for STEP 32 — Transactional Outbox & Monotonic Sequence Dispatcher."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.core.outbox import OutboxDispatcher, write_outbox
from app.packages.contracts.errors import register_error
from app.packages.db.models import outbox_table

register_error("test.simulated_failure", 500, "Simulated failure for testing.")


class SimulatedError(AppError):
    def __init__(self) -> None:
        super().__init__("test.simulated_failure")


@pytest.mark.asyncio
async def test_rollback_drops_the_event(seeded):
    """When a transaction fails and rolls back, outbox event MUST be dropped (Step 32)."""
    async with seeded["factory"]() as session:
        try:
            await write_outbox(
                session,
                event_type="test.event",
                payload={"data": 1},
                channel="dashboard",
                aggregate_type="test",
                aggregate_id=str(uuid.uuid4()),
            )
            # Simulate failure and rollback
            raise SimulatedError()
        except AppError:
            await session.rollback()

        count = (
            await session.execute(
                select(func.count())
                .select_from(outbox_table)
                .where(outbox_table.c.event_type == "test.event")
            )
        ).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_dispatcher_replays_after_outage(seeded):
    """Outbox dispatcher retries pending rows until success, setting dispatched_at (Step 32)."""
    event_id = str(uuid.uuid4())
    async with seeded["factory"]() as session:
        await write_outbox(
            session,
            event_type="call.started",
            payload={"callId": event_id},
            channel="calls_live",
            aggregate_type="call",
            aggregate_id=event_id,
        )
        await session.commit()

    class MockFailingKafka:
        def __init__(self, failing: bool = True):
            self.failing = failing

        async def send(self, event_type, payload):
            if self.failing:
                raise RuntimeError("Kafka down")

    # 1. Dispatch while Kafka is down -> fails, dispatched_at stays None
    failing_kafka = MockFailingKafka(failing=True)
    dispatcher = OutboxDispatcher(kafka_client=failing_kafka)

    async with seeded["factory"]() as session:
        dispatched = await dispatcher.tick(session)
        await session.commit()
        assert dispatched == 0

        pending_row = (
            (
                await session.execute(
                    select(outbox_table).where(outbox_table.c.aggregate_id == event_id)
                )
            )
            .mappings()
            .one()
        )
        assert pending_row["dispatched_at"] is None

    # 2. Restore Kafka -> succeeds on next tick
    failing_kafka.failing = False
    async with seeded["factory"]() as session:
        dispatched = await dispatcher.tick(session)
        await session.commit()
        assert dispatched == 1

        success_row = (
            (
                await session.execute(
                    select(outbox_table).where(outbox_table.c.aggregate_id == event_id)
                )
            )
            .mappings()
            .one()
        )
        assert success_row["dispatched_at"] is not None


@pytest.mark.asyncio
async def test_seq_is_monotonic_under_concurrency(seeded):
    """Sequences written under concurrency MUST be monotonic (Step 32)."""
    async with seeded["factory"]() as session:

        async def emit(i: int):
            async with seeded["factory"]() as s:
                await write_outbox(
                    s,
                    event_type="test.concurrent",
                    payload={"index": i},
                    channel="dashboard",
                    aggregate_type="test",
                    aggregate_id=str(uuid.uuid4()),
                )
                await s.commit()

        await asyncio.gather(*[emit(i) for i in range(20)])

        rows = list(
            (
                await session.execute(
                    select(outbox_table.c.seq)
                    .where(outbox_table.c.event_type == "test.concurrent")
                    .order_by(outbox_table.c.created_at.asc(), outbox_table.c.seq.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 20
        # Check non-null and monotonic
        seqs = [r for r in rows if r is not None]
        assert len(seqs) == 20
        assert seqs == sorted(seqs)
