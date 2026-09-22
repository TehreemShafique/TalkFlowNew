"""Schemas for compliance module API contract."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class ComplianceRuleDTO(APIBaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    rule_key: str
    mode: str
    rationale: str | None = None
    updated_at: datetime


class ComplianceProfileDTO(APIBaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    jurisdiction: str
    is_active: bool
    rules: list[ComplianceRuleDTO] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ComplianceRuleUpdate(APIBaseModel):
    mode: str
    confirmation: str | None = None
    rationale: str | None = None
