"""Call domain events (written to the outbox in the same tx, Rule R8).

The dispatcher worker translates these ``outbox.event_type`` values to Kafka
topics of the same name on the ``calls.events`` channel.  The event payload
always includes the ``reference`` field so consumers can log human-readable
identifiers without a lookup.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

CALLS_CHANNEL = "calls.events"
CALLS_AGGREGATE = "call"


class CallEventType(StrEnum):
    """Canonical event names for the calls domain."""

    OPENED = "call.opened"
    STATE_CHANGED = "call.state_changed"
    COMPLETED = "call.completed"
    DISPOSITION_CHANGED = "call.disposition_changed"
    QUALIFICATION_CHANGED = "call.qualification_changed"
    TRANSCRIPT = "call.transcript"


async def publish_call_event(
    session: AsyncSession,
    *,
    call_id: Any,
    reference: str,
    event_type: CallEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a call event to the outbox (same transaction as the write)."""
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(call_id),
        payload={"reference": reference, **(payload or {})},
        channel=CALLS_CHANNEL,
        aggregate_type=CALLS_AGGREGATE,
    )
