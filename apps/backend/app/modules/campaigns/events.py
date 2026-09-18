"""Campaign domain events (written to the outbox in the same tx, Rule R8).

The dispatcher worker translates these ``outbox.event_type`` values to Kafka
topics of the same name on the ``campaigns.events`` channel.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

CAMPAIGN_CHANNEL = "campaigns.events"
CAMPAIGN_AGGREGATE = "campaign"


class CampaignEventType(StrEnum):
    """Canonical event names for the campaigns domain."""

    CREATED = "campaign.created"
    UPDATED = "campaign.updated"
    STARTED = "campaign.started"
    PAUSED = "campaign.paused"
    STOPPED = "campaign.stopped"


async def publish_campaign_event(
    session: AsyncSession,
    *,
    campaign_id: Any,
    event_type: CampaignEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a campaign event to the outbox (same transaction as the write)."""
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(campaign_id),
        payload=payload or {},
        channel=CAMPAIGN_CHANNEL,
        aggregate_type=CAMPAIGN_AGGREGATE,
    )
