"""HTTP surface for the leads module (/api/v1/leads).

Explicit permission gates on every route (Rule R4): ``lead.view`` reads,
``lead.edit`` single-lead writes, ``lead.import`` the wizard.  The literal
``/import`` route group is registered BEFORE the ``{lead_id}`` path-param
routes so Starlette matches the literal ("import" never falls into the UUID
param and 422s).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import (
    PERM_CAMPAIGN_START,
    PERM_LEAD_EDIT,
    PERM_LEAD_IMPORT,
    PERM_LEAD_VIEW,
)
from app.modules.leads import service
from app.modules.leads.schemas import (
    BulkAssignRequest,
    ImportJobDTO,
    ImportUploadResponse,
    LeadBatchDTO,
    LeadCreate,
    LeadDTO,
    LeadListQuery,
    LeadUpdate,
    MappingRequest,
    UpdateBatchCampaignRequest,
    VicidialRunRequest,
    VicidialRunResultDTO,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/leads", tags=["leads"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_VIEW]))]
EditGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_EDIT]))]
ImportGate = Annotated[UserContext, Depends(require_permissions([PERM_LEAD_IMPORT]))]
# Starting a dialer run authorizes outbound calling, so it takes the campaign
# start permission rather than lead edit.
DialGate = Annotated[
    UserContext,
    Depends(require_permissions([PERM_LEAD_EDIT, PERM_CAMPAIGN_START])),
]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/batches", response_model=DataResponse[list[LeadBatchDTO]])
async def list_lead_batches(actor: ViewGate, db: DbSession):
    """List all imported lead batches/files with metadata."""
    return await service.list_batches(db, actor)


@router.patch(
    "/batches/{batch_id}/campaign", response_model=DataResponse[dict[str, Any]]
)
async def update_batch_campaign(
    batch_id: uuid.UUID,
    payload: UpdateBatchCampaignRequest,
    actor: EditGate,
    db: DbSession,
):
    """Assign or update the target campaign for an imported lead batch."""
    return await service.update_batch_campaign(db, actor, batch_id, payload.campaign_id)


@router.delete("/batches/{batch_id}", response_model=DataResponse[dict[str, Any]])
async def delete_lead_batch(
    batch_id: uuid.UUID,
    actor: EditGate,
    db: DbSession,
):
    """Delete an imported lead batch file and all its associated lead records from DB."""
    return await service.delete_batch(db, actor, str(batch_id))


@router.patch(
    "/batches/{batch_id}/vicidial-run",
    response_model=DataResponse[VicidialRunResultDTO],
)
async def set_batch_vicidial_run(
    batch_id: uuid.UUID,
    payload: VicidialRunRequest,
    actor: DialGate,
    db: DbSession,
):
    """Start or stop the VICIdial run for an imported lead list.

    Starting pushes the list's leads into the dialer hopper and bumps the run
    count; stopping records the interruption in TalkFlow (the non-agent API has
    no list pause). Gated on ``campaign.start`` because it authorizes dialing.
    """
    return await service.set_vicidial_run(
        db,
        actor,
        batch_id,
        is_active=payload.is_active,
        vicidial_list_id=payload.vicidial_list_id,
        campaign_id=payload.campaign_id,
    )


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
async def commit_import(
    job_id: uuid.UUID,
    actor: ImportGate,
    db: DbSession,
    idempotency_key: Annotated[str | None, Depends(lambda: None)] = None,
):
    """STEP 5: import the surviving rows in batches of 1000 (Step 28)."""
    return await service.commit_import(
        db, actor, job_id, idempotency_key=idempotency_key
    )


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


@router.post(
    "", response_model=DataResponse[LeadDTO], status_code=status.HTTP_201_CREATED
)
async def create_lead(payload: LeadCreate, actor: EditGate, db: DbSession):
    return await service.create_lead(db, actor, payload)


@router.post("/bulk-assign", response_model=DataResponse[dict[str, Any]])
async def bulk_assign_leads(payload: BulkAssignRequest, actor: EditGate, db: DbSession):
    """Bulk assign leads to a campaign or user (Step 27)."""
    return await service.bulk_assign_leads(db, actor, payload)


@router.get("/{lead_id}", response_model=DataResponse[LeadDTO])
async def get_lead(lead_id: uuid.UUID, actor: ViewGate, db: DbSession):
    return await service.get_lead(db, actor, lead_id)


@router.patch("/{lead_id}", response_model=DataResponse[LeadDTO])
async def update_lead(
    lead_id: uuid.UUID, payload: LeadUpdate, actor: EditGate, db: DbSession
):
    return await service.update_lead(db, actor, lead_id, payload)
