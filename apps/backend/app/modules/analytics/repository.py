"""Analytics repository - queries EXCLUSIVELY agg_* pre-aggregated tables (Step 39).

Strict Rule: ZERO direct queries against the raw ``calls`` table as a source of
metrics. The five KPI reports fold over ``agg_campaign_daily``,
``agg_script_version_daily``, ``agg_source_daily``, ``agg_bot_daily`` and
``agg_compliance_daily``.

The one exception is engineering telemetry (``/analytics/performance``), which
has no PRD report and no rollup: it reads the per-call latency telemetry table
directly. It still never derives a KPI from raw calls.

Rule R5: every query takes an explicit ``scope`` and none of them defaults to
"everything". A missing tenant constraint is a caller bug, not a fallback.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, NamedTuple

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.policies import Scope
from app.packages.db.models import (
    AggBotDaily,
    AggCampaignDaily,
    AggComplianceDaily,
    AggDashboardCounters,
    AggScriptVersionDaily,
    AggSourceDaily,
)

# Rows the rollup writes for calls that carry no tenant stamp.
UNSET_TENANT = "_unassigned"


def _scoped(stmt: Select[Any], model: Any, scope: Scope) -> Select[Any]:
    """Narrow ``stmt`` to the caller's tenant unless the scope is unrestricted."""
    tenant_id = scope.get("tenant_id")
    if tenant_id is not None:
        stmt = stmt.where(model.tenant_id == tenant_id)
    return stmt


async def get_dashboard_counters(
    session: AsyncSession,
    scope: Scope,
) -> AggDashboardCounters | None:
    stmt = select(AggDashboardCounters).limit(1)
    tenant_id = scope.get("tenant_id")
    if tenant_id is not None:
        stmt = stmt.where(AggDashboardCounters.tenant_id == tenant_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_campaign_rollups(
    session: AsyncSession,
    scope: Scope,
    from_date: date | None,
    to_date: date | None,
    campaign_id: uuid.UUID | None,
) -> list[AggCampaignDaily]:
    stmt = select(AggCampaignDaily)
    stmt = _scoped(stmt, AggCampaignDaily, scope)
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
    scope: Scope,
    from_date: date | None,
    to_date: date | None,
) -> list[AggScriptVersionDaily]:
    stmt = select(AggScriptVersionDaily)
    stmt = _scoped(stmt, AggScriptVersionDaily, scope)
    if from_date:
        stmt = stmt.where(AggScriptVersionDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggScriptVersionDaily.date <= to_date)

    stmt = stmt.order_by(AggScriptVersionDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_source_rollups(
    session: AsyncSession,
    scope: Scope,
    from_date: date | None,
    to_date: date | None,
) -> list[AggSourceDaily]:
    stmt = select(AggSourceDaily)
    stmt = _scoped(stmt, AggSourceDaily, scope)
    if from_date:
        stmt = stmt.where(AggSourceDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggSourceDaily.date <= to_date)

    stmt = stmt.order_by(AggSourceDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_bot_rollups(
    session: AsyncSession,
    scope: Scope,
    from_date: date | None,
    to_date: date | None,
) -> list[AggBotDaily]:
    stmt = select(AggBotDaily)
    stmt = _scoped(stmt, AggBotDaily, scope)
    if from_date:
        stmt = stmt.where(AggBotDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggBotDaily.date <= to_date)

    stmt = stmt.order_by(AggBotDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_compliance_rollups(
    session: AsyncSession,
    scope: Scope,
    from_date: date | None,
    to_date: date | None,
) -> list[AggComplianceDaily]:
    stmt = select(AggComplianceDaily)
    stmt = _scoped(stmt, AggComplianceDaily, scope)
    if from_date:
        stmt = stmt.where(AggComplianceDaily.date >= from_date)
    if to_date:
        stmt = stmt.where(AggComplianceDaily.date <= to_date)

    stmt = stmt.order_by(AggComplianceDaily.date.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


class PerformanceRow(NamedTuple):
    """One day x LLM provider latency percentile bucket."""

    date: date
    provider: str
    samples: int
    p50_turn_ms: float
    p95_turn_ms: float
    p99_turn_ms: float


# Operational latency telemetry, not a KPI: aggregated server-side so the
# percentiles are never computed in the browser. Reads the per-call telemetry
# table and joins calls only for its ``started_at`` timestamp. No KPI is derived
# from raw call columns here.
_PERFORMANCE_SQL = text("""
    SELECT date(c.started_at) AS day,
           COALESCE(p.llm_provider, 'unknown') AS provider,
           count(*) AS samples,
           COALESCE(percentile_cont(0.50) WITHIN GROUP (ORDER BY p.total_turn_ms), 0)
               AS p50_turn_ms,
           COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY p.total_turn_ms), 0)
               AS p95_turn_ms,
           COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY p.total_turn_ms), 0)
               AS p99_turn_ms
    FROM call_performance p
    JOIN calls c ON c.id = p.call_id
    WHERE c.started_at >= CAST(:from_ts AS timestamptz)
      AND c.started_at < CAST(:to_ts AS timestamptz)
      AND (:tenant_id IS NULL OR COALESCE(c.tenant_id, :unset_tenant) = :tenant_id)
    GROUP BY 1, 2
    ORDER BY 1, 2
""")


async def get_performance_rollups(
    session: AsyncSession,
    scope: Scope,
    from_ts: Any,
    to_ts: Any,
) -> list[PerformanceRow]:
    """Latency percentiles per day and LLM provider over ``[from_ts, to_ts)``."""
    res = await session.execute(
        _PERFORMANCE_SQL,
        {
            "from_ts": from_ts,
            "to_ts": to_ts,
            "tenant_id": scope.get("tenant_id"),
            "unset_tenant": UNSET_TENANT,
        },
    )
    return [PerformanceRow(*row) for row in res]
