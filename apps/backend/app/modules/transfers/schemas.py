"""Transfers DTOs and query models (Step 34)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import TransferStatus


class TransferDTO(APIBaseModel):
    """Wire model for a live or historical transfer."""

    id: uuid.UUID
    call_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    from_agent_id: str | None = None
    verifier_id: str | None = None
    verifier_group_id: str | None = None
    status: TransferStatus
    ring_timeout_seconds: int = 20
    initiated_at: datetime
    bridged_at: datetime | None = None
    ended_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TransferListQuery(APIBaseModel):
    """Query parameters for transfer list endpoint."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    status: TransferStatus | None = None
    verifier_id: str | None = None
    campaign_id: uuid.UUID | None = None
    sort: str | None = None
    order: str | None = None


class TransferRetryRequest(APIBaseModel):
    """Payload for POST /transfers/{id}/retry."""

    target_verifier_group: str | None = None


class TransferCallbackRequest(APIBaseModel):
    """Payload for POST /transfers/{id}/create-callback."""

    callback_time: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
