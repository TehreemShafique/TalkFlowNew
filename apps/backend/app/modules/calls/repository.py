"""Data access for the calls module (Rule R3/R5).

All reads go through repository functions that never join across module
boundaries they do not own (blueprint section 10).  The ``campaigns`` and
``leads`` tables are read-only projections consumed via the shared
``_shared`` metadata (Rule R3).

Scope constraints (Rule R5) are resolved once by the service layer and passed
in as a plain dict so the repository is trivially testable without a real
authenticated principal.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calls import policies
from app.modules.calls.schemas import CallListQuery
from app.packages.db.models import (
    Call,
    CallEvent,
    CallNodePath,
    CallPerformance,
    CallQualificationField,
    TranscriptTurn,
    User,
    campaigns_table,
    leads_table,
)

# ---------------------------------------------------------------------------
# Scope + order helpers
# ---------------------------------------------------------------------------

_SORTABLE: dict[str, Any] = {
    "started_at": Call.started_at,
    "duration_seconds": Call.duration_seconds,
    "attempt_number": Call.attempt_number,
    "reference": Call.reference,
}

_SORT_MAP = {
    "campaign_name": campaigns_table.c.name,
    "lead_name": func.concat_ws(" ", leads_table.c.first_name, leads_table.c.last_name),
}


def _scope_filters(constraints: dict[str, Any]) -> list:
    filters: list = []
    tenant_id = constraints.get("tenant_id")
    if tenant_id:
        filters.append(Call.tenant_id == tenant_id)
    return filters


def _order_by(query: CallListQuery):
    column: Any
    if query.sort in _SORTABLE:
        column = _SORTABLE[query.sort]
    elif query.sort in _SORT_MAP:
        column = _SORT_MAP[query.sort]
    else:
        column = Call.started_at
    descending = (query.order or "desc").lower() != "asc"
    if query.sort is None:
        descending = True
    return column.desc() if descending else column.asc()


# ---------------------------------------------------------------------------
# List + search
# ---------------------------------------------------------------------------


async def list_calls(
    session: AsyncSession,
    query: CallListQuery,
    constraints: dict[str, Any],
) -> tuple[list[dict], int]:
    """Return ``(rows, total)`` where each row is a plain dict.

    Campaign name, lead name and the caller's base phone number are resolved
    via read-only projections; the ``lead_name`` value is ``None`` when no
    matching lead row exists (the recording pipeline may land before the lead
    import).
    """
    base_filter: list = _scope_filters(constraints)

    # --- status / direction / disposition / qualification ---
    if query.status:
        base_filter.append(Call.status == query.status.value)
    if query.direction:
        base_filter.append(Call.direction == query.direction.value)
    if query.disposition:
        base_filter.append(Call.disposition.ilike(f"%{query.disposition}%"))
    if query.qualification_status:
        base_filter.append(Call.qualification_status == query.qualification_status)
    if query.transfer_status:
        base_filter.append(Call.transfer_status == query.transfer_status)
    if query.campaign_id:
        base_filter.append(Call.campaign_id == query.campaign_id)
    if query.lead_id:
        base_filter.append(Call.lead_id == query.lead_id)
    if query.from_:
        base_filter.append(Call.started_at >= query.from_)
    if query.to:
        base_filter.append(Call.started_at <= query.to)

    # --- search (reference, caller number, lead name) ---
    search = query.search
    search_filters: list = [
        Call.reference.ilike(f"%{search}%"),
        Call.caller_number.ilike(f"%{search}%"),
    ]
    if search:
        lead_sub = (
            select(leads_table.c.id)
            .where(
                or_(
                    func.concat_ws(
                        " ", leads_table.c.first_name, leads_table.c.last_name
                    ).ilike(f"%{search}%"),
                    leads_table.c.first_name.ilike(f"%{search}%"),
                    leads_table.c.last_name.ilike(f"%{search}%"),
                )
            )
            .correlate(Call)
            .scalar_subquery()
        )
        search_filters.append(Call.lead_id.in_(lead_sub))

    where_clause = and_(True, *base_filter)
    if search:
        where_clause = and_(where_clause, or_(*search_filters))

    count_stmt = select(func.count(Call.id)).where(where_clause)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Call,
            campaigns_table.c.name.label("campaign_name"),
            leads_table.c.first_name.label("lead_first"),
            leads_table.c.last_name.label("lead_last"),
        )
        .outerjoin(
            campaigns_table,
            campaigns_table.c.id == Call.campaign_id,
        )
        .outerjoin(
            leads_table,
            leads_table.c.id == Call.lead_id,
        )
        .where(where_clause)
        .order_by(_order_by(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows: list[dict] = []
    for row in (await session.execute(stmt)).all():
        lead_name = (
            f"{row.lead_first} {row.lead_last}".strip()
            if row.lead_first or row.lead_last
            else None
        )
        rows.append(
            {
                "call": row[0],
                "campaign_name": row.campaign_name,
                "lead_name": lead_name,
            }
        )
    return rows, total


# ---------------------------------------------------------------------------
# Single-call helpers
# ---------------------------------------------------------------------------


async def get_call(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> dict | None:
    stmt = (
        select(
            Call,
            campaigns_table.c.name.label("campaign_name"),
            leads_table.c.first_name.label("lead_first"),
            leads_table.c.last_name.label("lead_last"),
        )
        .outerjoin(
            campaigns_table,
            campaigns_table.c.id == Call.campaign_id,
        )
        .outerjoin(
            leads_table,
            leads_table.c.id == Call.lead_id,
        )
        .where(and_(Call.id == call_id, *_scope_filters(constraints)))
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None
    lead_name = (
        f"{row.lead_first} {row.lead_last}".strip()
        if row.lead_first or row.lead_last
        else None
    )
    return {
        "call": row[0],
        "campaign_name": row.campaign_name,
        "lead_name": lead_name,
    }


async def list_live_calls(
    session: AsyncSession,
    constraints: dict[str, Any],
) -> list[dict]:
    live_filters: list = [Call.status.in_(policies.LIVE_STATUSES)]
    live_filters.extend(_scope_filters(constraints))

    stmt = (
        select(
            Call,
            campaigns_table.c.name.label("campaign_name"),
        )
        .outerjoin(
            campaigns_table,
            campaigns_table.c.id == Call.campaign_id,
        )
        .where(and_(*live_filters))
        .order_by(Call.started_at.desc())
    )
    rows: list[dict] = []
    for row in (await session.execute(stmt)).all():
        rows.append({"call": row[0], "campaign_name": row.campaign_name})
    return rows


# ---------------------------------------------------------------------------
# Verifier name
# ---------------------------------------------------------------------------


async def get_user_name(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> str | None:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    return (user.full_name or user.username) if user else None


# ---------------------------------------------------------------------------
# Sub-tables
# ---------------------------------------------------------------------------


async def get_qualification_fields(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> list[CallQualificationField]:
    stmt = (
        select(CallQualificationField)
        .join(Call, Call.id == CallQualificationField.call_id)
        .where(
            and_(
                CallQualificationField.call_id == call_id,
                *_scope_filters(constraints),
            )
        )
        .order_by(CallQualificationField.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_transcript(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> list[TranscriptTurn]:
    stmt = (
        select(TranscriptTurn)
        .join(Call, Call.id == TranscriptTurn.call_id)
        .where(
            and_(
                TranscriptTurn.call_id == call_id,
                *_scope_filters(constraints),
            )
        )
        .order_by(TranscriptTurn.seq)
    )
    return list((await session.execute(stmt)).scalars().all())


async def search_transcripts(
    session: AsyncSession,
    constraints: dict[str, Any],
    search_query: str,
) -> list[TranscriptTurn]:
    """Full-text search over every transcript turn the caller may view.

    Scoped exactly like the CDR reads (Rule R5): unrestricted principals pass
    ``{}`` and see everything; everyone else is narrowed to their tenant id.
    The match runs against the PostgreSQL-generated ``tsv`` column via
    ``plainto_tsquery``, so inflection/stop-words are handled by the engine and
    the GIN index (``transcript_tsv_idx``) serves the query.
    """
    query = func.plainto_tsquery("english", search_query)
    stmt = (
        select(TranscriptTurn)
        .join(Call, Call.id == TranscriptTurn.call_id)
        .where(TranscriptTurn.tsv.op("@@")(query))
        .order_by(TranscriptTurn.start_ts_ms.desc(), TranscriptTurn.id)
    )
    for constraint in _scope_filters(constraints):
        stmt = stmt.where(constraint)
    return list((await session.execute(stmt)).scalars().all())


async def get_timeline(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> list[CallEvent]:
    stmt = (
        select(CallEvent)
        .join(Call, Call.id == CallEvent.call_id)
        .where(
            and_(
                CallEvent.call_id == call_id,
                *_scope_filters(constraints),
            )
        )
        .order_by(CallEvent.event_ts)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_performance(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> CallPerformance | None:
    stmt = (
        select(CallPerformance)
        .join(Call, Call.id == CallPerformance.call_id)
        .where(
            and_(
                CallPerformance.call_id == call_id,
                *_scope_filters(constraints),
            )
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_script_path(
    session: AsyncSession,
    call_id: uuid.UUID,
    constraints: dict[str, Any],
) -> list[CallNodePath]:
    stmt = (
        select(CallNodePath)
        .join(Call, Call.id == CallNodePath.call_id)
        .where(
            and_(
                CallNodePath.call_id == call_id,
                *_scope_filters(constraints),
            )
        )
        .order_by(CallNodePath.seq)
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


async def save(session: AsyncSession, call: Call) -> None:
    session.add(call)
    await session.flush()
