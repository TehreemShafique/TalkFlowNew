"""Data access for leads (Rule R3 - module-scoped; Rule R5 - scoped reads).

Insert/update of master contact rows goes through the ORM ``Lead``; the only
cross-module read (the suppression register used to classify CSV rows during
the wizard's STEP 3) goes through the shared read-only projection, mirroring
how recordings reads ``leads_table`` / campaigns reads ``calls_table``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leads.schemas import LeadListQuery
from app.packages.db.models import (
    Lead,
    LeadImportJob,
    campaigns_table,
    suppression_entries_table,
)

_SORTABLE = {
    "firstName": Lead.first_name,
    "lastName": Lead.last_name,
    "status": Lead.status,
    "attempts": Lead.attempts,
    "createdAt": Lead.created_at,
    "updatedAt": Lead.updated_at,
}


def _scope_filters(constraints: dict[str, Any]) -> list:
    _ = constraints
    return []


def _order_by(query: LeadListQuery):
    column = _SORTABLE.get(query.sort or "", Lead.created_at)
    descending = (query.order or "desc").lower() != "asc"
    if query.sort is None:
        descending = True
    return column.desc() if descending else column.asc()


async def list_leads(
    session: AsyncSession,
    query: LeadListQuery,
    constraints: dict[str, Any],
) -> tuple[list[tuple[Lead, str | None]], int]:
    filters: list = _scope_filters(constraints)
    if query.status is not None:
        filters.append(Lead.status == query.status.value)
    if query.suppressed is not None:
        filters.append(Lead.suppressed.is_(query.suppressed))
    if query.campaign_id is not None:
        filters.append(Lead.campaign_id == query.campaign_id)
    if query.source:
        filters.append(Lead.source == query.source)
    if query.search:
        like = f"%{query.search}%"
        filters.append(
            or_(
                Lead.first_name.ilike(like),
                Lead.last_name.ilike(like),
                Lead.phone_normalized.ilike(like),
                Lead.email.ilike(like),
            )
        )

    total = (
        await session.execute(
            select(func.count(Lead.id)).where(and_(True, *filters))
        )
    ).scalar_one()

    stmt = (
        select(Lead, campaigns_table.c.name)
        .outerjoin(campaigns_table, Lead.campaign_id == campaigns_table.c.id)
        .where(and_(True, *filters))
        .order_by(_order_by(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = list((await session.execute(stmt)).tuples().all())
    return rows, total


async def get_lead(
    session: AsyncSession,
    lead_id: uuid.UUID,
    constraints: dict[str, Any],
) -> tuple[Lead, str | None] | None:
    stmt = (
        select(Lead, campaigns_table.c.name)
        .outerjoin(campaigns_table, Lead.campaign_id == campaigns_table.c.id)
        .where(and_(Lead.id == lead_id, *_scope_filters(constraints)))
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None
    return (row[0], row[1])


async def campaign_name(
    session: AsyncSession, campaign_id: uuid.UUID
) -> str | None:
    stmt = select(campaigns_table.c.name).where(campaigns_table.c.id == campaign_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def existing_phone_numbers(
    session: AsyncSession, phones: list[str]
) -> set[str]:
    """Normalized phones already present in the leads table (dedup set)."""
    if not phones:
        return set()
    stmt = select(Lead.phone_normalized).where(Lead.phone_normalized.in_(phones))
    return {phone for phone in (await session.execute(stmt)).scalars().all() if phone}


async def active_suppressed_phones(
    session: AsyncSession, phones: list[str]
) -> set[str]:
    """ACTIVE (non-removed) suppression register phones (shared projection)."""
    if not phones:
        return set()
    stmt = select(suppression_entries_table.c.phone_normalized).where(
        suppression_entries_table.c.phone_normalized.in_(phones),
        suppression_entries_table.c.removed_at.is_(None),
    )
    return {
        phone
        for phone in (await session.execute(stmt)).scalars().all()
        if phone
    }


async def save_lead(session: AsyncSession, lead: Lead) -> None:
    session.add(lead)
    await session.flush()


async def bulk_insert_leads(session: AsyncSession, values: list[dict[str, Any]]) -> None:
    """Single-pass multi-row insert (no fire-and-forget per row, Rule R7)."""
    if not values:
        return
    await session.execute(pg_insert(Lead).values(values))


async def bulk_update_leads_by_phone(
    session: AsyncSession, updates: list[dict[str, Any]]
) -> None:
    """``UPDATE ... WHERE phone_normalized = :phone`` in one statement per phone.

    Only fields the mapping produced are written; the existing lead keeps its
    lifecycle (attempts / timers) untouched unless the wizard chose otherwise.
    """
    for update_ in updates:
        phone = update_.pop("phone")
        stmt = (
            update(Lead)
            .where(Lead.phone_normalized == phone)
            .values(**update_)
        )
        await session.execute(stmt)


# ---------------------------------------------------------------------------
# Import jobs
# ---------------------------------------------------------------------------
async def get_import_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    constraints: dict[str, Any],
) -> LeadImportJob | None:
    _ = constraints
    stmt = select(LeadImportJob).where(LeadImportJob.id == job_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def save_import_job(session: AsyncSession, job: LeadImportJob) -> None:
    session.add(job)
    await session.flush()