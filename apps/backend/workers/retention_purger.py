"""Daily retention purger worker (Step 38).

Deletes audio object from storage, sets status='purged' and audio_purged_at,
preserves the metadata row in call_recordings, and writes recording.purged audit log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.packages.contracts.enums import AuditResult, RecordingStatus
from app.packages.db.models import CallRecording
from app.packages.storage.provider import get_storage_provider

logger = structlog.get_logger("workers.retention_purger")


async def run_retention_purger(session: AsyncSession) -> int:
    """Purge expired recording audio files while preserving metadata rows (Step 38)."""
    now = datetime.now(UTC)

    # Find READY recordings whose expires_at has passed or audio retention cutoff reached
    stmt = select(CallRecording).where(
        CallRecording.status == RecordingStatus.READY.value,
        CallRecording.expires_at.is_not(None),
        CallRecording.expires_at <= now,
    ).limit(100)

    res = await session.execute(stmt)
    recordings = res.scalars().all()
    if not recordings:
        return 0

    provider = get_storage_provider()
    purged_count = 0

    for rec in recordings:
        if rec.storage_key:
            try:
                await provider.delete(rec.storage_key)
            except Exception as exc:
                logger.warning("failed deleting audio file during purge", recording_id=str(rec.id), error=str(exc))

        # Preserve metadata row; update status & audio_purged_at
        rec.status = RecordingStatus.PURGED.value
        rec.audio_purged_at = now

        # Write audit log (Step 38 requirement)
        await write_audit(
            session,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            actor_role="SYSTEM",
            action="recording.purged",
            resource_type="recording",
            resource_id=str(rec.id),
            result=AuditResult.SUCCESS,
            details={"reason": "retention.expired", "storage_key": rec.storage_key},
        )
        purged_count += 1

    await session.commit()
    logger.info("retention purger completed", purged_count=purged_count)
    return purged_count
