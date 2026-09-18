"""Data access for the suppression register (Rule R3 / R5).

The ``leads`` flag sync uses the shared ``leads_table`` projection (the same
surface recordings reads from), so the suppression module never reaches into
the leads module's repository.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.suppression.schemas import SuppressionListQuery
from app.packages.db.models import SuppressionEntry, leads_table

_SORTABLE = {
    "phone": SuppressionEntry.phone_normalized,
    "reason": SuppressionEntry.reason,
    "addedAt": SuppressionEntry.added_at,
    "removedAt": SuppressionEntry.removed_at,
}


def _scope_filters(constraints: dict[str, Any]) -> list:
    _ = constraints
    return []


def _order_by(query: SuppressionListQuery):
    column = _SORTABLE.get(query.sort or "", SuppressionEntry.added_at)
    descending = (query.order or "desc").lower() != "asc"
    if query.sort is None:
        descending = True
    return column.desc() if descending else column.asc()


async def list_entries(
    session: AsyncSession,
    query: SuppressionListQuery,
    constraints: dict[str, Any],
) -> tuple[list[SuppressionEntry], int]:
    filters: list = _scope_filters(constraints)
    if not query.include_removed:
        filters.append(SuppressionEntry.removed_at.is_(None))
    if query.phone:
        filters.append(SuppressionEntry.phone_normalized == query.phone)
    if query.reason is not None:
        filters.append(SuppressionEntry.reason == query.reason.value)
    if query.source:
        filters.append(SuppressionEntry.source == query.source)

    total = (
        await session.execute(
            select(func.count(SuppressionEntry.id)).where(and_(True, *filters))
        )
    ).scalar_one()

    stmt = (
        select(SuppressionEntry)
        .where(and_(True, *filters))
        .order_by(_order_by(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def get_entry(
    session: AsyncSession, entry_id: uuid.UUID, constraints: dict[str, Any]
) -> SuppressionEntry | None:
    stmt = select(SuppressionEntry).where(
        and_(SuppressionEntry.id == entry_id, *_scope_filters(constraints))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_active_entry_by_phone(
    session: AsyncSession, phone: str
) -> SuppressionEntry | None:
    stmt = select(SuppressionEntry).where(
        SuppressionEntry.phone_normalized == phone,
        SuppressionEntry.removed_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def save_entry(session: AsyncSession, entry: SuppressionEntry) -> None:
    session.add(entry)
    await session.flush()


async def bulk_add_entries(session: AsyncSession, values: list[dict[str, Any]]) -> int:
    """Insert-only; conflicts with an ACTIVE row are skipped (not updated).

    Conflicting rows count against the partial unique index, so a removed
    entry never blocks re-adding the same number.
    """
    if not values:
        return 0
    stmt = (
        pg_insert(SuppressionEntry)
        .values(values)
        .on_conflict_do_nothing(
            index_elements=["phone_normalized"],
            index_where=text("removed_at IS NULL"),
        )
    )
    result = await session.execute(stmt)
    rowcount = cast(CursorResult[Any], result).rowcount
    return int(rowcount or 0)


async def mark_leads_suppressed(
    session: AsyncSession, phones: list[str], reason: str
) -> None:
    """Reflect the DNC add onto the master leads registry (nullable flags)."""
    if not phones:
        return
    await session.execute(
        update(leads_table)
        .where(leads_table.c.phone_normalized.in_(phones))
        .values(suppressed=True, suppression_reason=reason)
    )


async def clear_leads_suppressed(
    session: AsyncSession, phones: list[str]
) -> None:
    """Reflect a DNC removal onto leads that carry this reason."""
    if not phones:
        return
    await session.execute(
        update(leads_table)
        .where(
            leads_table.c.phone_normalized.in_(phones),
            leads_table.c.suppressed.is_(True),
        )
        .values(suppressed=False, suppression_reason=None)
    )


async def touch_entry(
    session: AsyncSession,
    entry: SuppressionEntry,
    *,
    removed_at: datetime | None,
    removed_by: uuid.UUID | None,
) -> None:
    entry.removed_at = removed_at
    entry.removed_by = removed_by
    await save_entry(session, entry)