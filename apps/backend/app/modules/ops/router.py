"""HTTP surface for Operations Surface (/api/v1/health, /alerts, /search, /integrations, /notifications) (Step 51)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_auth
from app.modules.ops import service
from app.modules.ops.schemas import (
    AlertDTO,
    HealthCheckResponseDTO,
    IntegrationDTO,
    NotificationDTO,
    SearchResultResponseDTO,
)
from app.packages.contracts.base import DataResponse

router = APIRouter(tags=["ops"])

AuthGate = Annotated[UserContext, Depends(require_auth)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/health", response_model=HealthCheckResponseDTO)
async def get_health_status(db: DbSession):
    """Health probes including VICIdial API & MySQL cards (Step 51)."""
    return await service.get_health_status(db)


@router.get("/alerts", response_model=DataResponse[list[AlertDTO]])
async def get_alerts(actor: AuthGate, db: DbSession):
    """System alert log (Step 51)."""
    return await service.get_alerts(db)


@router.get("/search", response_model=SearchResultResponseDTO)
async def global_search(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    actor: AuthGate,
    db: DbSession,
    type: str | None = None,
):
    """Unified global search with audited phone lookups (Step 51)."""
    return await service.global_search(db, actor, q, type)


@router.get("/integrations", response_model=DataResponse[list[IntegrationDTO]])
async def get_integrations(actor: AuthGate, db: DbSession):
    """Integration configurations and status (Step 51)."""
    return await service.get_integrations(db)


@router.get("/notifications", response_model=DataResponse[list[NotificationDTO]])
async def get_notifications(actor: AuthGate, db: DbSession):
    """Notification history log (Step 51)."""
    return await service.get_notifications(db, actor)
