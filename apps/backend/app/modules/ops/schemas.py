"""Schemas and DTOs for Operations Surface (Step 51)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class HealthCardDTO(APIBaseModel):
    name: str
    status: str  # healthy | degraded | unhealthy | disabled
    details: str | dict[str, Any] | None = None
    checked_at: datetime


class HealthCheckResponseDTO(APIBaseModel):
    status: str  # healthy | degraded | unhealthy
    cards: list[HealthCardDTO]
    timestamp: datetime


class AlertDTO(APIBaseModel):
    id: uuid.UUID
    code: str
    severity: str  # critical | warning | info
    title: str
    message: str
    status: str  # active | acknowledged | resolved
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: datetime
    acknowledged_at: datetime | None = None


class SearchQueryDTO(APIBaseModel):
    q: str = Field(min_length=1, max_length=120)
    type: str | None = Field(
        default=None, description="calls | leads | campaigns | recordings | scripts"
    )


class SearchItemDTO(APIBaseModel):
    id: str
    type: str
    title: str
    subtitle: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResultResponseDTO(APIBaseModel):
    query: str
    total: int
    items: list[SearchItemDTO]


class IntegrationDTO(APIBaseModel):
    id: uuid.UUID
    name: str
    type: str
    status: str  # configured | active | error | disabled
    config: dict[str, Any] | None = None
    updated_at: datetime


class NotificationDTO(APIBaseModel):
    id: uuid.UUID
    title: str
    message: str
    type: str  # info | warning | success | error
    read: bool
    created_at: datetime
