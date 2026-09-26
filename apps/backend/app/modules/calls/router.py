"""HTTP surface for the calls module (/api/v1/calls).

Every route carries an explicit permission gate (Rule R4): reads require
``call.view`` and disposition writes require ``call.disposition``.  The
``/{call_id}/live`` route is placed before ``/{call_id}`` to avoid shadowing
(ADR-02).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_CALL_DISPOSITION, PERM_CALL_VIEW
from app.modules.calls import service
from app.modules.calls.schemas import (
    CallDTO,
    CallListQuery,
    DispositionUpdate,
    LiveCallDTO,
    PerformanceDTO,
    ScriptPathNodeDTO,
    TimelineEventDTO,
    TranscriptTurnDTO,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/calls", tags=["calls"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_CALL_VIEW]))]
DispoGate = Annotated[
    UserContext, Depends(require_permissions([PERM_CALL_DISPOSITION]))
]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[CallDTO])
async def list_calls(
    query: Annotated[CallListQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Paginated CDR (section 25)."""
    return await service.list_calls(db, actor, query)


@router.get("/live", response_model=DataResponse[list[LiveCallDTO]])
async def list_live_calls(
    actor: ViewGate,
    db: DbSession,
):
    """Calls currently in the dialer loop (section 22)."""
    return await service.list_live_calls(db, actor)


@router.get("/{call_id}", response_model=DataResponse[CallDTO])
async def get_call(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Call detail with qualification, consent and transfer panels (section 26)."""
    return await service.get_call(db, actor, call_id)


@router.patch(
    "/{call_id}/disposition",
    response_model=DataResponse[CallDTO],
)
async def update_disposition(
    call_id: uuid.UUID,
    payload: DispositionUpdate,
    actor: DispoGate,
    db: DbSession,
):
    """Write the call's final disposition + audit + outbox event (Rule R8)."""
    return await service.update_disposition(db, actor, call_id, payload)


@router.get(
    "/{call_id}/transcript",
    response_model=DataResponse[list[TranscriptTurnDTO]],
)
async def get_transcript(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    return await service.get_transcript(db, actor, call_id)


@router.get(
    "/{call_id}/timeline",
    response_model=DataResponse[list[TimelineEventDTO]],
)
async def get_timeline(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Millisecond event stream across categories (section 26.6)."""
    return await service.get_timeline(db, actor, call_id)


@router.get(
    "/{call_id}/performance",
    response_model=DataResponse[PerformanceDTO],
)
async def get_performance(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    return await service.get_performance(db, actor, call_id)


@router.get(
    "/{call_id}/script-path",
    response_model=DataResponse[list[ScriptPathNodeDTO]],
)
async def get_script_path(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Node sequence the call traversed (section 26.4)."""
    return await service.get_script_path(db, actor, call_id)


# ---------------------------------------------------------------------------
# Step 37 Call Recording Serving
# ---------------------------------------------------------------------------


@router.get("/{call_id}/recording")
async def get_call_recording(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Fetch recording details for call (Step 37)."""
    from app.modules.recordings import service as rec_service

    return await rec_service.get_recording_by_call_id(db, actor, call_id)


@router.get("/{call_id}/recording/playback-url")
async def get_call_playback_url(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """5-minute presigned playback URL + audited recording.played (Step 37)."""
    from app.modules.recordings import service as rec_service

    url = await rec_service.get_call_playback_url(db, actor, call_id)
    return {"data": {"url": url}}


@router.post("/{call_id}/recording/download-token")
async def get_call_download_token(
    call_id: uuid.UUID,
    actor: ViewGate,
    db: DbSession,
):
    """Single-use download token + audited recording.downloaded (Step 37)."""
    from app.modules.recordings import service as rec_service

    token = await rec_service.get_call_download_token(db, actor, call_id)
    return {"data": {"token": token}}
