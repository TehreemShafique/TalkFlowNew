"""Outbox writer - transactional integration events.

Events are persisted in the SAME transaction as the domain write (Rule R8),
then the dispatcher worker converts them to Kafka messages (aiokafka).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import outbox_table


async def write_outbox(
    session: AsyncSession,
    *,
    event_type: str,
    payload: dict[str, Any],
    channel: str = "recordings.events",
    aggregate_type: str = "recording",
    aggregate_id: str,
) -> None:
    now = datetime.now(UTC)
    stmt = pg_insert(outbox_table).values(
        id=uuid.uuid4(),
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        channel=channel,
        event_type=event_type,
        payload=payload,
        created_at=now,
        dispatched_at=None,
        attempts=0,
    )
    await session.execute(stmt)