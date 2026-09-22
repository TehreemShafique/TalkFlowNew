"""HTTP surface for transfers module (/api/v1/transfers) (Step 34)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_CALL_VIEW
from app.modules.transfers import service
from app.modules.transfers.schemas import (
    TransferCallbackRequest,
    TransferDTO,
    TransferListQuery,
    TransferRetryRequest,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/transfers", tags=["transfers"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_CALL_VIEW]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[TransferDTO])
async def list_transfers(
    query: Annotated[TransferListQuery, Depends()], actor: ViewGate, db: DbSession
):
    """List transfers with filtering and pagination (Step 34)."""
    return await service.list_transfers(db, actor, query)


@router.get("/failed", response_model=PagedResponse[TransferDTO])
async def list_failed_transfers(
    actor: ViewGate,
    db: DbSession,
    page: int = 1,
    page_size: int = 20,
):
    """List failed transfers recovery queue (Step 34)."""
    return await service.list_failed_transfers(
        db, actor, page=page, page_size=page_size
    )


@router.post("/{transfer_id}/retry", response_model=DataResponse[TransferDTO])
async def retry_transfer(
    transfer_id: uuid.UUID,
    payload: TransferRetryRequest,
    actor: ViewGate,
    db: DbSession,
):
    """Reschedule failed transfer retry attempt (Step 34)."""
    return await service.retry_transfer(db, actor, transfer_id, payload)


@router.post("/{transfer_id}/create-callback", response_model=DataResponse[TransferDTO])
async def create_callback(
    transfer_id: uuid.UUID,
    payload: TransferCallbackRequest,
    actor: ViewGate,
    db: DbSession,
):
    """Convert failed transfer to callback request (Step 34)."""
    return await service.create_callback(db, actor, transfer_id, payload)
