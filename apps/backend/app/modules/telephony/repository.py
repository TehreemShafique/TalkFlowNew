"""Call-log persistence for the telephony edge (Rule R3 - module-scoped reads).

The webhook maps an inbound start/dispo event onto the shared ``Call`` model
(``app.packages.db.models``).  Every persisted row keeps ``script_version_id``
and ``call_id`` (the UUID primary key) intact so later ingest never guesses
them; ``channel_id`` is unique per call (Rule 2 / idempotent open).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.telephony.schemas import DispoCallPayload, StartCallPayload
from app.packages.db.models import Call


def _now() -> datetime:
    return datetime.now(UTC)


async def ensure_call_started(
    session: AsyncSession, payload: StartCallPayload
) -> uuid.UUID:
    """Insert the call-open row for a start-call webhook.

    Uses ``INSERT ... ON CONFLICT (channel_id) DO NOTHING`` so a dialer that
    re-publishes the same channel across the idempotency window cannot open two
    calls.  Returns the (existing or new) call UUID.
    """
    call = Call(
        id=payload.call_id,
        lead_id=payload.lead_id,
        campaign_id=payload.campaign_id,
        script_version_id=payload.script_version_id,
        vicidial_call_id=payload.vicidial_call_id,
        vicidial_lead_id=payload.vicidial_lead_id,
        channel_id=payload.channel_id,
        caller_number=payload.caller_number,
        caller_state=payload.caller_state,
        did_used=payload.did_used,
        status="in_progress",
        direction="outbound",
        started_at=_now(),
    )
    stmt = pg_insert(Call).values(
        id=call.id,
        lead_id=call.lead_id,
        campaign_id=call.campaign_id,
        script_version_id=call.script_version_id,
        vicidial_call_id=call.vicidial_call_id,
        vicidial_lead_id=call.vicidial_lead_id,
        channel_id=call.channel_id,
        caller_number=call.caller_number,
        caller_state=call.caller_state,
        did_used=call.did_used,
        status=call.status,
        direction=call.direction,
        started_at=call.started_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Call.channel_id],
        set_={
            "vicidial_lead_id": call.vicidial_lead_id,
            "script_version_id": call.script_version_id,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return call.id


async def record_disposition(
    session: AsyncSession, payload: DispoCallPayload, vicidial_status: str | None
) -> uuid.UUID:
    """Stamp the dispo-call result onto the matching row (by call UUID)."""
    stmt = pg_insert(Call).values(
        id=payload.call_id,
        lead_id=payload.lead_id,
        campaign_id=payload.campaign_id,
        script_version_id=payload.script_version_id,
        vicidial_call_id=payload.vicidial_call_id,
        vicidial_lead_id=payload.vicidial_lead_id,
        channel_id=payload.channel_id,
        disposition=payload.outcome,
        vicidial_status=vicidial_status,
        status="completed",
        direction="outbound",
        started_at=_now(),
        ended_at=_now(),
        duration_seconds=payload.duration_seconds,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Call.id],
        set_={
            "disposition": payload.outcome,
            "vicidial_status": vicidial_status,
            "status": "completed",
            "ended_at": _now(),
            "duration_seconds": payload.duration_seconds,
            "script_version_id": payload.script_version_id,
            "vicidial_lead_id": payload.vicidial_lead_id,
        },
    )
    await session.execute(stmt)
    await session.flush()
    return payload.call_id
