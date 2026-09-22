"""HTTP surface for Analytics (/api/v1/analytics) (Step 39).

Rule: NO analytics endpoint in this router queries raw `calls`. All reads fold
over pre-aggregated agg_* tables.
"""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_REPORTING_VIEW
from app.modules.analytics import service
from app.modules.analytics.schemas import (
    AnalyticsDateQuery,
    AnalyticsSummaryDTO,
    BotAggDTO,
    CampaignAggDTO,
    ComplianceAggDTO,
    ScriptVersionAggDTO,
    SourceAggDTO,
)
from app.packages.contracts.base import DataResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_REPORTING_VIEW]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/summary", response_model=DataResponse[AnalyticsSummaryDTO])
async def get_analytics_summary(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Aggregate summary funnel metrics from agg_campaign_daily (Step 39)."""
    return await service.get_summary(db, query)


@router.get("/campaigns", response_model=DataResponse[list[CampaignAggDTO]])
async def get_campaign_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Campaign daily rollups from agg_campaign_daily (Step 39)."""
    return await service.get_campaign_analytics(db, query)


@router.get("/scripts", response_model=DataResponse[list[ScriptVersionAggDTO]])
async def get_script_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Script version daily rollups from agg_script_version_daily (Step 39)."""
    return await service.get_script_analytics(db, query)


@router.get("/sources", response_model=DataResponse[list[SourceAggDTO]])
async def get_source_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Lead source daily rollups from agg_source_daily (Step 39)."""
    return await service.get_source_analytics(db, query)


@router.get("/bot", response_model=DataResponse[list[BotAggDTO]])
async def get_bot_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Bot daily rollups from agg_bot_daily (Step 39)."""
    return await service.get_bot_analytics(db, query)


@router.get("/compliance", response_model=DataResponse[list[ComplianceAggDTO]])
async def get_compliance_analytics(
    query: Annotated[AnalyticsDateQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Compliance daily rollups from agg_compliance_daily (Step 39)."""
    return await service.get_compliance_analytics(db, query)
