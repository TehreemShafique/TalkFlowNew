"""Schemas for rule sets module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class RuleConditionDTO(APIBaseModel):
    field: str
    operator: str
    value: Any


class RuleSetVersionDTO(APIBaseModel):
    id: uuid.UUID
    rule_set_id: uuid.UUID
    version: int
    status: str
    rules: dict[str, Any] = Field(default_factory=dict)
    disqualification_reasons: dict[str, Any] = Field(default_factory=dict)
    change_note: str | None = None
    created_at: datetime


class RuleSetDTO(APIBaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    current_version: int
    active_version_id: uuid.UUID | None = None
    status: str
    versions: list[RuleSetVersionDTO] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RuleSetCreate(APIBaseModel):
    name: str
    description: str | None = None
    rules: dict[str, Any] = Field(default_factory=dict)
    disqualification_reasons: dict[str, Any] = Field(default_factory=dict)


class RuleSetEvaluateRequest(APIBaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)


class RuleSetEvaluateResponse(APIBaseModel):
    status: str
    reason: str | None = None
