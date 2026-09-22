"""Verifier DTOs and payload schemas (Step 35)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class VerifierAvailabilityRequest(APIBaseModel):
    """Payload for POST /verifier/availability."""

    status: str = Field(description="available | busy | offline")


class VerifierDispositionRequest(APIBaseModel):
    """Payload for POST /verifier/calls/{id}/disposition."""

    disposition: str = Field(min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class VerifierQueueItemDTO(APIBaseModel):
    """Item in verifier incoming transfer queue."""

    transfer_id: uuid.UUID
    call_id: uuid.UUID
    prospect_name: str
    phone: str
    campaign_name: str
    ring_timeout_seconds: int
    initiated_at: datetime


class VerifierAcceptContextDTO(APIBaseModel):
    """Single-payload response returning full context in ONE call (Step 35)."""

    transfer_id: uuid.UUID
    call_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    prospect_details: dict[str, Any]
    qualification_status: str
    qualification_fields: list[dict[str, Any]]
    consent_evidence: dict[str, Any]
    recording_ref: str | None = None
    lead_history: list[dict[str, Any]]
    script_context: dict[str, Any]
