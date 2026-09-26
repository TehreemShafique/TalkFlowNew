"""Telephony webhook DTOs and metadata (BACKEND-8a).

Every inbound payload preserves the control-plane identifiers required by the
blueprint: the active ``script_version_id`` and the TalkFlow ``call_id``.  The
VICIdial edge echoes the same values back so later ingest never has to guess
them (roadmap section 660).
"""

from __future__ import annotations

import uuid

from app.packages.contracts.base import APIBaseModel


class TelephonyWebhookEnvelope(APIBaseModel):
    """Shared envelope for authenticated VICIdial webhook bodies."""

    lead_id: uuid.UUID
    call_id: uuid.UUID
    script_version_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None

    # Preserved identifiers (metadata preservation requirement).
    vicidial_lead_id: str | None = None
    vicidial_call_id: str | None = None
    channel_id: str | None = None


class StartCallPayload(TelephonyWebhookEnvelope):
    """``POST /telephony/vicidial/start-call`` body."""

    caller_number: str | None = None
    caller_state: str | None = None
    did_used: str | None = None
    event_ts: str | None = None


class DispoCallPayload(TelephonyWebhookEnvelope):
    """``POST /telephony/vicidial/dispo-call`` body.

    ``outcome`` carries the TalkFlow disposition (e.g. ``qualified``); the
    mapped VICIdial status is derived locally via
    :func:`app.packages.vicidial.mapper.map_talkflow_to_vicidial_status`.
    """

    outcome: str | None = None
    status: str | None = None
    duration_seconds: int | None = None
    event_ts: str | None = None


class WebhookResult(APIBaseModel):
    """Acknowledgement returned to VICIdial.

    ``ignored_duplicate: true`` signals the request was a replay; the caller
    should treat HTTP 200 either way (no retry storm).
    """

    request_id: str
    status: str = "processed"
    ignored_duplicate: bool = False
    valid: bool = True
    error: str | None = None
