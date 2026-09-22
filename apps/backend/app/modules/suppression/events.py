"""Suppression domain events (written to the outbox in the same tx, Rule R8).

Unlike the other modules the suppression channel is the VICIdial sync topic:
callers/predictive dialers consume these to drop DNC numbers from dial lists,
so ``add``/``remove`` events MUST be durable - hence outbox, not a fire-and-
forget Kafka publish.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

SUPPRESSION_CHANNEL = "talkflow.vicidial.sync.v1"
SUPPRESSION_AGGREGATE = "suppression_entry"


class SuppressionEventType(StrEnum):
    """Canonical event names for the suppression/DNC register."""

    ADDED = "suppression.added"
    REMOVED = "suppression.removed"
    IMPORTED = "suppression.imported"


async def publish_suppression_event(
    session: AsyncSession,
    *,
    entry_id: Any,
    event_type: SuppressionEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a suppression event to the outbox (same transaction as the write)."""
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(entry_id),
        payload=payload or {},
        channel=SUPPRESSION_CHANNEL,
        aggregate_type=SUPPRESSION_AGGREGATE,
    )
