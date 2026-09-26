"""Lead domain events (written to the outbox in the same tx, Rule R8).

The import wizard emits ``lead.import.*`` events so the analytics/feeds
consumers can react to batches as they land; a worker translates these
outbox rows onto the ``leads.events`` channel.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

LEADS_CHANNEL = "leads.events"
LEAD_AGGREGATE = "lead"
IMPORT_JOB_AGGREGATE = "lead_import_job"


class LeadEventType(StrEnum):
    """Canonical event names for the leads domain."""

    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    IMPORT_UPLOADED = "lead.import.uploaded"
    IMPORT_MAPPING_SAVED = "lead.import.mapping_saved"
    IMPORT_COMMITTED = "lead.import.committed"
    VICIDIAL_RUN_STARTED = "lead.vicidial.run_started"
    VICIDIAL_RUN_STOPPED = "lead.vicidial.run_stopped"


async def publish_lead_event(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: Any,
    event_type: LeadEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a lead-domain event to the outbox (same transaction as the write)."""
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(aggregate_id),
        payload=payload or {},
        channel=LEADS_CHANNEL,
        aggregate_type=aggregate_type,
    )
