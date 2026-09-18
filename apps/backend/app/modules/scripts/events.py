"""Outbox domain event types and publisher for the scripts module."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox


class ScriptEventType(StrEnum):
    CREATED = "script.created"
    VERSION_CREATED = "script.version_created"
    SUBMITTED = "script.submitted"
    APPROVED = "script.approved"
    REJECTED = "script.rejected"
    ACTIVATED = "script.activated"
    ARCHIVED = "script.archived"


async def publish_script_event(
    session: AsyncSession,
    *,
    script_id: Any,
    event_type: ScriptEventType | str,
    payload: dict[str, Any],
) -> None:
    ev_type = event_type if isinstance(event_type, str) else event_type.value
    await write_outbox(
        session,
        event_type=ev_type,
        payload=payload,
        channel="scripts.events",
        aggregate_type="script",
        aggregate_id=str(script_id),
    )
