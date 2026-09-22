"""QA DTOs and payload schemas (Step 49)."""

from __future__ import annotations

import uuid
import datetime as dt
from datetime import datetime
from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class CriterionScoreItem(APIBaseModel):
    criterion_id: uuid.UUID
    score_value: float = Field(ge=0.0, le=100.0, description="Score value 0 to 100")


class QAReviewCreateRequest(APIBaseModel):
    call_id: uuid.UUID
    recording_id: uuid.UUID | None = None
    scorecard_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)
    scores: list[CriterionScoreItem] = Field(min_items=1)


class QACriterionDTO(APIBaseModel):
    id: uuid.UUID
    scorecard_id: uuid.UUID
    category: str
    title: str
    weight: float
    auto_fail: bool
    display_order: int


class QAScorecardDTO(APIBaseModel):
    id: uuid.UUID
    name: str
    version: str
    is_active: bool
    criteria: list[QACriterionDTO] = []
    created_at: datetime


class QAReviewDTO(APIBaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    recording_id: uuid.UUID | None = None
    scorecard_id: uuid.UUID
    reviewer_id: uuid.UUID
    total_score: float
    passed: bool
    auto_failed: bool
    notes: str | None = None
    created_at: datetime


class QASampleQuery(APIBaseModel):
    date: dt.date | None = None
    campaign_id: uuid.UUID | None = None
    size: int = Field(default=10, ge=1, le=100)


class QASampleCallDTO(APIBaseModel):
    call_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    started_at: datetime
    duration_seconds: int | None = None
    transfer_status: str | None = None
    recording_status: str | None = None
    qa_flags: list[str] | None = None
    risk_score: float
