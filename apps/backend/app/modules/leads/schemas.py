"""Lead DTOs and query models (camelCase on the wire).

The ``LeadDTO`` shape mirrors the dashboard ``Lead`` interface (spec section
11); the ``LeadImportJob`` machinery mirrors the ``LeadImportJob`` wizard
contract (spec section 12) including the validation counts the STEP 3 preview
renders before the user commits.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field

from app.packages.contracts.base import APIBaseModel
from app.packages.contracts.enums import (
    ImportJobStatus,
    LeadStatus,
    VicidialRunStatus,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 25_000
PREVIEW_SAMPLE_ROWS = 3


# ---------------------------------------------------------------------------
# Lead registry
# ---------------------------------------------------------------------------
class LeadDTO(APIBaseModel):
    """Wire model for one lead row (spec 11 ``Lead`` interface)."""

    id: uuid.UUID
    external_key: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    alt_phone: str | None = None
    email: str | None = None
    state: str | None = None
    zip_code: str | None = None
    date_of_birth: date | None = None
    age: int | None = None
    source: str | None = None
    source_batch_id: str | None = None
    campaign_id: uuid.UUID | None = None
    campaign_name: str | None = None
    status: LeadStatus = LeadStatus.NEW
    attempts: int = 0
    last_attempt_at: datetime | None = None
    next_attempt_at: datetime | None = None
    assigned_to: uuid.UUID | None = None
    suppressed: bool = False
    suppression_reason: str | None = None
    custom_fields: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class LeadCreate(APIBaseModel):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    phone: str = Field(min_length=10, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    state: str | None = Field(default=None, max_length=8)
    zip_code: str | None = Field(default=None, max_length=16)
    date_of_birth: date | None = None
    source: str | None = Field(default=None, max_length=120)
    source_batch_id: str | None = Field(default=None, max_length=64)
    campaign_id: uuid.UUID | None = None
    status: LeadStatus = LeadStatus.NEW
    assigned_to: uuid.UUID | None = None
    custom_fields: dict[str, Any] | None = None


class LeadUpdate(APIBaseModel):
    """PATCH /leads/{id} payload - extra fields forbidden (Step 27)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, min_length=10, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    state: str | None = Field(default=None, max_length=8)
    zip_code: str | None = Field(default=None, max_length=16)
    date_of_birth: date | None = None
    source: str | None = Field(default=None, max_length=120)
    source_batch_id: str | None = Field(default=None, max_length=64)
    campaign_id: uuid.UUID | None = None
    status: LeadStatus | None = None
    assigned_to: uuid.UUID | None = None
    custom_fields: dict[str, Any] | None = None


LeadPatch = LeadUpdate


class BulkAssignRequest(APIBaseModel):
    lead_ids: list[uuid.UUID]
    campaign_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None


class LeadListQuery(APIBaseModel):
    """Collection query parameters (all optional, whitelisted)."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    search: str | None = Field(default=None, max_length=160)
    status: LeadStatus | None = None
    suppressed: bool | None = None
    campaign_id: uuid.UUID | None = None
    source: str | None = Field(default=None, max_length=120)
    import_job_id: uuid.UUID | None = None
    sort: str | None = None
    order: str | None = None


class LeadBatchDTO(APIBaseModel):
    """Wire model for one imported CSV lead file batch."""

    id: uuid.UUID
    file_name: str
    status: ImportJobStatus = ImportJobStatus.COMPLETED
    total_rows: int = 0
    imported_rows: int = 0
    columns: list[str] = Field(default_factory=list)
    campaign_id: uuid.UUID | None = None
    campaign_name: str | None = None
    created_at: datetime
    # VICIdial run control (dashboard lead-list registry). ``vicidial_list_id``
    # is None until the list has been assigned a dialer list.
    vicidial_list_id: str | None = None
    vicidial_run_count: int = 0
    vicidial_status: VicidialRunStatus = VicidialRunStatus.IDLE
    is_active_for_vicidial: bool = False
    vicidial_started_at: datetime | None = None
    vicidial_stopped_at: datetime | None = None


class UpdateBatchCampaignRequest(APIBaseModel):
    campaign_id: uuid.UUID | None = None


class VicidialRunRequest(APIBaseModel):
    """Start or stop the dialer run for one imported lead list.

    Turning the run ON pushes the batch's leads into the VICIdial hopper and
    increments the run count.  Turning it OFF only changes TalkFlow state: the
    non-agent API exposes no list/hopper pause, so the dialer may still be
    working through records already in the hopper.
    """

    is_active: bool
    vicidial_list_id: str | None = None
    campaign_id: uuid.UUID | None = None


class VicidialRunResultDTO(APIBaseModel):
    """Outcome of a run toggle, including the hopper ingest tally."""

    batch_id: uuid.UUID
    vicidial_list_id: str | None = None
    vicidial_run_count: int = 0
    vicidial_status: VicidialRunStatus = VicidialRunStatus.IDLE
    is_active_for_vicidial: bool = False
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    dialer_lead_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CSV import wizard (spec 12 + 14 LEADS)
# ---------------------------------------------------------------------------
class ColumnPreview(APIBaseModel):
    """One source column: name + the first few values for the mapping table."""

    name: str
    sample_values: list[str] = Field(default_factory=list)


class ImportUploadResponse(APIBaseModel):
    """POST /leads/import result - the job waits for a column mapping."""

    job_id: uuid.UUID
    file_name: str
    status: ImportJobStatus
    total_rows: int
    columns: list[ColumnPreview] = Field(default_factory=list)


class ImportOptions(APIBaseModel):
    skip_invalid: bool = True
    skip_duplicates: bool = True
    update_existing: bool = False


class MappingRequest(APIBaseModel):
    """Step 4: source column -> TalkFlow field assignments + batch options.

    ``campaign_id`` / ``assigned_to`` are applied to every committed row; the
    mapping is the authoritative source of which CSV columns feed which fields.
    """

    mapping: dict[str, str]
    campaign_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    initial_status: LeadStatus = LeadStatus.NEW
    options: ImportOptions = Field(default_factory=ImportOptions)


class ValidationSummary(APIBaseModel):
    """STEP 3 preview strip describing what a commit will do."""

    total: int
    valid: int
    invalid: int
    duplicates_file: int = 0
    duplicates_system: int = 0
    suppressed: int = 0


class ImportJobDTO(APIBaseModel):
    """Wire model of one import job (dashboard ``LeadImportJob``)."""

    id: uuid.UUID
    file_name: str
    status: ImportJobStatus
    total_rows: int = 0
    imported_rows: int = 0
    duplicate_rows: int = 0
    suppressed_rows: int = 0
    invalid_rows: int = 0
    validation: ValidationSummary | None = None
    error_report_url: str | None = None
    campaign_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
