"""HTTP surface for the verifier workspace (/api/v1/verifier) (Step 35)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_VERIFIER_WORKSPACE
from app.modules.verifier import service
from app.modules.verifier.schemas import (
    VerifierAcceptContextDTO,
    VerifierAvailabilityRequest,
    VerifierDispositionRequest,
    VerifierQueueItemDTO,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/verifier", tags=["verifier"])

VerifierGate = Annotated[
    UserContext, Depends(require_permissions([PERM_VERIFIER_WORKSPACE]))
]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/queue", response_model=DataResponse[list[VerifierQueueItemDTO]])
async def get_verifier_queue(actor: VerifierGate, db: DbSession):
    """List pending calls/transfers waiting in queue (Step 35)."""
    return await service.get_verifier_queue(db, actor)


@router.post("/availability", response_model=DataResponse[dict[str, Any]])
async def set_verifier_availability(
    payload: VerifierAvailabilityRequest, actor: VerifierGate, db: DbSession
):
    """Toggle verifier status (available | busy | offline) and refresh presence (Step 35)."""
    return await service.set_availability(db, actor, payload)


@router.post(
    "/calls/{call_id}/accept", response_model=DataResponse[VerifierAcceptContextDTO]
)
async def accept_verifier_call(call_id: uuid.UUID, actor: VerifierGate, db: DbSession):
    """Accept incoming transfer and return full context in ONE payload (<300ms) (Step 35)."""
    return await service.accept_call(db, actor, call_id)


@router.post("/calls/{call_id}/reject", response_model=DataResponse[dict[str, Any]])
async def reject_verifier_call(call_id: uuid.UUID, actor: VerifierGate, db: DbSession):
    """Reject transfer offer (Step 35)."""
    return await service.reject_call(db, actor, call_id)


@router.post(
    "/calls/{call_id}/disposition", response_model=DataResponse[dict[str, Any]]
)
async def disposition_verifier_call(
    call_id: uuid.UUID,
    payload: VerifierDispositionRequest,
    actor: VerifierGate,
    db: DbSession,
):
    """Set final disposition on verified call (Step 35)."""
    return await service.disposition_call(db, actor, call_id, payload)


@router.get("/history", response_model=PagedResponse[dict[str, Any]])
async def get_verifier_history(
    actor: VerifierGate, db: DbSession, page: int = 1, page_size: int = 20
):
    """List verifier's own completed verifications history (Step 35)."""
    return await service.get_verifier_history(db, actor, page=page, page_size=page_size)
