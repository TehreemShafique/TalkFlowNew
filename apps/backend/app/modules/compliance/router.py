"""HTTP API router for compliance module (/api/v1/compliance)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_SCRIPT_EDIT, PERM_SCRIPT_VIEW
from app.modules.compliance import service
from app.modules.compliance.schemas import (
    ComplianceProfileDTO,
    ComplianceRuleUpdate,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/compliance", tags=["compliance"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_VIEW]))]
EditGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_EDIT]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/profiles", response_model=PagedResponse[ComplianceProfileDTO])
async def list_profiles(
    actor: ViewGate,
    db: DbSession,
):
    """List compliance profiles."""
    return await service.list_profiles(db, actor)


@router.get("/profiles/{id}", response_model=DataResponse[ComplianceProfileDTO])
async def get_profile(
    id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Get a compliance profile with rules."""
    return await service.get_profile(db, actor, id)


@router.patch(
    "/profiles/{id}/rules/{rule_key}", response_model=DataResponse[ComplianceProfileDTO]
)
async def update_rule_mode(
    id: uuid.UUID,
    rule_key: str,
    payload: ComplianceRuleUpdate,
    actor: EditGate,
    db: DbSession,
):
    """Update compliance rule mode (enforce, warn, off). Require MASTER_ADMIN for warn/off."""
    return await service.update_rule_mode(db, actor, id, rule_key, payload)
