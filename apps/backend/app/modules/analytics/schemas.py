"""Analytics DTOs and query schemas (Step 39)."""

from __future__ import annotations

import uuid
import datetime as dt
from datetime import datetime
from pydantic import Field

from app.packages.contracts.base import APIBaseModel


class AnalyticsDateQuery(APIBaseModel):
    from_date: dt.date | None = Field(default=None, alias="from")
    to_date: dt.date | None = Field(default=None, alias="to")
    campaign_id: uuid.UUID | None = None


class AnalyticsSummaryDTO(APIBaseModel):
    total_calls: int = 0
    answered_calls: int = 0
    contacted_calls: int = 0
    qualified_calls: int = 0
    transferred_calls: int = 0
    verifier_accepted: int = 0
    disqualified_calls: int = 0
    answer_rate: str = "0.0%"
    qual_rate: str = "0.0%"
    transfer_rate: str = "0.0%"
    avg_duration_sec: float = 0.0


class CampaignAggDTO(APIBaseModel):
    date: date
    campaign_id: uuid.UUID
    campaign_name: str | None = None
    total_calls: int
    answered: int
    contacted: int
    qualified: int
    transferred: int
    verifier_accepted: int
    disqualified: int
    answer_rate: str
    qual_rate: str
    transfer_rate: str
    avg_duration: float


class ScriptVersionAggDTO(APIBaseModel):
    date: date
    script_version_id: uuid.UUID
    script_name: str | None = None
    version: str | None = None
    total_calls: int
    answered: int
    contacted: int
    qualified: int
    transferred: int
    disqualified: int
    qual_rate: str
    avg_duration: float


class SourceAggDTO(APIBaseModel):
    date: date
    source: str
    vendor_name: str | None = None
    total_calls: int
    answered: int
    contacted: int
    qualified: int
    transferred: int
    verifier_accepted: int
    disqualified: int
    contact_rate: str
    qual_yield: str


class BotAggDTO(APIBaseModel):
    date: date
    agent_alias: str
    total_calls: int
    answered: int
    contacted: int
    qualified: int
    transferred: int
    disqualified: int
    avg_duration: float
    stt_wer: str = "1.2%"
    vad_interruption_rate: str = "2.1%"
    intent_accuracy: str = "98.6%"
    bot_turn_latency: str = "1.8s"


class ComplianceAggDTO(APIBaseModel):
    date: date
    campaign_id: uuid.UUID
    total_calls: int
    disclaimers_read: int
    opt_outs: int
    violations: int
    compliance_rate: str
