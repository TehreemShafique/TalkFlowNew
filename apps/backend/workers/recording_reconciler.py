"""5-minute recording reconciler worker (Step 37).

Finds completed calls with no ready or failed call_recording row and requeues
the fetch / creates a pending recording row to close the orphan gap.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.contracts.enums import RecordingStatus
from app.packages.db.models import Call, CallRecording

logger = structlog.get_logger("workers.recording_reconciler")


async def run_reconciler(session: AsyncSession) -> int:
    """Requeue missing recording fetches for completed calls older than 5 minutes."""
    cutoff = datetime.now(UTC) - timedelta(minutes=5)

    # Completed calls that do NOT have a ready/failed recording row
    stmt = (
        select(Call.id, Call.campaign_id, Call.lead_id)
        .where(
            Call.status.in_(["completed", "transferred"]),
            Call.ended_at <= cutoff,
            ~Call.id.in_(
                select(CallRecording.call_id).where(
                    CallRecording.status.in_(
                        [RecordingStatus.READY.value, RecordingStatus.FAILED.value]
                    )
                )
            ),
        )
        .limit(50)
    )

    res = await session.execute(stmt)
    rows = res.all()
    if not rows:
        return 0

    requeued_count = 0
    for row in rows:
        call_id, campaign_id, lead_id = row.id, row.campaign_id, row.lead_id
        # Check if pending row already exists
        rec_stmt = (
            select(CallRecording).where(CallRecording.call_id == call_id).limit(1)
        )
        rec = (await session.execute(rec_stmt)).scalar_one_or_none()

        if not rec:
            rec = CallRecording(
                id=uuid.uuid4(),
                call_id=call_id,
                campaign_id=campaign_id,
                lead_id=lead_id,
                status=RecordingStatus.PENDING.value,
                duration_seconds=0,
                storage_provider="local",
                created_at=datetime.now(UTC),
            )
            session.add(rec)
        else:
            rec.status = RecordingStatus.FETCHING.value

        requeued_count += 1

    await session.commit()
    logger.info("recording reconciler requeued calls", count=requeued_count)
    return requeued_count
