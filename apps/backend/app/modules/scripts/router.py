"""HTTP API router surface for the scripts module (/api/v1/scripts)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_SCRIPT_APPROVE, PERM_SCRIPT_EDIT, PERM_SCRIPT_VIEW
from app.modules.scripts import service
from app.modules.scripts.schemas import (
    ScriptCreate,
    ScriptDiffDTO,
    ScriptDTO,
    ScriptListQuery,
    ScriptSimulationRequest,
    ScriptSimulationResultDTO,
    ScriptUpdate,
    ScriptVersionActivate,
    ScriptVersionCreate,
    ScriptVersionDTO,
    ScriptVersionReject,
    ScriptVersionSummaryDTO,
    ScriptVersionUpdate,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/scripts", tags=["scripts"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_VIEW]))]
EditGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_EDIT]))]
ApproveGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_APPROVE]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[ScriptDTO])
async def list_scripts(
    query: Annotated[ScriptListQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """List scripts for the script library view."""
    return await service.list_scripts(db, actor, query)


@router.post("", response_model=DataResponse[ScriptDTO], status_code=status.HTTP_201_CREATED)
async def create_script(
    payload: ScriptCreate,
    actor: EditGate,
    db: DbSession,
):
    """Create a new script container with version 1 in draft status."""
    return await service.create_script(db, actor, payload)


@router.get("/approvals", response_model=PagedResponse[dict[str, Any]])
async def list_approval_queue(
    actor: ViewGate,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List script versions in the approval queue."""
    return await service.list_approval_queue(db, actor, page=page, page_size=page_size)


@router.get("/{id}", response_model=DataResponse[ScriptDTO])
async def get_script(
    id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Get script overview and version history."""
    return await service.get_script(db, actor, id)


@router.patch("/{id}", response_model=DataResponse[ScriptDTO])
async def update_script(
    id: uuid.UUID,
    payload: ScriptUpdate,
    actor: EditGate,
    db: DbSession,
):
    """Update script metadata (name, description, language)."""
    return await service.update_script(db, actor, id, payload)


@router.post("/{id}/duplicate", response_model=DataResponse[ScriptDTO], status_code=status.HTTP_201_CREATED)
async def duplicate_script(
    id: uuid.UUID,
    actor: EditGate,
    db: DbSession,
):
    """Duplicate a script creating a copy with version 1 in draft status."""
    return await service.duplicate_script(db, actor, id)


@router.get("/{id}/versions", response_model=DataResponse[list[ScriptVersionSummaryDTO]])
async def list_versions(
    id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """List all version summaries for a script."""
    return await service.list_versions(db, actor, id)


@router.post("/{id}/versions", response_model=DataResponse[ScriptVersionDTO], status_code=status.HTTP_201_CREATED)
async def create_version(
    id: uuid.UUID,
    payload: ScriptVersionCreate,
    actor: EditGate,
    db: DbSession,
):
    """Create a new draft version for script."""
    return await service.create_version(db, actor, id, payload)


@router.get("/{id}/versions/{v}", response_model=DataResponse[ScriptVersionDTO])
async def get_version(
    id: uuid.UUID,
    v: str,
    actor: ViewGate,
    db: DbSession,
):
    """Get a specific version snapshot."""
    return await service.get_version(db, actor, id, v)


@router.patch("/{id}/versions/{v}", response_model=DataResponse[ScriptVersionDTO])
async def update_version(
    id: uuid.UUID,
    v: str,
    payload: ScriptVersionUpdate,
    actor: EditGate,
    db: DbSession,
):
    """Update draft version content."""
    return await service.update_version(db, actor, id, v, payload)


@router.post("/{id}/versions/{v}/submit", response_model=DataResponse[ScriptVersionDTO])
async def submit_version(
    id: uuid.UUID,
    v: str,
    actor: EditGate,
    db: DbSession,
):
    """Submit draft version for approval (draft -> pending_approval)."""
    return await service.submit_version(db, actor, id, v)


@router.post("/{id}/versions/{v}/approve", response_model=DataResponse[ScriptVersionDTO])
async def approve_version(
    id: uuid.UUID,
    v: str,
    actor: ApproveGate,
    db: DbSession,
):
    """Approve script version (pending_approval -> approved)."""
    return await service.approve_version(db, actor, id, v)


@router.post("/{id}/versions/{v}/reject", response_model=DataResponse[ScriptVersionDTO])
async def reject_version(
    id: uuid.UUID,
    v: str,
    payload: ScriptVersionReject,
    actor: ApproveGate,
    db: DbSession,
):
    """Reject script version (pending_approval -> draft)."""
    return await service.reject_version(db, actor, id, v, payload)


@router.post("/{id}/versions/{v}/activate", response_model=DataResponse[ScriptVersionDTO])
async def activate_version(
    id: uuid.UUID,
    v: str,
    payload: ScriptVersionActivate,
    actor: ApproveGate,
    db: DbSession,
):
    """Activate approved script version (approved -> active)."""
    return await service.activate_version(db, actor, id, v, payload)


@router.get("/{id}/versions/{v}/diff", response_model=DataResponse[ScriptDiffDTO])
async def diff_version(
    id: uuid.UUID,
    v: str,
    actor: ViewGate,
    db: DbSession,
    against: int = Query(..., alias="against"),
):
    """Compare version v against version N."""
    return await service.diff_version(db, actor, id, v, against)


@router.post("/{id}/versions/{v}/simulate", response_model=DataResponse[ScriptSimulationResultDTO])
async def simulate_version(
    id: uuid.UUID,
    v: str,
    payload: ScriptSimulationRequest,
    actor: ViewGate,
    db: DbSession,
):
    """Simulate conversation flow through version node graph."""
    return await service.simulate_version(db, actor, id, v, payload)


@router.post("/{id}/simulate", response_model=DataResponse[ScriptSimulationResultDTO])
async def simulate_latest(
    id: uuid.UUID,
    payload: ScriptSimulationRequest,
    actor: ViewGate,
    db: DbSession,
):
    """Simulate conversation flow using current script version."""
    script_res = await service.get_script(db, actor, id)
    v_str = str(script_res.data.current_version)
    return await service.simulate_version(db, actor, id, v_str, payload)
