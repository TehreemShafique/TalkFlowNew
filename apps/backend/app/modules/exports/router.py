"""HTTP surface for the export pipeline (/api/v1/exports).

Create/process/download mirror an analytics export run; READ of the history
requires ``export.view``, creating a run ``export.create``, and downloading the
artifact ``export.download`` (Rule R4).  Download responses stream the CSV with
a ``Content-Disposition`` attachment.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import (
    PERM_EXPORT_CREATE,
    PERM_EXPORT_DOWNLOAD,
    PERM_EXPORT_VIEW,
)
from app.modules.exports import service
from app.modules.exports.schemas import (
    ExportJobDTO,
    ExportListQuery,
    ExportRequest,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/exports", tags=["exports"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_EXPORT_VIEW]))]
CreateGate = Annotated[UserContext, Depends(require_permissions([PERM_EXPORT_CREATE]))]
DownloadGate = Annotated[
    UserContext, Depends(require_permissions([PERM_EXPORT_DOWNLOAD]))
]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[ExportJobDTO])
async def list_exports(
    query: Annotated[ExportListQuery, Depends()], actor: ViewGate, db: DbSession
):
    """Export history (spec 28.8)."""
    return await service.list_exports(db, actor, query)


@router.post(
    "", response_model=DataResponse[ExportJobDTO], status_code=status.HTTP_201_CREATED
)
async def create_export(payload: ExportRequest, actor: CreateGate, db: DbSession):
    """Request an export; processes it inline and returns the finished job."""
    return await service.create_export(db, actor, payload)


@router.get("/{job_id}", response_model=DataResponse[ExportJobDTO])
async def get_export(job_id: uuid.UUID, actor: ViewGate, db: DbSession):
    return await service.get_export(db, actor, job_id)


@router.get("/{job_id}/download")
async def download_export(job_id: uuid.UUID, actor: DownloadGate, db: DbSession):
    """Stream the ready CSV artifact (masked for non-PII tenants)."""
    data, filename = await service.download_export(db, actor, job_id)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
