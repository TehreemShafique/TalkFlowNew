"""HTTP surface for the recordings module (/api/v1/recordings)."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_auth
from app.core.redis import token_store
from app.core.security import decode_signed_grant
from app.modules.recordings import service
from app.modules.recordings.errors import (
    RecordingDownloadUnauthorizedError,
    RecordingNotFoundError,
    RecordingSourceUnavailableError,
)
from app.modules.recordings.policies import (
    PERM_QA_AUDIT,
    PERM_RECORDING_DOWNLOAD,
    PERM_RECORDING_PLAY,
    PERM_RECORDING_PURGE,
    PERM_RECORDING_VIEW,
)
from app.modules.recordings.schemas import (
    PurgeRequest,
    QaAuditRequest,
    RecordingDTO,
    RecordingListQuery,
)
from app.packages.contracts.base import DataResponse, PagedResponse
from app.packages.storage.provider import LocalStorageProvider, get_storage_provider

router = APIRouter(prefix="/recordings", tags=["recordings"])

Db = Depends(get_db)
Auth = Depends(require_auth)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=PagedResponse[RecordingDTO])
async def list_recordings(
    query: Annotated[RecordingListQuery, Depends()],
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    """List recordings (scoped to the caller's access scope, Rule R5)."""
    if not PERM_RECORDING_VIEW in user.permissions:
        raise RecordingNotFoundError("recording.not_found")  # 404, not 403: hide existence
    return await service.list_recordings(db, user, query)


@router.get("/{recording_id}", response_model=DataResponse[RecordingDTO])
async def get_recording(
    recording_id: uuid.UUID,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    if PERM_RECORDING_VIEW not in user.permissions:
        raise RecordingNotFoundError("recording.not_found")
    return await service.get_recording(db, user, recording_id)


# ---------------------------------------------------------------------------
# Streaming / download
# ---------------------------------------------------------------------------

@router.get("/{recording_id}/stream", response_model=str)
async def get_stream_url(
    recording_id: uuid.UUID,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    """Signed playback grant for the audio element (<audio> can't send headers)."""
    if PERM_RECORDING_PLAY not in user.permissions:
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    return await service.get_playback_url(db, user, recording_id)


@router.get("/{recording_id}/download", response_model=str)
async def get_download_url(
    recording_id: uuid.UUID,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    if PERM_RECORDING_DOWNLOAD not in user.permissions:
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    return await service.get_download_url(db, user, recording_id)


@router.get("/stream/{token}")
async def stream_audio(token: str, response: Response):
    """Serve the audio bytes for a signed playback grant (local provider)."""
    try:
        payload = decode_signed_grant(token)
    except jwt.PyJWTError:
        raise RecordingSourceUnavailableError("recording.source_unavailable") from None
    if payload.get("purpose") != "stream":
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    provider = get_storage_provider()
    if not isinstance(provider, LocalStorageProvider):
        # S3/MinIO handles streaming via presigned URLs instead.
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    path: Path = provider._path(payload["sub"])
    response.headers["Content-Type"] = "audio/wav"
    return FileResponse(path, media_type="audio/wav")


@router.get("/download/{token}")
async def download_audio(token: str):
    """Single-use signed download for the local provider."""
    try:
        payload = decode_signed_grant(token)
    except jwt.PyJWTError:
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized") from None
    if payload.get("purpose") != "download":
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    if not await token_store.consume(payload["jti"]):
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    provider = get_storage_provider()
    if not isinstance(provider, LocalStorageProvider):
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    path: Path = provider._path(payload["sub"])
    return FileResponse(path, media_type="audio/wav", filename=path.name)


# ---------------------------------------------------------------------------
# QA / compliance audit
# ---------------------------------------------------------------------------

@router.post("/{recording_id}/qa-audit", response_model=DataResponse[RecordingDTO])
async def qa_audit_recording(
    recording_id: uuid.UUID,
    body: QaAuditRequest,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    """Persist QA score, status and compliance checklist flags (scorecard modal)."""
    if PERM_QA_AUDIT not in user.permissions:
        raise RecordingNotFoundError("recording.not_found")
    return await service.save_qa_audit(db, user, recording_id, body)


# ---------------------------------------------------------------------------
# Purge (retention / ER-only destroy)
# ---------------------------------------------------------------------------

@router.post("/{recording_id}/purge", status_code=status.HTTP_200_OK)
async def purge_recording(
    recording_id: uuid.UUID,
    body: PurgeRequest | None = None,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    if PERM_RECORDING_PURGE not in user.permissions:
        raise RecordingNotFoundError("recording.not_found")
    return await service.purge_recording(db, user, recording_id, body or PurgeRequest())