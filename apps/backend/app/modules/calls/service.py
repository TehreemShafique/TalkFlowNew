"""Call service - query orchestration + disposition lifecycle (Rule R8).

Every mutation writes its ``audit_log`` row and its outbox event in the **same
transaction** as the state change, and the pure disposition/qualification
policies (``policies.py``) decide every business rule without any I/O.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.modules.calls import policies
from app.modules.calls import repository as repo
from app.modules.calls.errors import CallInvalidStateError, CallNotFoundError
from app.modules.calls.events import CallEventType, publish_call_event
from app.modules.calls.schemas import (
    CallDTO,
    CallerInfoDTO,
    CallListQuery,
    ConsentEvidenceDTO,
    DispositionUpdate,
    LiveCallDTO,
    PerformanceDTO,
    QualificationDTO,
    QualificationFieldDTO,
    ScriptPathNodeDTO,
    TimelineEventDTO,
    TranscriptTurnDTO,
    TransferRecordDTO,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import (
    AuditResult,
    CallDirection,
    CallStatus,
    QualificationStatus,
)
from app.packages.db.models import Call

logger = structlog.get_logger("calls.service")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _qualification_from_call(call: Call) -> QualificationDTO:
    if not call.qualification_status:
        return QualificationDTO(status=QualificationStatus.PENDING.value)
    return QualificationDTO(
        status=call.qualification_status,
        disqualification_reason=call.disqualification_reason,
    )


def _consent_from_call(call: Call) -> ConsentEvidenceDTO:
    """Best-effort consent evidence until the compliance-events module lands.

    A call that reached a conversation (has talk time) implies recorded-consent
    capture was attempted; the authoritative consent artifact table belongs to
    the compliance module and will replace this heuristic.
    """
    return ConsentEvidenceDTO(
        captured=bool(call.talk_time_seconds or call.duration_seconds)
    )


def _transfer_from_call(call: Call, verifier_name: str | None) -> TransferRecordDTO:
    return TransferRecordDTO(
        status=call.transfer_status or "not_applicable",
        verifier_id=call.verifier_id,
        verifier_name=verifier_name,
    )


def _dto_from_row(
    row: dict,
    user: UserContext,
    *,
    include_verifier: bool = False,
) -> CallDTO:
    call = row["call"]
    caller_number = call.caller_number or None
    sees_full_pii = policies.CallPolicy.sees_full_pii(user)
    return CallDTO(
        id=call.id,
        reference=call.reference or str(call.id),
        direction=CallDirection(call.direction or CallDirection.OUTBOUND.value),
        status=CallStatus(call.status or CallStatus.QUEUED.value),
        disposition=call.disposition,
        lead_id=call.lead_id,
        lead_name=row.get("lead_name"),
        campaign_id=call.campaign_id,
        campaign_name=row.get("campaign_name"),
        script_id=call.script_id,
        script_version_id=call.script_version_id,
        rule_set_version_id=call.rule_set_version_id,
        channel_id=call.channel_id,
        vicidial_call_id=call.vicidial_call_id,
        vicidial_lead_id=call.vicidial_lead_id,
        vicidial_list_id=call.vicidial_list_id,
        vicidial_status=call.vicidial_status,
        caller=CallerInfoDTO(
            number=caller_number if sees_full_pii else None,
            masked=policies.CallPolicy.masked_phone(caller_number, user),
            state=call.caller_state,
        ),
        did_used=call.did_used,
        caller_id_used=call.caller_id_used,
        agent_alias_used=call.agent_alias_used,
        attempt_number=call.attempt_number or 1,
        started_at=call.started_at,
        answered_at=call.answered_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        talk_time_seconds=call.talk_time_seconds,
        qualification=_qualification_from_call(call),
        consent=_consent_from_call(call),
        transfer=_transfer_from_call(
            call,
            row.get("verifier_name")
            if include_verifier
            else None,
        ),
        qa_status=call.qa_status,
        qa_score=call.qa_score,
        created_at=call.created_at,
        updated_at=call.updated_at,
    )


async def _load(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> dict:
    row = await repo.get_call(
        session, call_id, policies.resolve_scope_constraints(user)
    )
    if row is None:
        raise CallNotFoundError()
    return row


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_calls(
    session: AsyncSession,
    user: UserContext,
    query: CallListQuery,
) -> PagedResponse[CallDTO]:
    rows, total = await repo.list_calls(
        session, query, policies.resolve_scope_constraints(user)
    )
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[CallDTO](
        data=[_dto_from_row(r, user) for r in rows],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            sort=query.sort,
            order=query.order,
        ),
    )


async def get_call(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[CallDTO]:
    """Call detail: row + qualification fields + verifier name (section 26)."""
    row = await _load(session, user, call_id)
    call = row["call"]
    if call.verifier_id:
        row["verifier_name"] = await repo.get_user_name(session, call.verifier_id)

    field_rows = await repo.get_qualification_fields(
        session, call.id, policies.resolve_scope_constraints(user)
    )
    dto = _dto_from_row(
        row,
        user,
        include_verifier=True,
    )
    dto.qualification.fields = [
        QualificationFieldDTO(
            field=f.field,
            label=f.label,
            value=_simplify_value(f.value),
            captured_at=f.captured_at,
            transcript_ref=f.transcript_ref,
            confidence=f.confidence,
        )
        for f in field_rows
    ]
    if call.qualification_status:
        dto.qualification.evaluated_at = call.updated_at

    # Link the sibling recordings module while it keeps its own table.
    # The calls module does not own recordings; a null here simply means the
    # recording pipeline has not produced one for this call yet.
    dto.recording = None
    return DataResponse[CallDTO](data=dto)


def _simplify_value(value: dict | None) -> str | int | float | bool | None:
    """Unwrap a stored single-value ``call_qualification_fields.value`` dict.

    The pipeline may persist ``{"value": "yes"}`` or a raw scalar; either way
    the wire contract wants the scalar, not the container.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        if "value" in value and value.get("value") is not None:
            return value["value"]
        return None
    return value


async def list_live_calls(
    session: AsyncSession,
    user: UserContext,
) -> DataResponse[list[LiveCallDTO]]:
    rows = await repo.list_live_calls(
        session, policies.resolve_scope_constraints(user)
    )
    return DataResponse[list[LiveCallDTO]](
        data=[
            LiveCallDTO(
                id=r["call"].id,
                reference=r["call"].reference or str(r["call"].id),
                campaign_name=r["campaign_name"],
                script_version=None,
                caller=CallerInfoDTO(
                    number=r["call"].caller_number
                    if policies.CallPolicy.sees_full_pii(user)
                    else None,
                    masked=policies.CallPolicy.masked_phone(
                        r["call"].caller_number, user
                    ),
                    state=r["call"].caller_state,
                ),
                live_state=policies.live_state(r["call"].status),
                node_name=None,
                attempt_number=r["call"].attempt_number or 1,
                started_at=r["call"].started_at,
                duration_seconds=r["call"].duration_seconds,
                qualification_status=r["call"].qualification_status,
                consent_captured=bool(
                    r["call"].talk_time_seconds or r["call"].duration_seconds
                ),
            )
            for r in rows
        ]
    )


async def get_transcript(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[list[TranscriptTurnDTO]]:
    await _load(session, user, call_id)
    turns = await repo.get_transcript(
        session, call_id, policies.resolve_scope_constraints(user)
    )
    return DataResponse[list[TranscriptTurnDTO]](
        data=[
            TranscriptTurnDTO(
                id=t.id,
                speaker=t.speaker,
                text=t.text,
                start_ms=t.start_ts_ms,
                end_ms=t.end_ts_ms,
                node_id=t.node_id,
                confidence=t.confidence,
                redacted=t.redacted,
            )
            for t in turns
        ]
    )


async def get_timeline(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[list[TimelineEventDTO]]:
    await _load(session, user, call_id)
    events = await repo.get_timeline(
        session, call_id, policies.resolve_scope_constraints(user)
    )
    return DataResponse[list[TimelineEventDTO]](
        data=[
            TimelineEventDTO(
                id=e.id,
                type=e.type,
                event_ts=e.event_ts,
                category=policies.event_category(e.type),
                payload=e.payload,
            )
            for e in events
        ]
    )


async def get_performance(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[PerformanceDTO]:
    await _load(session, user, call_id)
    perf = await repo.get_performance(
        session, call_id, policies.resolve_scope_constraints(user)
    )
    if perf is None:
        return DataResponse[PerformanceDTO](data=PerformanceDTO())
    return DataResponse[PerformanceDTO](
        data=PerformanceDTO(
            vad_ms=perf.vad_ms,
            stt_ms=perf.stt_ms,
            decide_ms=perf.decide_ms,
            llm_ttft_ms=perf.llm_ttft_ms,
            llm_total_ms=perf.llm_total_ms,
            tts_ttfa_ms=perf.tts_ttfa_ms,
            tts_total_ms=perf.tts_total_ms,
            total_turn_ms=perf.total_turn_ms,
            turn_count=perf.turn_count,
            stt_provider=perf.stt_provider,
            tts_provider=perf.tts_provider,
            llm_provider=perf.llm_provider,
        )
    )


async def get_script_path(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[list[ScriptPathNodeDTO]]:
    await _load(session, user, call_id)
    nodes = await repo.get_script_path(
        session, call_id, policies.resolve_scope_constraints(user)
    )
    return DataResponse[list[ScriptPathNodeDTO]](
        data=[
            ScriptPathNodeDTO(
                id=n.id,
                seq=n.seq,
                node_id=n.node_id,
                node_type=n.node_type,
                node_name=n.node_name,
                entered_at=n.entered_at,
                exited_at=n.exited_at,
                transition_taken=n.transition_taken,
                meta=n.meta,
            )
            for n in nodes
        ]
    )


# ---------------------------------------------------------------------------
# Write - disposition
# ---------------------------------------------------------------------------


async def update_disposition(
    session: AsyncSession,
    user: UserContext,
    call_id: uuid.UUID,
    payload: DispositionUpdate,
) -> DataResponse[CallDTO]:
    """Write the call's disposition and any qualification consequence atomically.

    The rule (TalkFlow.md section 26.1 "Outcome"): the disposition may only be
    updated while the call is still in the dialer loop; once it has closed,
    only the verifier pipeline may change it (its own endpoints).  Qualification
    dispositions like ``disqualified_age`` also roll the ``qualification_status``
    column, so the CDR funnel and the call record can never disagree.
    """
    row = await _load(session, user, call_id)
    call = row["call"]

    if not policies.can_update_disposition(call.status):
        raise CallInvalidStateError(
            details={
                "status": call.status,
                "reason": "Disposition is immutable once the call has closed.",
            }
        )

    old_disposition = call.disposition
    old_qual_status = call.qualification_status
    call.disposition = payload.disposition

    # Qualification consequences of this disposition (pure policy, no I/O).
    qual_status, disqual_reason = policies.qualification_result(payload.disposition)
    if qual_status:
        call.qualification_status = qual_status
    if disqual_reason:
        call.disqualification_reason = disqual_reason

    call.vicidial_status = policies.to_vicidial_status(
        payload.disposition
    ) or call.vicidial_status

    await repo.save(session, call)

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="call.disposition",
        resource_type="call",
        resource_id=str(call.id),
        result=AuditResult.SUCCESS,
        details={
            "from": old_disposition,
            "to": payload.disposition,
            "reason": payload.reason,
            "vicidial_status": call.vicidial_status,
        },
    )
    await publish_call_event(
        session,
        call_id=call.id,
        reference=call.reference or str(call.id),
        event_type=CallEventType.DISPOSITION_CHANGED,
        payload={
            "from": old_disposition,
            "to": payload.disposition,
            "reason": payload.reason,
            "campaign_id": str(call.campaign_id) if call.campaign_id else None,
        },
    )
    if qual_status and qual_status != old_qual_status:
        await publish_call_event(
            session,
            call_id=call.id,
            reference=call.reference or str(call.id),
            event_type=CallEventType.QUALIFICATION_CHANGED,
            payload={
                "status": qual_status,
                "reason": disqual_reason,
            },
        )
    await session.commit()

    logger.info(
        "call disposition updated",
        call_id=str(call.id),
        disposition=payload.disposition,
        actor=str(user.user_id),
    )
    return DataResponse[CallDTO](data=_dto_from_row(row, user))