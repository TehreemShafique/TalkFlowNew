"""Export domain events (written to the outbox in the same tx, Rule R8).

Consumers watch ``export.completed.failed`` to push download-ready notifications
or trigger the analytics pipeline for the requested report.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import write_outbox

EXPORTS_CHANNEL = "exports.events"
EXPORT_AGGREGATE = "export_job"


class ExportEventType(StrEnum):
    """Canonical event names for the export pipeline."""

    REQUESTED = "export.requested"
    COMPLETED = "export.completed"
    FAILED = "export.failed"


async def publish_export_event(
    session: AsyncSession,
    *,
    job_id: Any,
    event_type: ExportEventType,
    payload: dict[str, Any] | None = None,
) -> None:
    await write_outbox(
        session,
        event_type=event_type.value,
        aggregate_id=str(job_id),
        payload=payload or {},
        channel=EXPORTS_CHANNEL,
        aggregate_type=EXPORT_AGGREGATE,
    )
