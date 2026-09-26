"""HTTP surface for the recordings module (/api/v1/recordings)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_auth
from app.core.permissions import has_permission
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
    PERM_RECORDING_PURGE,
    PERM_RECORDING_READ,
)
from app.modules.recordings.schemas import (
    PurgeRequest,
    QaAuditRequest,
    RecordingDTO,
    RecordingListQuery,
)
from app.packages.contracts.base import DataResponse, PagedResponse
from app.packages.contracts.enums import AuditResult
from app.packages.storage.provider import LocalStorageProvider, get_storage_provider

router = APIRouter(prefix="/recordings", tags=["recordings"])

Db = Depends(get_db)
Auth = Depends(require_auth)


def _require_hidden(user: UserContext, permission: str) -> None:
    """Hide the existence of recordings from principals without the gate."""
    if not has_permission(user.permissions, permission):
        raise RecordingNotFoundError("recording.not_found")


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
    _require_hidden(user, PERM_RECORDING_READ)
    return await service.list_recordings(db, user, query)


@router.get("/{recording_id}", response_model=DataResponse[RecordingDTO])
async def get_recording(
    recording_id: uuid.UUID,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    _require_hidden(user, PERM_RECORDING_READ)
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
    return await service.get_playback_url(db, user, recording_id)


@router.get("/{recording_id}/download", response_model=str)
async def get_download_url(
    recording_id: uuid.UUID,
    user: UserContext = Auth,
    db: AsyncSession = Db,
):
    return await service.get_download_url(db, user, recording_id)


def _local_path_for_grant(payload: dict) -> Path:
    provider = get_storage_provider()
    if not isinstance(provider, LocalStorageProvider):
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    path: Path = provider._path(subject)
    if not path.is_file():
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    return path


@router.get("/stream/{token}")
async def stream_audio(token: str, response: Response):
    """Serve the audio bytes for a signed playback grant (local provider)."""
    try:
        payload = decode_signed_grant(token)
    except jwt.PyJWTError:
        raise RecordingSourceUnavailableError("recording.source_unavailable") from None
    if payload.get("purpose") != "stream":
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    path = _local_path_for_grant(payload)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Content-Type"] = "audio/wav"
    return FileResponse(path, media_type="audio/wav")


async def _audit_grant_use(
    db: AsyncSession,
    payload: dict,
    *,
    action: str,
    result: AuditResult,
) -> None:
    actor_id = payload.get("actor_id")
    if isinstance(actor_id, str):
        try:
            actor_id = uuid.UUID(actor_id)
        except ValueError:
            actor_id = None
    await write_audit(
        db,
        actor_id=actor_id,
        actor_role=payload.get("actor_role") or "unknown",
        action=action,
        resource_type="recording",
        resource_id=str(payload.get("recording_id") or payload.get("sub")),
        result=result,
        details={"jti": payload.get("jti"), "call_id": payload.get("call_id")},
    )
    await db.commit()


@router.get("/download/{token}")
async def download_audio(token: str, db: AsyncSession = Db):
    """Single-use signed download for the local provider."""
    try:
        payload = decode_signed_grant(token)
    except jwt.PyJWTError:
        raise RecordingDownloadUnauthorizedError(
            "recording.download_unauthorized"
        ) from None
    if payload.get("purpose") != "download":
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    if not await token_store.consume(payload["jti"]):
        await _audit_grant_use(
            db, payload, action="recording.download", result=AuditResult.DENIED
        )
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    path = _local_path_for_grant(payload)
    await _audit_grant_use(
        db, payload, action="recording.download_consumed", result=AuditResult.SUCCESS
    )
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=path.name,
        headers={"Cache-Control": "no-store, private"},
    )


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
    _require_hidden(user, PERM_QA_AUDIT)
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
    _require_hidden(user, PERM_RECORDING_PURGE)
    return await service.purge_recording(db, user, recording_id, body or PurgeRequest())
