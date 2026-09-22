"""Data access for export jobs + report row sources (Rule R3 / R5).

Exports read from the shared projections (``leads_table`` / ``campaigns_table``
/ ``calls_table``) exactly as recordings reads ``leads_table`` and campaigns
reads ``calls_table``; the owning modules migrate the real tables.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.exports.schemas import ExportFilters, ExportListQuery
from app.packages.db.models import ExportJob, calls_table, campaigns_table, leads_table

_SORTABLE = {
    "report": ExportJob.report,
    "status": ExportJob.status,
    "createdAt": ExportJob.created_at,
    "updatedAt": ExportJob.updated_at,
}


def _order_by(query: ExportListQuery):
    column = _SORTABLE.get(query.sort or "", ExportJob.created_at)
    descending = (query.order or "desc").lower() != "asc"
    if query.sort is None:
        descending = True
    return column.desc() if descending else column.asc()


async def list_exports(
    session: AsyncSession,
    query: ExportListQuery,
) -> tuple[list[ExportJob], int]:
    filters: list = []
    if query.status is not None:
        filters.append(ExportJob.status == query.status.value)
    if query.report:
        filters.append(ExportJob.report == query.report)

    total = (
        await session.execute(
            select(func.count(ExportJob.id)).where(and_(True, *filters))
        )
    ).scalar_one()
    stmt = (
        select(ExportJob)
        .where(and_(True, *filters))
        .order_by(_order_by(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def get_export(session: AsyncSession, job_id: uuid.UUID) -> ExportJob | None:
    stmt = select(ExportJob).where(ExportJob.id == job_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def save_export(session: AsyncSession, job: ExportJob) -> None:
    session.add(job)
    await session.flush()


# ---------------------------------------------------------------------------
# Report row sources
# ---------------------------------------------------------------------------
def _lead_filters(filters: ExportFilters) -> list:
    clauses: list = []
    if filters.campaign_id is not None:
        clauses.append(leads_table.c.campaign_id == filters.campaign_id)
    if filters.status:
        clauses.append(leads_table.c.status == filters.status)
    if filters.source:
        clauses.append(leads_table.c.source == filters.source)
    if filters.date_from:
        clauses.append(leads_table.c.created_at >= filters.date_from)
    if filters.date_to:
        clauses.append(leads_table.c.created_at <= filters.date_to)
    if filters.q:
        like = f"%{filters.q}%"
        clauses.append(
            or_(
                leads_table.c.first_name.ilike(like),
                leads_table.c.last_name.ilike(like),
                leads_table.c.phone_normalized.ilike(like),
                leads_table.c.email.ilike(like),
            )
        )
    return clauses


def _campaign_filters(filters: ExportFilters) -> list:
    clauses: list = []
    if filters.status:
        clauses.append(campaigns_table.c.status == filters.status)
    if filters.date_from:
        clauses.append(campaigns_table.c.created_at >= filters.date_from)
    if filters.date_to:
        clauses.append(campaigns_table.c.created_at <= filters.date_to)
    if filters.q:
        clauses.append(campaigns_table.c.name.ilike(f"%{filters.q}%"))
    return clauses


def _call_filters(filters: ExportFilters) -> list:
    clauses: list = []
    if filters.campaign_id is not None:
        clauses.append(calls_table.c.campaign_id == filters.campaign_id)
    if filters.date_from:
        clauses.append(calls_table.c.started_at >= filters.date_from)
    if filters.date_to:
        clauses.append(calls_table.c.started_at <= filters.date_to)
    if filters.q:
        like = f"%{filters.q}%"
        clauses.append(
            or_(
                calls_table.c.disposition.ilike(like),
                calls_table.c.qualification_status.ilike(like),
            )
        )
    return clauses


async def fetch_report_rows(
    session: AsyncSession, report: str, filters: ExportFilters, limit: int = 100_000
) -> list[dict[str, Any]]:
    """Fetch the report rows as header-keyed dicts (bounded for safety)."""
    if report == "leads":
        stmt = (
            select(
                leads_table.c.id,
                leads_table.c.first_name,
                leads_table.c.last_name,
                leads_table.c.phone_normalized.label("phone"),
                leads_table.c.alt_phone,
                leads_table.c.email,
                leads_table.c.state,
                leads_table.c.zip_code,
                leads_table.c.date_of_birth,
                leads_table.c.age,
                leads_table.c.source,
                leads_table.c.source_batch_id,
                leads_table.c.campaign_id,
                leads_table.c.status,
                leads_table.c.attempts,
                leads_table.c.last_attempt_at,
                leads_table.c.next_attempt_at,
                leads_table.c.assigned_to,
                leads_table.c.suppressed,
                leads_table.c.suppression_reason,
                leads_table.c.created_at,
                leads_table.c.updated_at,
            )
            .where(and_(True, *_lead_filters(filters)))
            .order_by(leads_table.c.created_at)
            .limit(limit)
        )
    elif report == "campaigns":
        stmt = (
            select(
                campaigns_table.c.id,
                campaigns_table.c.name,
                campaigns_table.c.status,
                campaigns_table.c.created_at,
                campaigns_table.c.updated_at,
            )
            .where(and_(True, *_campaign_filters(filters)))
            .order_by(campaigns_table.c.created_at)
            .limit(limit)
        )
    else:  # calls
        stmt = (
            select(
                calls_table.c.id,
                calls_table.c.started_at,
                calls_table.c.duration_seconds,
                calls_table.c.disposition,
                calls_table.c.qualification_status,
                calls_table.c.disqualification_reason,
                calls_table.c.lead_id,
                calls_table.c.campaign_id,
                calls_table.c.verifier_id,
            )
            .where(and_(True, *_call_filters(filters)))
            .order_by(calls_table.c.started_at)
            .limit(limit)
        )

    rows = (await session.execute(stmt)).all()
    return [dict(row._mapping) for row in rows]
