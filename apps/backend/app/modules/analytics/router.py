"""HTTP surface for Analytics (/api/v1/analytics) (Step 39).

Rule: no analytics endpoint derives a KPI from raw ``calls``. All KPI reads fold
over pre-aggregated ``agg_*`` tables; ``/performance`` reads operational latency
telemetry, which has no PRD report and therefore no rollup.

Rule R5: every handler resolves its own read scope from the authenticated
principal, so no query can default to "all tenants".
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_ANALYTICS_VIEW
from app.modules.analytics import policies, service
from app.modules.analytics.schemas import (
    AnalyticsDateQuery,
    AnalyticsSummaryDTO,
    BotAggDTO,
    CampaignAggDTO,
    ComplianceAggDTO,
    PerformanceAggDTO,
    ScriptVersionAggDTO,
    SourceAggDTO,
)
from app.packages.contracts.base import DataResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_ANALYTICS_VIEW]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary", response_model=DataResponse[AnalyticsSummaryDTO])
async def get_analytics_summary(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Aggregate summary funnel metrics from agg_campaign_daily (Step 39)."""
    return await service.get_summary(db, policies.resolve_scope_constraints(actor), query)


@router.get("/campaigns", response_model=DataResponse[list[CampaignAggDTO]])
async def get_campaign_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Campaign daily rollups from agg_campaign_daily (Step 39)."""
    return await service.get_campaign_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )


@router.get("/scripts", response_model=DataResponse[list[ScriptVersionAggDTO]])
async def get_script_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Script version daily rollups from agg_script_version_daily (Step 39)."""
    return await service.get_script_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )


@router.get("/sources", response_model=DataResponse[list[SourceAggDTO]])
async def get_source_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Lead source daily rollups from agg_source_daily (Step 39)."""
    return await service.get_source_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )


@router.get("/bot", response_model=DataResponse[list[BotAggDTO]])
async def get_bot_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Bot daily rollups from agg_bot_daily (Step 39)."""
    return await service.get_bot_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )


@router.get("/compliance", response_model=DataResponse[list[ComplianceAggDTO]])
async def get_compliance_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Compliance daily rollups from agg_compliance_daily (Step 39)."""
    return await service.get_compliance_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )


@router.get("/performance", response_model=DataResponse[list[PerformanceAggDTO]])
async def get_performance_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """LLM turn-latency percentiles per day and provider (docs/metrics.md)."""
    return await service.get_performance_analytics(
        db, policies.resolve_scope_constraints(actor), query
    )
