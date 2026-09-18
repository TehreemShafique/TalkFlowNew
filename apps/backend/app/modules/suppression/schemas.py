"""Suppression DTOs and query models (camelCase on the wire).

``SuppressionEntryDTO`` mirrors the register row the dashboard renders; the
check endpoint returns the tri-state (suppressed/reason/expiry) the lead detail
and the dialer pre-check consume before placing a call.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import SuppressionReason

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class SuppressionEntryDTO(APIBaseModel):
    """Wire model for one suppression/DNC row (spec 19.4)."""

    id: uuid.UUID
    phone: str
    reason: SuppressionReason
    source: str | None = None
    added_by: uuid.UUID | None = None
    added_at: datetime
    expires_at: datetime | None = None
    evidence_reference: str | None = None
    removed_at: datetime | None = None
    removed_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class SuppressionEntryCreate(APIBaseModel):
    """POST /suppression payload."""

    phone: str = Field(min_length=10, max_length=32)
    reason: SuppressionReason = SuppressionReason.INTERNAL_DNC
    source: str | None = Field(default=None, max_length=120)
    expires_at: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=255)


class SuppressionListQuery(APIBaseModel):
    """Collection query parameters (all optional, whitelisted)."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    phone: str | None = Field(default=None, max_length=32)
    reason: SuppressionReason | None = None
    source: str | None = Field(default=None, max_length=120)
    include_removed: bool = False
    sort: str | None = None
    order: str | None = None


class SuppressionCheckDTO(APIBaseModel):
    """GET /suppression/check?phone= result (dialer pre-check)."""

    suppressed: bool
    reason: SuppressionReason | None = None
    entry_id: uuid.UUID | None = None
    expires_at: datetime | None = None


class SuppressionImportResult(APIBaseModel):
    """POST /suppression/import summary."""

    total: int
    added: int
    duplicate: int
    invalid: int