"""HTTP surface for the campaigns module (/api/v1/campaigns).

Every route carries an explicit permission gate (Rule R4): reads require
``campaign.view`` and lifecycle transitions require ``campaign.start``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_CAMPAIGN_START, PERM_CAMPAIGN_VIEW
from app.modules.campaigns import service
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignDTO,
    CampaignListQuery,
    CampaignStartResponse,
    CampaignStatsDTO,
    CampaignUpdate,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_CAMPAIGN_VIEW]))]
StartGate = Annotated[UserContext, Depends(require_permissions([PERM_CAMPAIGN_START]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[CampaignDTO])
async def list_campaigns(
    query: Annotated[CampaignListQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """List campaigns (scoped to the caller's access scope, Rule R5)."""
    return await service.list_campaigns(db, actor, query)


@router.post(
    "", response_model=DataResponse[CampaignDTO], status_code=status.HTTP_201_CREATED
)
async def create_campaign(
    payload: CampaignCreate,
    actor: ViewGate,
    db: DbSession,
):
    """Create a campaign; it always opens in ``draft`` until started."""
    return await service.create_campaign(db, actor, payload)


@router.get("/{campaign_id}", response_model=DataResponse[CampaignDTO])
async def get_campaign(
    campaign_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    return await service.get_campaign(db, actor, campaign_id)


@router.get("/{campaign_id}/stats", response_model=DataResponse[CampaignStatsDTO])
async def get_campaign_stats(
    campaign_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Today's counters + contact/qualification/transfer rates (PRD FR-11)."""
    return await service.get_campaign_stats(db, actor, campaign_id)


@router.put("/{campaign_id}", response_model=DataResponse[CampaignDTO])
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    actor: ViewGate,
    db: DbSession,
):
    return await service.update_campaign(db, actor, campaign_id, payload)


@router.post("/{campaign_id}/start", response_model=DataResponse[CampaignStartResponse])
async def start_campaign(
    campaign_id: uuid.UUID,
    actor: StartGate,
    db: DbSession,
):
    """Activate the campaign if the start guard passes (all gaps returned at once)."""
    return await service.start_campaign(db, actor, campaign_id)


@router.post("/{campaign_id}/pause", response_model=DataResponse[CampaignDTO])
async def pause_campaign(
    campaign_id: uuid.UUID,
    actor: StartGate,
    db: DbSession,
):
    return await service.pause_campaign(db, actor, campaign_id)


@router.post("/{campaign_id}/stop", response_model=DataResponse[CampaignDTO])
async def stop_campaign(
    campaign_id: uuid.UUID,
    actor: StartGate,
    db: DbSession,
):
    """Stop an active or paused campaign (keeps all bindings for a later start)."""
    return await service.stop_campaign(db, actor, campaign_id)


@router.post("/{campaign_id}/script", response_model=DataResponse[CampaignDTO])
async def bind_campaign_script(
    campaign_id: uuid.UUID,
    script_id: uuid.UUID,
    active_script_version_id: uuid.UUID,
    actor: StartGate,
    db: DbSession,
):
    """Bind an approved script version to a campaign."""
    return await service.bind_script(
        db, actor, campaign_id, script_id, active_script_version_id
    )
