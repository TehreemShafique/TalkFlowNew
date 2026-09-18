"""Campaign DTOs and query models (camelCase on the wire).

Matches the dashboard ``Campaign`` contract: identity + lifecycle status, the
bound script / rule set / compliance references, and the opaque ``dialing`` /
``transfer`` / ``recording`` / ``retention`` governance blobs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import CampaignStatus

_UTC = UTC


class CampaignDTO(APIBaseModel):
    """Wire model for one campaign row."""

    id: uuid.UUID
    name: str
    status: CampaignStatus

    # Soft references to modules that are not built yet.
    script_id: uuid.UUID | None = None
    active_script_version_id: uuid.UUID | None = None
    rule_set_version_id: uuid.UUID | None = None
    compliance_profile_id: uuid.UUID | None = None

    # VICIdial routing.
    vicidial_campaign_id: str | None = None
    closer_in_group: str | None = None
    vicidial_list_ids: list[str] = Field(default_factory=list)

    timezone: str = "America/New_York"

    dialing: dict[str, Any] | None = None
    transfer: dict[str, Any] | None = None
    recording: dict[str, Any] | None = None
    retention: dict[str, Any] | None = None

    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(_UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(_UTC))


class CampaignCreate(APIBaseModel):
    """POST /campaigns payload (new campaigns always open in ``draft``)."""

    name: str = Field(min_length=1, max_length=160)
    script_id: uuid.UUID | None = None
    active_script_version_id: uuid.UUID | None = None
    rule_set_version_id: uuid.UUID | None = None
    compliance_profile_id: uuid.UUID | None = None
    vicidial_campaign_id: str | None = Field(default=None, max_length=64)
    closer_in_group: str | None = Field(default=None, max_length=120)
    timezone: str = Field(default="America/New_York", max_length=64)
    dialing: dict[str, Any] | None = None
    transfer: dict[str, Any] | None = None
    recording: dict[str, Any] | None = None
    retention: dict[str, Any] | None = None
    vicidial_list_ids: list[str] = Field(default_factory=list)


class CampaignUpdate(APIBaseModel):
    """PUT /campaigns/{id} payload - every field optional (partial update)."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    status: CampaignStatus | None = None
    script_id: uuid.UUID | None = None
    active_script_version_id: uuid.UUID | None = None
    rule_set_version_id: uuid.UUID | None = None
    compliance_profile_id: uuid.UUID | None = None
    vicidial_campaign_id: str | None = Field(default=None, max_length=64)
    closer_in_group: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    dialing: dict[str, Any] | None = None
    transfer: dict[str, Any] | None = None
    recording: dict[str, Any] | None = None
    retention: dict[str, Any] | None = None
    vicidial_list_ids: list[str] | None = None
    # Optimistic locking: when supplied it must match the stored version.
    version: int | None = Field(default=None, ge=1)


class CampaignStatsDTO(APIBaseModel):
    """GET /campaigns/{id}/stats - today's performance counters (PRD FR-11).

    ``contact_rate`` / ``qualification_rate`` / ``transfer_rate`` are fractions
    in ``[0.0, 1.0]`` (the frontend formats them as percentages).
    """

    calls_today: int = Field(default=0, ge=0)
    contact_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    qualification_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    transfer_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class CampaignStartResponse(APIBaseModel):
    """POST /campaigns/{id}/start result (problems empty on success)."""

    campaign: CampaignDTO
    problems: list[str] = Field(default_factory=list)


class CampaignListQuery(APIBaseModel):
    """Collection query parameters (all optional, whitelisted)."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    status: CampaignStatus | None = None
    search: str | None = Field(default=None, max_length=160)
    sort: str | None = None
    order: str | None = None
