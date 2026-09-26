"""Telephony edge service: idempotency-gated webhook processing (BACKEND-8a).

Each webhook handler performs the same two-step dance:

1.  atomically claim ``(lead_id, call_id)`` through the idempotency guard;
2.  only the winning request touches the database (Rule R8 - no duplicate rows),
    duplicates return ``ignored_duplicate: true``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.idempotency import VicidialIdempotencyGuard
from app.modules.telephony import repository
from app.modules.telephony.events import (
    TelephonyEventType,
    publish_telephony_event,
)
from app.modules.telephony.schemas import (
    DispoCallPayload,
    StartCallPayload,
    WebhookResult,
)
from app.packages.vicidial.mapper import (
    map_outcome_safe,
    map_talkflow_to_vicidial_status,
)

_REPLAYED = "ignored_duplicate"


async def process_start_call(
    session: AsyncSession,
    payload: StartCallPayload,
    idempotency_client: Any = None,
    idempotency_guard: VicidialIdempotencyGuard | None = None,
) -> WebhookResult:
    """Receive a dialer ``start-call`` webhook and persist the call-open row."""
    guard = idempotency_guard or VicidialIdempotencyGuard()
    request_id = uuid.uuid4()

    if not await guard.try_acquire(
        payload.lead_id, payload.call_id, client=idempotency_client
    ):
        return WebhookResult(
            request_id=str(request_id),
            status=_REPLAYED,
            ignored_duplicate=True,
        )

    call_id = await repository.ensure_call_started(session, payload)
    await publish_telephony_event(
        session,
        call_id=call_id,
        event_type=TelephonyEventType.START_CALL_RECEIVED,
        payload={"requestId": str(request_id), "leadId": str(payload.lead_id)},
    )
    await session.commit()
    return WebhookResult(request_id=str(request_id), status="processed")


async def process_dispo_call(
    session: AsyncSession,
    payload: DispoCallPayload,
    idempotency_client: Any = None,
    idempotency_guard: VicidialIdempotencyGuard | None = None,
) -> WebhookResult:
    """Receive a dialer ``dispo-call`` webhook and stamp the disposition."""
    guard = idempotency_guard or VicidialIdempotencyGuard()
    request_id = uuid.uuid4()

    if not await guard.try_acquire(
        payload.lead_id, payload.call_id, client=idempotency_client
    ):
        return WebhookResult(
            request_id=str(request_id),
            status=_REPLAYED,
            ignored_duplicate=True,
        )

    vicidial_status = None
    if payload.outcome:
        try:
            vicidial_status = map_talkflow_to_vicidial_status(payload.outcome)
        except KeyError:
            # Keep the raw outcome for the control plane; the dialer simply is
            # not told about dispositions we do not model upstream.
            vicidial_status = map_outcome_safe(payload.outcome)

    call_id = await repository.record_disposition(session, payload, vicidial_status)
    await publish_telephony_event(
        session,
        call_id=call_id,
        event_type=TelephonyEventType.DISPO_CALL_RECEIVED,
        payload={
            "requestId": str(request_id),
            "leadId": str(payload.lead_id),
            "outcome": payload.outcome,
            "vicidialStatus": vicidial_status,
        },
    )
    await session.commit()
    return WebhookResult(request_id=str(request_id), status="processed")
