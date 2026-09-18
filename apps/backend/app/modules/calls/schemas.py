"""Call DTOs and query models (camelCase on the wire).

Field names match the committed dashboard contract (apps/TalkFlow.md section
26): the ``Call`` interface's caller/qualification/consent/transfer sub-objects,
the ``TranscriptTurn`` shape, and the live-card contract of section 22.1.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import CallDirection, CallStatus, QualificationStatus

_UTC = UTC


class TranscriptTurnDTO(APIBaseModel):
    """One row of the transcript (section 26.2)."""

    id: uuid.UUID
    speaker: str
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    node_id: str | None = None
    is_final: bool = True
    confidence: float | None = None
    redacted: bool = False


class TimelineEventDTO(APIBaseModel):
    """One event in the millisecond-level timeline (section 26.6)."""

    id: uuid.UUID
    type: str
    event_ts: datetime
    category: str = "GENERAL"
    payload: dict[str, Any] | None = None


class PerformanceDTO(APIBaseModel):
    """Per-call latency snapshot (section 26.7)."""

    vad_ms: float | None = None
    stt_ms: float | None = None
    decide_ms: float | None = None
    llm_ttft_ms: float | None = None
    llm_total_ms: float | None = None
    tts_ttfa_ms: float | None = None
    tts_total_ms: float | None = None
    total_turn_ms: float | None = None
    turn_count: int | None = None
    stt_provider: str | None = None
    tts_provider: str | None = None
    llm_provider: str | None = None


class ScriptPathNodeDTO(APIBaseModel):
    """One step in the node path the call traversed (section 26.4)."""

    id: uuid.UUID
    seq: int | None = None
    node_id: str | None = None
    node_type: str | None = None
    node_name: str | None = None
    entered_at: datetime | None = None
    exited_at: datetime | None = None
    transition_taken: str | None = None
    meta: dict[str, Any] | None = None


class CallerInfoDTO(APIBaseModel):
    """Phone shown to the user: raw number for PII grants, masked otherwise."""

    number: str | None = None
    masked: str | None = None
    name: str | None = None
    state: str | None = None


class QualificationFieldDTO(APIBaseModel):
    """One captured qualification-evidence value with its provenance."""

    field: str
    label: str | None = None
    value: str | int | float | bool | None = None
    captured_at: datetime | None = None
    transcript_ref: str | None = None
    confidence: float | None = None
    required: bool = True


class QualificationDTO(APIBaseModel):
    """Live qualification outcome of a call (TalkFlow.md section 11.4)."""

    status: str = QualificationStatus.PENDING.value
    fields: list[QualificationFieldDTO] = Field(default_factory=list)
    disqualification_reason: str | None = None
    evaluated_at: datetime | None = None


class ConsentEvidenceDTO(APIBaseModel):
    """Verbatim consent evidence contract; the call's compliance-event table is
    not part of this module yet, so ``captured`` is a best-effort read of the
    recording/transcript state until that module ships."""

    captured: bool = False
    consent_language_version: str | None = None
    captured_at: datetime | None = None
    recording_offset_ms: int | None = None
    transcript_ref: str | None = None
    method: str = "not_captured"


class TransferRecordDTO(APIBaseModel):
    """Transfer summary shown on the detail overview (section 26.1)."""

    status: str = "not_applicable"
    initiated_at: datetime | None = None
    bridged_at: datetime | None = None
    ended_at: datetime | None = None
    verifier_id: uuid.UUID | None = None
    verifier_name: str | None = None
    attempts: int = Field(default=0, ge=0)
    wait_seconds: int | None = None
    failure_reason: str | None = None
    fallback_action: str | None = None


class RecordingPointerDTO(APIBaseModel):
    """Optional link to the owned recordings module (''-JSON null when absent)."""

    call_id: uuid.UUID
    status: str | None = None
    duration_seconds: int | None = None
    size_bytes: int | None = None


class CallDTO(APIBaseModel):
    """Wire model for one call row (list + detail)."""

    id: uuid.UUID
    reference: str
    direction: CallDirection
    status: CallStatus
    disposition: str | None = None

    lead_id: uuid.UUID | None = None
    lead_name: str | None = None
    campaign_id: uuid.UUID | None = None
    campaign_name: str | None = None
    script_id: uuid.UUID | None = None
    script_version: int | None = None
    script_version_id: uuid.UUID | None = None
    rule_set_version_id: uuid.UUID | None = None

    channel_id: str | None = None
    vicidial_call_id: str | None = None
    vicidial_lead_id: str | None = None
    vicidial_list_id: str | None = None
    vicidial_status: str | None = None

    caller: CallerInfoDTO = Field(default_factory=CallerInfoDTO)
    did_used: str | None = None
    caller_id_used: str | None = None
    agent_alias_used: str | None = None
    attempt_number: int = 1

    started_at: datetime
    answered_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    talk_time_seconds: int | None = None

    qualification: QualificationDTO = Field(default_factory=QualificationDTO)
    consent: ConsentEvidenceDTO = Field(default_factory=ConsentEvidenceDTO)
    transfer: TransferRecordDTO = Field(default_factory=TransferRecordDTO)
    recording: RecordingPointerDTO | None = None

    qa_status: str | None = None
    qa_score: float | None = None

    # Live-card extras (only populated by GET /calls/live).
    live_state: str | None = None
    node_name: str | None = None

    created_at: datetime
    updated_at: datetime


class LiveCallDTO(APIBaseModel):
    """Concise shape for the /calls/live card grid (section 22.1)."""

    id: uuid.UUID
    reference: str
    campaign_name: str | None = None
    script_version: int | None = None
    caller: CallerInfoDTO = Field(default_factory=CallerInfoDTO)
    live_state: str
    node_name: str | None = None
    attempt_number: int = 1
    started_at: datetime
    duration_seconds: int | None = None
    qualification_status: str | None = None
    consent_captured: bool = False


class CallListQuery(APIBaseModel):
    """Collection query parameters (all optional, whitelisted)."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    search: str | None = Field(default=None, max_length=160)
    sort: str | None = None  # started_at | duration_seconds | attempt_number | reference
    order: str | None = None  # asc | desc
    status: CallStatus | None = None
    direction: CallDirection | None = None
    disposition: str | None = Field(default=None, max_length=128)
    qualification_status: str | None = Field(default=None, max_length=64)
    transfer_status: str | None = Field(default=None, max_length=64)
    campaign_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None


class DispositionUpdate(APIBaseModel):
    """PATCH /calls/{id}/disposition payload (section 26.1 outcome write)."""

    disposition: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=200)