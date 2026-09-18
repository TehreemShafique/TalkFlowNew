"""HTTP surface for the suppression module (/api/v1/suppression).

Reads (list/check) require ``suppression.view``; adds require
``suppression.add``; the DELETE - a soft removal - is gated to
``suppression.remove``, which is only held by the ADMIN roles (spec 19.4:
removal is MASTER ADMIN only).  The literal ``check`` / ``import`` routes are
registered before the ``{entry_id}`` path parameter.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import (
    PERM_SUPPRESSION_ADD,
    PERM_SUPPRESSION_REMOVE,
    PERM_SUPPRESSION_VIEW,
)
from app.modules.suppression import service
from app.modules.suppression.schemas import (
    SuppressionCheckDTO,
    SuppressionEntryCreate,
    SuppressionEntryDTO,
    SuppressionImportResult,
    SuppressionListQuery,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/suppression", tags=["suppression"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_SUPPRESSION_VIEW]))]
AddGate = Annotated[UserContext, Depends(require_permissions([PERM_SUPPRESSION_ADD]))]
RemoveGate = Annotated[
    UserContext, Depends(require_permissions([PERM_SUPPRESSION_REMOVE]))
]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/check", response_model=DataResponse[SuppressionCheckDTO])
async def check_suppression(
    phone: Annotated[str, Query(description="US number to pre-check before dialing")],
    actor: ViewGate,
    db: DbSession,
):
    """Is this number blocked? Returns the reason when it is (spec 19.4)."""
    return await service.check_phone(db, actor, phone)


@router.post(
    "/import",
    response_model=DataResponse[SuppressionImportResult],
    status_code=status.HTTP_201_CREATED,
)
async def import_suppression_csv(
    file: Annotated[UploadFile, File(description="CSV with a phone column")],
    actor: AddGate,
    db: DbSession,
):
    """Bulk DNC upload (spec 14 SUPPRESSION: POST /suppression/import)."""
    return await service.import_csv(db, actor, file)


@router.get("", response_model=PagedResponse[SuppressionEntryDTO])
async def list_suppression(
    query: Annotated[SuppressionListQuery, Depends()], actor: ViewGate, db: DbSession
):
    return await service.list_entries(db, actor, query)


@router.post(
    "", response_model=DataResponse[SuppressionEntryDTO], status_code=status.HTTP_201_CREATED
)
async def add_suppression(
    payload: SuppressionEntryCreate, actor: AddGate, db: DbSession
):
    return await service.add_entry(db, actor, payload)


@router.delete("/{entry_id}", response_model=DataResponse[SuppressionEntryDTO])
async def remove_suppression(
    entry_id: uuid.UUID, actor: RemoveGate, db: DbSession
):
    """Soft-remove an active entry (keeps the audit trail + sync event)."""
    return await service.remove_entry(db, actor, entry_id)