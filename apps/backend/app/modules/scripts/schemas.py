"""Pydantic schemas for the scripts module API contract."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import ScriptNodeType, ScriptStatus


class ScriptTransitionDTO(APIBaseModel):
    id: str = Field(default_factory=lambda: f"tr-{uuid.uuid4().hex[:6]}")
    when: str = "always"
    expression: str | None = None
    next_node_id: str | None = None
    end_call: bool = False
    disposition: str | None = None


class ScriptNodeDTO(APIBaseModel):
    id: str
    type: ScriptNodeType
    label: str
    prompt: str
    capture_field: str | None = None
    capture_type: str | None = None
    choices: list[str] | None = None
    required: bool = False
    max_retries: int = 1
    no_response_ms: int = 5000
    fallback_prompt: str | None = None
    transitions: list[ScriptTransitionDTO] = Field(default_factory=list)
    allow_barge_in: bool = True


class ScriptVersionSummaryDTO(APIBaseModel):
    id: uuid.UUID
    version: int
    status: ScriptStatus
    change_note: str | None = None
    created_by: str | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_reason: str | None = None


class ScriptVersionDTO(APIBaseModel):
    id: uuid.UUID
    script_id: uuid.UUID
    version: int
    status: ScriptStatus
    entry_node_id: str
    nodes: list[ScriptNodeDTO] = Field(default_factory=list)
    rule_set_id: uuid.UUID | None = None
    change_note: str | None = None
    created_by: str | None = None
    created_at: datetime
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_reason: str | None = None
    activated_at: datetime | None = None
    campaign_ids: list[str] = Field(default_factory=list)
    # Projections for dashboard editor view
    greeting: str | None = None
    consent: str | None = None
    qualification_questions: list[str] = Field(default_factory=list)
    transfer_message: str | None = None
    disqualification_message: str | None = None


class ScriptDTO(APIBaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    language: str
    current_version: int
    active_version: int | None = None
    active_version_id: uuid.UUID | None = None
    status: ScriptStatus
    versions: list[ScriptVersionSummaryDTO] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    version_counter: int = Field(alias="version", default=1)
    # Projections for simplified frontend components
    greeting: str | None = None
    consent: str | None = None
    qualification_questions: list[str] = Field(default_factory=list)
    transfer_message: str | None = None
    disqualification_message: str | None = None


class ScriptCreate(APIBaseModel):
    name: str
    description: str | None = None
    language: str = "en-US"
    entry_node_id: str = "node-1"
    nodes: list[ScriptNodeDTO] = Field(default_factory=list)
    rule_set_id: uuid.UUID | None = None
    # Helper fields for direct text-based creation
    greeting: str | None = None
    consent: str | None = None
    qualification_questions: list[str] | None = None
    transfer_message: str | None = None
    disqualification_message: str | None = None


class ScriptUpdate(APIBaseModel):
    name: str | None = None
    description: str | None = None
    language: str | None = None
    expected_version: int | None = None


class ScriptVersionCreate(APIBaseModel):
    from_version: int | None = None
    change_note: str | None = None
    entry_node_id: str | None = None
    nodes: list[ScriptNodeDTO] | None = None
    rule_set_id: uuid.UUID | None = None


class ScriptVersionUpdate(APIBaseModel):
    entry_node_id: str | None = None
    nodes: list[ScriptNodeDTO] | None = None
    rule_set_id: uuid.UUID | None = None
    change_note: str | None = None
    greeting: str | None = None
    consent: str | None = None
    qualification_questions: list[str] | None = None
    transfer_message: str | None = None
    disqualification_message: str | None = None


class ScriptVersionReject(APIBaseModel):
    reason: str


class ScriptVersionActivate(APIBaseModel):
    campaign_id: uuid.UUID | None = None


class ScriptDiffDTO(APIBaseModel):
    script_id: uuid.UUID
    version: int
    against_version: int
    added_nodes: list[dict[str, Any]] = Field(default_factory=list)
    removed_nodes: list[dict[str, Any]] = Field(default_factory=list)
    modified_nodes: list[dict[str, Any]] = Field(default_factory=list)
    diff_summary: str


class SimulationInput(APIBaseModel):
    node_id: str
    user_response: str | None = None
    no_response: bool = False


class ScriptSimulationRequest(APIBaseModel):
    inputs: list[SimulationInput] = Field(default_factory=list)


class ScriptSimulationStepDTO(APIBaseModel):
    step: int
    node_id: str
    node_type: str
    prompt: str
    user_response: str | None = None
    transition_taken: str | None = None
    captured_field: str | None = None
    captured_value: Any = None


class ScriptSimulationResultDTO(APIBaseModel):
    steps: list[ScriptSimulationStepDTO] = Field(default_factory=list)
    spoken_prompts: list[str] = Field(default_factory=list)
    captured_fields: dict[str, Any] = Field(default_factory=dict)
    final_disposition: str | None = None
    completed: bool = False


class ScriptListQuery(APIBaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: ScriptStatus | None = None
    search: str | None = None
    sort: str | None = None
    order: str | None = None
