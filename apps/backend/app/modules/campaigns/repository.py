"""Data access for campaigns (Rule R3 - module-scoped; Rule R5 - scoped reads)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.schemas import CampaignListQuery
from app.packages.db.models import Campaign, CampaignVicidialList, calls_table

# Stats vocabularies (TalkFlow.md sections 11.3-11.5).  Lower-cased so a mixed
# case write from the calls pipeline still counts.
_QUALIFIED_STATUSES = ("qualified", "passed")
_TRANSFER_DISPOSITIONS = (
    "qualified_transferred",
    "qualified_transfer_failed",
    "verified_accepted",
    "verified_rejected",
    "verifier_no_contact",
)

_SORTABLE = {
    "name": Campaign.name,
    "status": Campaign.status,
    "created_at": Campaign.created_at,
    "updated_at": Campaign.updated_at,
}


def _scope_filters(constraints: dict[str, Any]) -> list:
    """Column-level scoping (Rule R5).

    Campaigns are global today, so this returns no narrowing; the hook exists so
    callers already pass constraints and scoping can be tightened in one place
    once campaign assignment / verifier-group tables land.
    """
    _ = constraints
    return []


def _order_by(query: CampaignListQuery):
    column = _SORTABLE.get(query.sort or "", Campaign.created_at)
    descending = (query.order or "desc").lower() != "asc"
    if query.sort is None:
        descending = True
    return column.desc() if descending else column.asc()


async def list_campaigns(
    session: AsyncSession,
    query: CampaignListQuery,
    constraints: dict[str, Any],
) -> tuple[list[Campaign], int]:
    filters: list = _scope_filters(constraints)
    if query.status is not None:
        filters.append(Campaign.status == query.status.value)
    if query.search:
        like = f"%{query.search}%"
        filters.append(or_(Campaign.name.ilike(like), Campaign.status.ilike(like)))

    total = (
        await session.execute(
            select(func.count(Campaign.id)).where(and_(True, *filters))
        )
    ).scalar_one()

    stmt = (
        select(Campaign)
        .where(and_(True, *filters))
        .order_by(_order_by(query))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def get_campaign(
    session: AsyncSession,
    campaign_id: uuid.UUID,
    constraints: dict[str, Any],
) -> Campaign | None:
    stmt = select(Campaign).where(
        and_(Campaign.id == campaign_id, *_scope_filters(constraints))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def fetch_list_ids(session: AsyncSession, campaign_id: uuid.UUID) -> list[str]:
    stmt = (
        select(CampaignVicidialList.vicidial_list_id)
        .where(
            CampaignVicidialList.campaign_id == campaign_id,
            CampaignVicidialList.active.is_(True),
        )
        .order_by(CampaignVicidialList.vicidial_list_id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def batch_list_ids(
    session: AsyncSession, campaign_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not campaign_ids:
        return {}
    stmt = (
        select(
            CampaignVicidialList.campaign_id,
            CampaignVicidialList.vicidial_list_id,
        )
        .where(
            CampaignVicidialList.campaign_id.in_(campaign_ids),
            CampaignVicidialList.active.is_(True),
        )
        .order_by(CampaignVicidialList.vicidial_list_id)
    )
    grouped: dict[uuid.UUID, list[str]] = {cid: [] for cid in campaign_ids}
    for row in (await session.execute(stmt)).all():
        grouped[row.campaign_id].append(row.vicidial_list_id)
    return grouped


async def replace_vicidial_lists(
    session: AsyncSession, campaign_id: uuid.UUID, list_ids: list[str]
) -> None:
    """Replace the campaign's VICIdial list mapping (de-duplicated, order-stable)."""
    await session.execute(
        delete(CampaignVicidialList).where(
            CampaignVicidialList.campaign_id == campaign_id
        )
    )
    unique_ids = list(dict.fromkeys(list_ids))
    if unique_ids:
        await session.execute(
            insert(CampaignVicidialList).values(
                [
                    {"campaign_id": campaign_id, "vicidial_list_id": list_id}
                    for list_id in unique_ids
                ]
            )
        )
    await session.flush()


async def get_campaign_stats(
    session: AsyncSession, campaign_id: uuid.UUID
) -> tuple[int, int, int, int]:
    """Today's ``(calls, contacted, qualified, transferred)`` for a campaign.

    Aggregated in a single pass over the shared ``calls`` projection.  A call is
    "contacted" when it had talk time (``duration_seconds > 0``), "qualified"
    when its §11.4 status is qualified and "transferred" when its §11.3/§11.5
    disposition is a transfer outcome.  The calls module owns the table; this
    read-only projection consumes only the columns it needs (Rule R3/R5).
    """
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(
        func.count().label("calls_today"),
        func.count().filter(calls_table.c.duration_seconds > 0).label("contacted"),
        func.count()
        .filter(func.lower(calls_table.c.qualification_status).in_(_QUALIFIED_STATUSES))
        .label("qualified"),
        func.count()
        .filter(func.lower(calls_table.c.disposition).in_(_TRANSFER_DISPOSITIONS))
        .label("transferred"),
    ).where(
        calls_table.c.campaign_id == campaign_id,
        calls_table.c.started_at >= day_start,
    )
    row = (await session.execute(stmt)).one()
    return (
        int(row.calls_today),
        int(row.contacted),
        int(row.qualified),
        int(row.transferred),
    )


async def save(session: AsyncSession, campaign: Campaign) -> None:
    session.add(campaign)
    await session.flush()
