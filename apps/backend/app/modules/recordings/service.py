"""Recording service - orchestrates repository + policies + storage + audit.

All mutations (purge) are written to the database synchronously with their
outbox events and audit records so the worker's eventual consistency is the
only failure domain (Rule R8).
"""

from __future__ import annotations

import urllib.parse
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import settings
from app.core.context import UserContext
from app.core.outbox import write_outbox
from app.core.security import create_signed_grant
from app.modules.recordings import repository as repo
from app.modules.recordings.errors import (
    RecordingDownloadUnauthorizedError,
    RecordingNotFoundError,
    RecordingPurgedError,
    RecordingPurgeUnauthorizedError,
    RecordingSourceUnavailableError,
)
from app.modules.recordings.policies import (
    CannedQualificationPolicy,
    RecordingPolicy,
    resolve_scope_constraints,
)
from app.modules.recordings.schemas import (
    PurgeRequest,
    QaAuditRequest,
    RecordingDTO,
    RecordingListQuery,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, RecordingStatus
from app.packages.db.models import CallRecording
from app.packages.storage.provider import get_storage_provider

_UTC = UTC
logger = structlog.get_logger("recordings.service")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_entity(raw: dict[str, Any]) -> CallRecording | None:
    """The ORM object embedded in every repository row dict (key 'CallRecording')."""
    ent = raw.get("CallRecording")
    return ent if isinstance(ent, CallRecording) else None


def _format_row(
    raw: dict[str, Any], user: UserContext, audio_url: str | None
) -> RecordingDTO:
    ent = _row_entity(raw)
    if ent is None:  # pragma: no cover - defensive; repository always embeds it
        raise RecordingNotFoundError("recording.not_found")

    first = raw.get("first_name") or ""
    last = raw.get("last_name") or ""
    lead_name = f"{first} {last}".strip() or None
    phone = RecordingPolicy.masked_phone(raw.get("phone_normalized") or "", user)

    qual_status = CannedQualificationPolicy.resolve(
        raw.get("qualification_status"),
        raw.get("disqualification_reason"),
    )
    duration = raw.get("call_duration") or ent.duration_seconds or 0

    return RecordingDTO(
        id=ent.id,
        call_id=ent.call_id,
        vicidial_recording_id=ent.vicidial_recording_id,
        lead_id=ent.lead_id,
        lead_name=lead_name,
        phone=phone,
        campaign=raw.get("campaign_name"),
        disposition=raw.get("disposition"),
        duration_sec=int(duration),
        consent_captured=ent.consent_offset_ms is not None,
        qual_status=qual_status,
        qual_details=raw.get("disqualification_reason"),
        verifier=raw.get("verifier_name"),
        qa_score=raw.get("qa_score"),
        qa_status=raw.get("qa_status"),
        status=RecordingStatus(ent.status),
        audio_url=audio_url,
        transcript=raw.get("transcript"),
        expires_at=ent.expires_at,
        created_at=ent.created_at,
    )


async def _publish_event(
    session: AsyncSession,
    *,
    event_type: str,
    recording_id: uuid.UUID,
    payload: dict[str, Any],
) -> None:
    await write_outbox(
        session,
        event_type=event_type,
        aggregate_id=str(recording_id),
        payload=payload,
    )


async def _audit(
    session: AsyncSession,
    *,
    user: UserContext,
    action: str,
    recording_id: uuid.UUID | str,
    result: AuditResult,
    details: dict[str, Any] | None = None,
) -> None:
    """Every recording read/write of PHI goes through the central audit writer."""
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action=action,
        resource_type="recording",
        resource_id=str(recording_id),
        result=result,
        details=details or {},
    )


def _grant_claims(
    user: UserContext, recording: CallRecording, *, purpose: str
) -> dict[str, Any]:
    return {
        "actor_id": str(user.user_id),
        "actor_role": user.role,
        "recording_id": str(recording.id),
        "call_id": str(recording.call_id),
        "purpose": purpose,
    }


async def _fetch_ready_recording(
    session: AsyncSession, user: UserContext, recording_id: uuid.UUID
) -> CallRecording:
    row = await repo.fetch_row(session, recording_id, resolve_scope_constraints(user))
    if row.status == RecordingStatus.PURGED.value:
        raise RecordingPurgedError("recording.purged_or_expired")
    if row.status != RecordingStatus.READY.value:
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    if not row.storage_key:
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    return row


async def _recording_for_call(
    session: AsyncSession, call_id: uuid.UUID
) -> CallRecording:
    stmt = select(CallRecording).where(CallRecording.call_id == call_id).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise RecordingNotFoundError("recording.not_found")
    return row


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


async def get_recording(
    session: AsyncSession, user: UserContext, recording_id: uuid.UUID
) -> DataResponse[RecordingDTO]:
    constraints = resolve_scope_constraints(user)
    raw = await repo.get_recording(session, recording_id, constraints)

    audio_url = None
    ent = _row_entity(raw)
    if (
        ent is not None
        and ent.status == RecordingStatus.READY.value
        and ent.storage_key
    ):
        provider = get_storage_provider()
        audio_url = provider.build_access_url(
            storage_key=ent.storage_key,
            purpose="stream",
            ttl_seconds=settings.playback_url_ttl_seconds,
        )

    dto = _format_row(raw, user, audio_url)
    return DataResponse(data=dto)


async def list_recordings(
    session: AsyncSession,
    user: UserContext,
    query: RecordingListQuery,
) -> PagedResponse[RecordingDTO]:
    constraints = resolve_scope_constraints(user)
    rows, total = await repo.list_recordings(session, query, constraints)
    provider = get_storage_provider()
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)

    dtos: list[RecordingDTO] = []
    for row in rows:
        audio_url = None
        ent = _row_entity(row)
        if (
            ent is not None
            and ent.status == RecordingStatus.READY.value
            and ent.storage_key
        ):
            audio_url = provider.build_access_url(
                storage_key=ent.storage_key,
                purpose="stream",
                ttl_seconds=settings.playback_url_ttl_seconds,
            )
        dtos.append(_format_row(row, user, audio_url))

    meta = PagedMeta(
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=total_pages,
        sort=query.sort,
        order=query.order,
    )
    return PagedResponse(data=dtos, meta=meta)


async def get_playback_url(
    session: AsyncSession,
    user: UserContext,
    recording_id: uuid.UUID,
) -> str:
    """Mint a 5-minute playback grant, then audit the issuance.

    Authorization lives here (not in the route dependency) so a denied attempt
    is still written to the central audit log.
    """
    if not RecordingPolicy.can_play(user):
        await _audit(
            session,
            user=user,
            action="recording.play",
            recording_id=recording_id,
            result=AuditResult.DENIED,
            details={"reason": "missing recordings:read"},
        )
        await session.commit()
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    row = await _fetch_ready_recording(session, user, recording_id)
    token, _jti = create_signed_grant(
        row.storage_key,
        purpose="stream",
        ttl_seconds=settings.playback_url_ttl_seconds,
        claims=_grant_claims(user, row, purpose="stream"),
    )
    await _audit(
        session,
        user=user,
        action="recording.played",
        recording_id=row.id,
        result=AuditResult.GRANTED,
        details={
            "call_id": str(row.call_id),
            "purpose": "stream",
            "ttl_seconds": settings.playback_url_ttl_seconds,
        },
    )
    await session.commit()
    base = settings.storage_public_base_url.rstrip("/")
    return f"{base}/api/v1/recordings/stream/{urllib.parse.quote(token, safe='')}"


async def get_download_url(
    session: AsyncSession,
    user: UserContext,
    recording_id: uuid.UUID,
) -> str:
    """Mint a single-use 15-minute download grant, then audit the issuance."""
    if not RecordingPolicy.can_download(user):
        await _audit(
            session,
            user=user,
            action="recording.download",
            recording_id=recording_id,
            result=AuditResult.DENIED,
            details={"reason": "missing recordings:download"},
        )
        await session.commit()
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    row = await _fetch_ready_recording(session, user, recording_id)
    token, _jti = await _issue_download_grant(session, user, row)
    base = settings.storage_public_base_url.rstrip("/")
    return f"{base}/api/v1/recordings/download/{urllib.parse.quote(token, safe='')}"


async def _issue_download_grant(
    session: AsyncSession, user: UserContext, row: CallRecording
) -> tuple[str, str]:
    ttl_seconds = settings.download_token_ttl_minutes * 60
    token, jti = create_signed_grant(
        row.storage_key,
        purpose="download",
        ttl_seconds=ttl_seconds,
        claims=_grant_claims(user, row, purpose="download"),
    )
    await _audit(
        session,
        user=user,
        action="recording.downloaded",
        recording_id=row.id,
        result=AuditResult.GRANTED,
        details={
            "call_id": str(row.call_id),
            "purpose": "download",
            "jti": jti,
            "ttl_seconds": ttl_seconds,
            "single_use": True,
        },
    )
    await _publish_event(
        session,
        event_type="recording.download_requested",
        recording_id=row.id,
        payload={
            "call_id": str(row.call_id),
            "requested_by": str(user.user_id),
            "storage_key": row.storage_key,
        },
    )
    await session.commit()
    return token, jti


async def get_recording_by_call_id(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> DataResponse[RecordingDTO]:
    stmt = select(CallRecording).where(CallRecording.call_id == call_id).limit(1)
    res = await session.execute(stmt)
    row = res.scalar_one_or_none()
    if not row:
        raise RecordingNotFoundError("recording.not_found")
    return await get_recording(session, user, row.id)


async def get_call_playback_url(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> str:
    """Step 37: 5-minute presigned playback URL + audited action recording.played."""
    if not RecordingPolicy.can_play(user):
        await _audit(
            session,
            user=user,
            action="recording.play",
            recording_id=call_id,
            result=AuditResult.DENIED,
            details={"reason": "missing recordings:read", "call_id": str(call_id)},
        )
        await session.commit()
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    row = await _recording_for_call(session, call_id)
    return await get_playback_url(session, user, row.id)


async def get_call_download_token(
    session: AsyncSession, user: UserContext, call_id: uuid.UUID
) -> str:
    """Step 37: Single-use download token + audited action recording.downloaded."""
    if not RecordingPolicy.can_download(user):
        await _audit(
            session,
            user=user,
            action="recording.download",
            recording_id=call_id,
            result=AuditResult.DENIED,
            details={"reason": "missing recordings:download", "call_id": str(call_id)},
        )
        await session.commit()
        raise RecordingDownloadUnauthorizedError("recording.download_unauthorized")
    row = await _recording_for_call(session, call_id)
    if row.status == RecordingStatus.PURGED.value:
        raise RecordingPurgedError("recording.purged_or_expired")
    if row.status != RecordingStatus.READY.value or not row.storage_key:
        raise RecordingSourceUnavailableError("recording.source_unavailable")
    token, _jti = await _issue_download_grant(session, user, row)
    return token


async def purge_recording(
    session: AsyncSession,
    user: UserContext,
    recording_id: uuid.UUID,
    request: PurgeRequest,
) -> DataResponse[RecordingDTO]:
    row = await repo.fetch_row(session, recording_id, resolve_scope_constraints(user))
    if not RecordingPolicy.can_purge(user):
        raise RecordingPurgeUnauthorizedError("recording.purge_unauthorized")

    provider = get_storage_provider()
    await provider.delete(row.storage_key) if row.storage_key else None
    row.status = RecordingStatus.PURGED.value
    row.audio_purged_at = datetime.now(_UTC)
    await repo.save(session, row)
    await _publish_event(
        session,
        event_type="recording.purged",
        recording_id=recording_id,
        payload={
            "call_id": str(row.call_id),
            "reason": request.reason,
            "purged_by": str(user.user_id),
            "deleted_object": {"key": row.storage_key},
        },
    )
    await _audit(
        session,
        user=user,
        action="recording.purge",
        recording_id=recording_id,
        result=AuditResult.SUCCESS,
        details={"reason": request.reason, "call_id": str(row.call_id)},
    )
    await session.commit()
    return DataResponse(
        data=RecordingDTO(
            id=row.id,
            call_id=row.call_id,
            vicidial_recording_id=row.vicidial_recording_id,
            lead_id=row.lead_id,
            campaign=None,
            disposition=None,
            duration_sec=row.duration_seconds,
            consent_captured=bool(row.consent_offset_ms),
            status=RecordingStatus.PURGED,
            audio_url=None,
            created_at=row.created_at,
        )
    )


async def purge_expired_recordings(session: AsyncSession) -> int:
    """Background retention purge (blueprint 15.5).

    Marks every READY recording whose ``expires_at`` has passed as PURGED and
    deletes the physical audio via the storage provider.  Idempotent and
    best-effort: already-purged rows are skipped, and missing files are not an
    error.  Call periodically from a worker (e.g. an APScheduler/interval task).
    """
    now = datetime.now(_UTC)
    stmt = select(CallRecording).where(
        CallRecording.expires_at.is_not(None),
        CallRecording.expires_at <= now,
        CallRecording.status == RecordingStatus.READY.value,
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return 0

    provider = get_storage_provider()
    purged = 0
    for row in rows:
        if row.storage_key:
            try:
                await provider.delete(row.storage_key)
            except Exception:
                logger.exception(
                    "recording purge file delete failed", recording_id=str(row.id)
                )
        row.status = RecordingStatus.PURGED.value
        row.audio_purged_at = now
        await _publish_event(
            session,
            event_type="recording.purged",
            recording_id=row.id,
            payload={
                "call_id": str(row.call_id),
                "reason": "retention.expired",
                "purged_by": "system",
                "deleted_object": {"key": row.storage_key},
            },
        )
        purged += 1

    await session.commit()
    logger.info("recordings purged by retention", count=purged)
    return purged


async def save_qa_audit(
    session: AsyncSession,
    user: UserContext,
    recording_id: uuid.UUID,
    payload: QaAuditRequest,
) -> DataResponse[RecordingDTO]:
    """Write the QA Audit Scorecard (score, status, compliance checklist).

    Persists into the single per-call ``qa_reviews`` row, records an audit log
    and emits a ``recording.qa_audited`` outbox event - all in one transaction.
    """
    row = await repo.fetch_row(session, recording_id, resolve_scope_constraints(user))
    now = datetime.now(_UTC)

    await repo.upsert_qa_review(
        session, recording=row, payload=payload, actor_id=user.user_id, now=now
    )
    await _audit(
        session,
        user=user,
        action="recording.qa_audit",
        recording_id=recording_id,
        result=AuditResult.SUCCESS,
        details={
            "score": payload.score,
            "status": payload.status or "Audited",
            "consent_verified": payload.consent_verified,
            "qual_verified": payload.qual_verified,
            "transfer_verified": payload.transfer_verified,
        },
    )
    await _publish_event(
        session,
        event_type="recording.qa_audited",
        recording_id=recording_id,
        payload={
            "call_id": str(row.call_id),
            "score": payload.score,
            "status": payload.status or "Audited",
            "audited_by": str(user.user_id),
        },
    )
    await session.commit()

    # Re-fetch so the response reflects the freshly written QA row.
    return await get_recording(session, user, recording_id)
