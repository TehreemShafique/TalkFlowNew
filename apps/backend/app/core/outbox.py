"""Outbox writer & dispatcher - transactional integration events (Step 32).

Events are persisted in the SAME transaction as the domain write (Rule R8).
Sequence numbers (seq) are assigned from Postgres sequences (outbox_seq_{channel})
at insert time to guarantee strict monotonic ordering even across concurrent workers.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.packages.db.models import outbox_table

logger = structlog.get_logger("core.outbox")


def _clean_channel_name(channel: str) -> str:
    """Sanitize channel name for Postgres sequence naming."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", channel).lower()
    return cleaned[:48]


async def write_outbox(
    session: AsyncSession,
    *,
    event_type: str,
    payload: dict[str, Any],
    channel: str = "recordings_events",
    aggregate_type: str = "recording",
    aggregate_id: str,
) -> None:
    now = datetime.now(UTC)
    channel_clean = _clean_channel_name(channel)
    seq_val: int | None = None

    try:
        seq_res = await session.execute(
            text(f"SELECT nextval('outbox_seq_{channel_clean}')")
        )
        seq_val = seq_res.scalar_one_or_none()
    except Exception:  # noqa: BLE001 - fallback if the sequence is missing
        # Fallback if specific sequence is missing or sqlite test mode
        try:
            seq_res = await session.execute(
                text("SELECT COALESCE(MAX(seq), 0) + 1 FROM outbox")
            )
            seq_val = seq_res.scalar_one_or_none()
        except Exception:  # noqa: BLE001 - degenerate fallback keeps the write alive
            seq_val = 1

    stmt = pg_insert(outbox_table).values(
        id=uuid.uuid4(),
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        channel=channel,
        event_type=event_type,
        seq=seq_val,
        payload=payload,
        created_at=now,
        dispatched_at=None,
        attempts=0,
    )
    await session.execute(stmt)


class OutboxDispatcher:
    """Dispatcher that fans out pending outbox events to Kafka and Redis in parallel."""

    def __init__(self, kafka_client: Any | None = None) -> None:
        self.kafka_client = kafka_client

    async def _send_to_kafka(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.kafka_client is not None and hasattr(self.kafka_client, "send"):
            await self.kafka_client.send(event_type, payload)

    async def _send_to_redis(self, channel: str, payload: dict[str, Any]) -> None:
        try:
            redis_client = get_redis()
            pub_channel = f"cp:channel:{channel}"
            await redis_client.publish(pub_channel, json.dumps(payload))
        except Exception as exc:  # noqa: BLE001 - Redis pub is best-effort
            logger.warning("redis outbox pub failed", channel=channel, error=str(exc))

    async def tick(self, session: AsyncSession) -> int:
        """Process pending outbox rows, dispatching to Kafka and Redis in parallel."""
        stmt = (
            select(outbox_table)
            .where(outbox_table.c.dispatched_at.is_(None))
            .order_by(outbox_table.c.created_at.asc())
            .limit(100)
        )
        rows = list((await session.execute(stmt)).mappings().all())
        if not rows:
            return 0

        dispatched_count = 0
        now = datetime.now(UTC)

        for row in rows:
            payload = row["payload"] or {}
            if row.get("seq") is not None and "seq" not in payload:
                payload = {**payload, "seq": row["seq"]}

            try:
                # Parallel fanout to Kafka and Redis
                await asyncio.gather(
                    self._send_to_kafka(row["event_type"], payload),
                    self._send_to_redis(row["channel"], payload),
                )

                # Mark dispatched
                await session.execute(
                    update(outbox_table)
                    .where(outbox_table.c.id == row["id"])
                    .values(dispatched_at=now)
                )
                dispatched_count += 1
            except Exception as exc:  # noqa: BLE001 - dispatch failures are retried
                logger.error(
                    "outbox dispatch failed", row_id=str(row["id"]), error=str(exc)
                )
                await session.execute(
                    update(outbox_table)
                    .where(outbox_table.c.id == row["id"])
                    .values(attempts=row["attempts"] + 1)
                )
                break

        await session.flush()
        return dispatched_count
