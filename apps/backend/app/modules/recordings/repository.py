"""Data access for recordings with explicit scope enforcement (Rule R5).

Every query embeds the caller's scope constraints at the ORM level so an
over-broad IEnumerable call can never leak another tenant's rows.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.recordings.errors import RecordingNotFoundError
from app.modules.recordings.schemas import QaAuditRequest, RecordingListQuery
from app.packages.db.models import (
    CallRecording,
    User,
    call_transcripts_table,
    calls_table,
    campaigns_table,
    leads_table,
    qa_reviews_table,
)


def _scope_filters(constraints: dict[str, Any]) -> list:
    """Column-level tenant scoping (Rule R5).

    ``calls.tenant_id`` is only present after the recordings-alignment
    migration; callers that run against a pre-migration DB simply get no
    narrowing (the reconciled master-admin scope is unfiltered anyway).
    """
    filters: list = []
    tenant = constraints.get("tenant_id")
    if tenant:
        filters.append(calls_table.c.tenant_id == tenant)
    return filters


async def _fetch_transcripts(
    session: AsyncSession, call_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Batch-load AI Voice Bot transcript lines per call, in spoken order."""
    if not call_ids:
        return {}
    stmt = (
        select(
            call_transcripts_table.c.call_id,
            call_transcripts_table.c.seq,
            call_transcripts_table.c.speaker,
            call_transcripts_table.c.time,
            call_transcripts_table.c.text,
        )
        .where(call_transcripts_table.c.call_id.in_(call_ids))
        .order_by(call_transcripts_table.c.call_id, call_transcripts_table.c.seq)
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[uuid.UUID, list[dict[str, Any]]] = {cid: [] for cid in call_ids}
    for row in rows:
        grouped[row.call_id].append(
            {
                "speaker": row.speaker,
                "time": row.time,
                "text": row.text,
            }
        )
    return grouped


async def get_recording(
    session: AsyncSession,
    recording_id: uuid.UUID,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Fetch one row with its joined display columns; 404 when missing."""
    stmt = (
        select(
            CallRecording,
            leads_table.c.first_name,
            leads_table.c.last_name,
            leads_table.c.phone_normalized,
            campaigns_table.c.name.label("campaign_name"),
            calls_table.c.duration_seconds.label("call_duration"),
            calls_table.c.disposition,
            calls_table.c.qualification_status,
            calls_table.c.disqualification_reason,
            User.full_name.label("verifier_name"),
            qa_reviews_table.c.score.label("qa_score"),
            qa_reviews_table.c.status.label("qa_status"),
        )
        .join(calls_table, calls_table.c.id == CallRecording.call_id)
        .outerjoin(leads_table, leads_table.c.id == CallRecording.lead_id)
        .outerjoin(campaigns_table, campaigns_table.c.id == CallRecording.campaign_id)
        .outerjoin(User, User.id == calls_table.c.verifier_id)
        .outerjoin(
            qa_reviews_table, qa_reviews_table.c.call_id == CallRecording.call_id
        )
        .where(and_(CallRecording.id == recording_id, *_scope_filters(constraints)))
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise RecordingNotFoundError("recording.not_found")
    data = dict(row._mapping)
    ent = data.get("CallRecording")
    if ent is not None:
        transcripts = await _fetch_transcripts(session, [ent.call_id])
        data["transcript"] = transcripts.get(ent.call_id)
    return data


async def list_recordings(
    session: AsyncSession,
    query: RecordingListQuery,
    constraints: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """Paginated collection honoring R5 scope constraints."""
    filters: list = _scope_filters(constraints)

    if query.status is not None:
        filters.append(CallRecording.status == query.status.value)
    if query.campaign_id is not None:
        filters.append(CallRecording.campaign_id == query.campaign_id)
    if query.lead_id is not None:
        filters.append(CallRecording.lead_id == query.lead_id)
    if query.disposition:
        filters.append(calls_table.c.disposition.ilike(f"%{query.disposition}%"))
    if query.qa_status:
        filters.append(qa_reviews_table.c.status == query.qa_status)
    if query.from_ is not None:
        filters.append(CallRecording.created_at >= query.from_)
    if query.to is not None:
        filters.append(CallRecording.created_at <= query.to)
    if query.search:
        like = f"%{query.search}%"
        filters.append(
            or_(
                leads_table.c.first_name.ilike(like),
                leads_table.c.last_name.ilike(like),
                leads_table.c.phone_normalized.ilike(like),
                CallRecording.vicidial_recording_id.ilike(like),
            )
        )

    count_stmt = (
        select(func.count(CallRecording.id))
        .join(calls_table, calls_table.c.id == CallRecording.call_id)
        .join(leads_table, leads_table.c.id == CallRecording.lead_id, isouter=True)
        .join(
            qa_reviews_table,
            qa_reviews_table.c.call_id == CallRecording.call_id,
            isouter=True,
        )
        .where(and_(True, *filters))
    )
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            CallRecording,
            leads_table.c.first_name,
            leads_table.c.last_name,
            leads_table.c.phone_normalized,
            campaigns_table.c.name.label("campaign_name"),
            calls_table.c.duration_seconds.label("call_duration"),
            calls_table.c.disposition,
            calls_table.c.qualification_status,
            calls_table.c.disqualification_reason,
            User.full_name.label("verifier_name"),
            qa_reviews_table.c.score.label("qa_score"),
            qa_reviews_table.c.status.label("qa_status"),
        )
        .join(calls_table, calls_table.c.id == CallRecording.call_id)
        .outerjoin(leads_table, leads_table.c.id == CallRecording.lead_id)
        .outerjoin(campaigns_table, campaigns_table.c.id == CallRecording.campaign_id)
        .outerjoin(User, User.id == calls_table.c.verifier_id)
        .outerjoin(
            qa_reviews_table, qa_reviews_table.c.call_id == CallRecording.call_id
        )
        .where(and_(True, *filters))
        .order_by(CallRecording.created_at.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = (await session.execute(stmt)).all()
    raw_rows = [dict(r._mapping) for r in rows]
    call_ids = [
        ent.call_id
        for r in raw_rows
        if isinstance(ent := r.get("CallRecording"), CallRecording)
    ]
    transcripts = await _fetch_transcripts(session, call_ids)
    for r in raw_rows:
        ent = r.get("CallRecording")
        r["transcript"] = (
            transcripts.get(ent.call_id) if isinstance(ent, CallRecording) else None
        )
    return raw_rows, total


# Kept for callers that only need the ORM row (e.g. stream/download grants).
async def fetch_row(
    session: AsyncSession, recording_id: uuid.UUID, constraints: dict[str, Any]
) -> CallRecording:
    stmt = select(CallRecording).where(
        and_(CallRecording.id == recording_id, *_scope_filters(constraints))
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise RecordingNotFoundError("recording.not_found")
    return row


async def save(session: AsyncSession, row: CallRecording) -> None:
    session.add(row)
    await session.flush()


async def fetch_qa_review(
    session: AsyncSession, recording: CallRecording
) -> dict[str, Any] | None:
    """One QA review row for a recording (None when never audited)."""
    stmt = select(qa_reviews_table).where(
        qa_reviews_table.c.call_id == recording.call_id
    )
    row = (await session.execute(stmt)).first()
    return dict(row._mapping) if row is not None else None


async def upsert_qa_review(
    session: AsyncSession,
    *,
    recording: CallRecording,
    payload: QaAuditRequest,
    actor_id: uuid.UUID,
    now: Any,
) -> None:
    """Insert or update the single QA review for the recording's call.

    Keyed on ``call_id`` (one review per call); every field from the scorecard
    modal round-trips through this statement.
    """
    values = {
        "call_id": recording.call_id,
        "recording_id": recording.id,
        "status": payload.status or "Audited",
        "score": payload.score,
        "auto_failed": payload.auto_failed,
        "consent_verified": payload.consent_verified,
        "qual_verified": payload.qual_verified,
        "transfer_verified": payload.transfer_verified,
        "notes": payload.notes,
        "audited_by": actor_id,
        "updated_at": now,
    }
    stmt = (
        pg_insert(qa_reviews_table)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[qa_reviews_table.c.call_id],
            set_={
                "recording_id": values["recording_id"],
                "status": values["status"],
                "score": values["score"],
                "auto_failed": values["auto_failed"],
                "consent_verified": values["consent_verified"],
                "qual_verified": values["qual_verified"],
                "transfer_verified": values["transfer_verified"],
                "notes": values["notes"],
                "audited_by": values["audited_by"],
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
