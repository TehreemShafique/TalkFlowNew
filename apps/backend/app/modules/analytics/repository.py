"""Analytics repository - queries EXCLUSIVELY agg_* pre-aggregated tables (Step 39).

Strict Rule: ZERO direct queries against raw calls table. All analytics
endpoints query from agg_campaign_daily, agg_script_version_daily,
agg_source_daily, agg_bot_daily, agg_compliance_daily, or
agg_dashboard_counters.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import (
    AggBotDaily,
    AggCampaignDaily,
    AggComplianceDaily,
    AggDashboardCounters,
    AggScriptVersionDaily,
    AggSourceDaily,
)


async def get_dashboard_counters(session: AsyncSession) -> AggDashboardCounters | None:
    stmt = select(AggDashboardCounters).where(AggDashboardCounters.id == "default").limit(1)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_campaign_rollups(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
    campaign_id: uuid.UUID | None,
) -> list[AggCampaignDaily]:
    stmt = select(AggCampaignDaily)
    if from_date:
        stmt = stmt.where(AggCampaignDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggCampaignDaily.date <= to_date)
    if campaign_id:
        stmt = stmt.where(AggCampaignDaily.campaign_id == campaign_id)

    stmt = stmt.order_by(AggCampaignDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_script_version_rollups(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
) -> list[AggScriptVersionDaily]:
    stmt = select(AggScriptVersionDaily)
    if from_date:
        stmt = stmt.where(AggScriptVersionDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggScriptVersionDaily.date <= to_date)

    stmt = stmt.order_by(AggScriptVersionDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_source_rollups(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
) -> list[AggSourceDaily]:
    stmt = select(AggSourceDaily)
    if from_date:
        stmt = stmt.where(AggSourceDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggSourceDaily.date <= to_date)

    stmt = stmt.order_by(AggSourceDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_bot_rollups(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
) -> list[AggBotDaily]:
    stmt = select(AggBotDaily)
    if from_date:
        stmt = stmt.where(AggBotDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggBotDaily.date <= to_date)

    stmt = stmt.order_by(AggBotDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_compliance_rollups(
    session: AsyncSession,
    from_date: date | None,
    to_date: date | None,
) -> list[AggComplianceDaily]:
    stmt = select(AggComplianceDaily)
    if from_date:
        stmt = stmt.where(AggComplianceDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggComplianceDaily.date <= to_date)

    stmt = stmt.order_by(AggComplianceDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())
