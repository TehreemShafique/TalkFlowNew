"""Telephony edge events (written to the outbox in the same tx, Rule R8)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

TELEPHONY_CHANNEL = "telephony.events"
TELEPHONY_AGGREGATE = "call"


class TelephonyEventType(StrEnum):
    """Canonical event names for the telephony edge."""

    START_CALL_RECEIVED = "telephony.start_call_received"
    DISPO_CALL_RECEIVED = "telephony.dispo_call_received"
    WEBHOOK_REPLAYED = "telephony.webhook_replayed"


async def publish_telephony_event(
    session: AsyncSession,
    *,
    call_id: Any,
    event_type: TelephonyEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a telephony edge event to the outbox (same tx as the write)."""
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(call_id),
        payload=payload or {},
        channel=TELEPHONY_CHANNEL,
        aggregate_type=TELEPHONY_AGGREGATE,
    )
