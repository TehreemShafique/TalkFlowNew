"""Recording DTOs and query models.

The API always talks in camelCase (see packages.contracts.base).  Field names
and the envelope match the dashboard's frozen frontend contract
(apps/TalkFlow.md section 11.8): lead name, masked phone, campaign, disposition,
duration, consent, qualification status/details, verifier, QA score/status,
and a playable audioUrl.  Never a raw storage path (Rule R7).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import RecordingStatus

_UTC = UTC


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class RecordingDTO(APIBaseModel):
    """Wire model for one recording row (camelCase on the wire)."""

    id: uuid.UUID
    call_id: uuid.UUID
    vicidial_recording_id: str | None = None

    lead_id: uuid.UUID | None = None
    lead_name: str | None = None
    phone: str | None = None  # masked unless pii.view_full granted (mask_phone)

    campaign: str | None = None
    disposition: str | None = None
    duration_sec: int = 0
    consent_captured: bool | None = None

    qual_status: str | None = None
    qual_details: str | None = None
    verifier: str | None = None

    qa_score: float | None = None
    qa_status: str | None = None

    status: RecordingStatus
    audio_url: str | None = None  # signed playback/download grant or presigned S3 URL

    # AI Voice Bot transcript lines ([{speaker, time, text}]) in spoken order.
    transcript: list[dict[str, Any]] | None = None
    expires_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(_UTC))


class RecordingListQuery(APIBaseModel):
    """Collection query parameters (all optional, whitelisted)."""

    page: int = 1
    page_size: int = 20
    sort: str | None = None
    order: str | None = None
    search: str | None = None
    status: RecordingStatus | None = None
    campaign_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    disposition: str | None = None
    qa_status: str | None = None
    from_: datetime | None = Field(None, alias="from")
    to: datetime | None = None


class PurgeRequest(APIBaseModel):
    reason: str | None = Field(default=None, max_length=200)


class QaAuditRequest(APIBaseModel):
    """Payload from the QA Audit Scorecard modal (POST /{id}/qa-audit).

    All fields optional so a partial checklist update round-trips cleanly;
    ``score`` accepts decimals (e.g. 4.5 or 4.85 from a QA scorecard).
    """

    score: float | None = Field(default=None, ge=0, le=5)
    status: str | None = None
    consent_verified: bool | None = None
    qual_verified: bool | None = None
    transfer_verified: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)
    auto_failed: bool | None = None
