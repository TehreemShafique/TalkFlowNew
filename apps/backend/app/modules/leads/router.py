"""HTTP surface for the leads module (/api/v1/leads).

Explicit permission gates on every route (Rule R4): ``lead.view`` reads,
``lead.edit`` single-lead writes, ``lead.import`` the wizard.  The literal
``/import`` route group is registered BEFORE the ``{lead_id}`` path-param
routes so Starlette matches the literal ("import" never falls into the UUID
param and 422s).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_LEAD_EDIT, PERM_LEAD_IMPORT, PERM_LEAD_VIEW
from app.modules.leads import service
from app.modules.leads.schemas import (
    ImportJobDTO,
    ImportUploadResponse,
    LeadCreate,
    LeadDTO,
    LeadListQuery,
    LeadUpdate,
    MappingRequest,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/leads", tags=["leads"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_VIEW]))]
EditGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_EDIT]))]
ImportGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_IMPORT]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Import wizard (literal paths registered before {lead_id} routes)
# ---------------------------------------------------------------------------
@router.get("/import/{job_id}", response_model=DataResponse[ImportJobDTO])
async def get_import_job(job_id: uuid.UUID, actor: ImportGate, db: DbSession):
    return await service.get_import_job(db, actor, job_id)


@router.post("/import/{job_id}/mapping", response_model=DataResponse[ImportJobDTO])
async def save_import_mapping(
    job_id: uuid.UUID, payload: MappingRequest, actor: ImportGate, db: DbSession
):
    """STEP 3-4: attach a column mapping, classify rows, publish the preview."""
    return await service.save_mapping(db, actor, job_id, payload)


@router.post("/import/{job_id}/commit", response_model=DataResponse[ImportJobDTO])
async def commit_import(job_id: uuid.UUID, actor: ImportGate, db: DbSession):
    """STEP 5: import the surviving rows (idempotent - safe to retry)."""
    return await service.commit_import(db, actor, job_id)


@router.get("/import/{job_id}/errors")
async def get_import_errors(job_id: uuid.UUID, actor: ViewGate, db: DbSession):
    """Stream the skipped-rows CSV report (row number + reason)."""
    data, filename = await service.get_error_report(db, actor, job_id)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/import",
    response_model=DataResponse[ImportUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_import(
    file: Annotated[UploadFile, File(description="UTF-8 CSV with a header row")],
    actor: ImportGate,
    db: DbSession,
):
    """STEP 1-2: upload a CSV, infer its columns, park it for mapping."""
    return await service.upload_import(db, actor, file)


# ---------------------------------------------------------------------------
# Lead registry
# ---------------------------------------------------------------------------
@router.get("", response_model=PagedResponse[LeadDTO])
async def list_leads(
    query: Annotated[LeadListQuery, Depends()], actor: ViewGate, db: DbSession
):
    return await service.list_leads(db, actor, query)


@router.post("", response_model=DataResponse[LeadDTO], status_code=status.HTTP_201_CREATED)
async def create_lead(payload: LeadCreate, actor: EditGate, db: DbSession):
    return await service.create_lead(db, actor, payload)


@router.get("/{lead_id}", response_model=DataResponse[LeadDTO])
async def get_lead(lead_id: uuid.UUID, actor: ViewGate, db: DbSession):
    return await service.get_lead(db, actor, lead_id)


@router.patch("/{lead_id}", response_model=DataResponse[LeadDTO])
async def update_lead(
    lead_id: uuid.UUID, payload: LeadUpdate, actor: EditGate, db: DbSession
):
    return await service.update_lead(db, actor, lead_id, payload)