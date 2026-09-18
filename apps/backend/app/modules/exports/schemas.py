"""Export DTOs and query models (camelCase on the wire)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import ExportFormat, ExportStatus


class ExportFilters(APIBaseModel):
    """Per-report filter whitelist (schema-level, applied in the repository)."""

    campaign_id: uuid.UUID | None = None
    status: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=120)
    date_from: datetime | None = None
    date_to: datetime | None = None
    q: str | None = Field(default=None, max_length=160)


class ExportRequest(APIBaseModel):
    """POST /exports payload."""

    report: str = Field(min_length=1, max_length=64)
    filters: ExportFilters | None = None


class ExportJobDTO(APIBaseModel):
    """Wire model of one export job (history rows of spec 28.8)."""

    id: uuid.UUID
    report: str
    format: ExportFormat = ExportFormat.CSV
    filters: dict[str, Any] | None = None
    status: ExportStatus
    row_count: int = 0
    error: str | None = None
    download_url: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class ExportListQuery(APIBaseModel):
    """Export history query parameters (all optional, whitelisted)."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    status: ExportStatus | None = None
    report: str | None = Field(default=None, max_length=64)
    sort: str | None = None
    order: str | None = None