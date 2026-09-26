"""Lead service - registry CRUD + the resumable CSV import wizard.

The wizard runs SYNCHRONOUSLY inside the request (background workers would race
the test engine's per-request session), but its progress is fully persisted on
``lead_import_jobs`` so it is resumable *and* idempotent: re-POSTing the commit
for a ``completed`` job returns the existing result without re-importing.

Only the rows that survive STEP 3 live on the job; the skipped rows are written
to a CSV error report in object storage and served from ``/errors``.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.core.security import mask_phone
from app.modules.leads import repository as repo
from app.modules.leads.errors import (
    CampaignNotFoundError,
    ImportEmptyError,
    ImportFileTooLargeError,
    ImportInvalidStateError,
    ImportJobNotFoundError,
    ImportMappingInvalidError,
    ImportNoErrorsError,
    ImportNoMappingError,
    LeadInvalidPhoneError,
    LeadNotFoundError,
    VicidialIngestFailedError,
    VicidialNotConfiguredError,
    VicidialNothingToSubmitError,
)
from app.modules.leads.events import (
    IMPORT_JOB_AGGREGATE,
    LEAD_AGGREGATE,
    LeadEventType,
    publish_lead_event,
)
from app.modules.leads.policies import (
    classify_row,
    generate_external_key,
    missing_required_fields,
    prepare_row,
    resolve_scope_constraints,
)
from app.modules.leads.schemas import (
    MAX_IMPORT_ROWS,
    MAX_UPLOAD_BYTES,
    PREVIEW_SAMPLE_ROWS,
    BulkAssignRequest,
    ColumnPreview,
    ImportJobDTO,
    ImportUploadResponse,
    LeadBatchDTO,
    LeadCreate,
    LeadDTO,
    LeadListQuery,
    LeadUpdate,
    MappingRequest,
    ValidationSummary,
    VicidialRunResultDTO,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import (
    AuditResult,
    ImportJobStatus,
    LeadStatus,
    VicidialRunStatus,
)
from app.packages.db.models import Lead, LeadImportJob
from app.packages.phone import normalize_us_phone
from app.packages.vicidial.client import VicidialClient
from app.packages.vicidial.credentials import get_vicidial_credentials
from app.packages.vicidial.parser import extract_added_lead_id

logger = structlog.get_logger("leads.service")

_UPDATABLE_LEAD_FIELDS = (
    "first_name",
    "last_name",
    "alt_phone",
    "email",
    "state",
    "zip_code",
    "date_of_birth",
    "source",
    "source_batch_id",
    "campaign_id",
    "status",
    "assigned_to",
    "custom_fields",
)


def _json_safe(values: dict[str, Any]) -> dict[str, Any]:
    """JSONB cache (job.rows) holds ISO strings, not Python dates."""
    return {
        key: value.isoformat() if isinstance(value, (date, datetime)) else value
        for key, value in values.items()
    }


def _dob_value(value: Any) -> date | None:
    """Round-trip the DOB stored in the job cache back to a real date."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _to_dto(row: tuple[Lead, str | None]) -> LeadDTO:
    lead, campaign_name = row
    return LeadDTO(
        id=lead.id,
        external_key=lead.external_key or generate_external_key(),
        first_name=lead.first_name,
        last_name=lead.last_name,
        phone=lead.phone_normalized,
        alt_phone=lead.alt_phone,
        email=lead.email,
        state=lead.state,
        zip_code=lead.zip_code,
        date_of_birth=lead.date_of_birth,
        age=lead.age,
        source=lead.source,
        source_batch_id=lead.source_batch_id,
        campaign_id=lead.campaign_id,
        campaign_name=campaign_name,
        status=LeadStatus(lead.status),
        attempts=lead.attempts or 0,
        last_attempt_at=lead.last_attempt_at,
        next_attempt_at=lead.next_attempt_at,
        assigned_to=lead.assigned_to,
        suppressed=lead.suppressed,
        suppression_reason=lead.suppression_reason,
        custom_fields=lead.custom_fields,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


def _column_names(columns: Any) -> list[str]:
    """Flatten a job's column previews down to their header names.

    ``LeadImportJob.columns`` stores ``{"name", "sample_values"}`` objects for the
    mapping table, but the batch registry DTO (and the dashboard table that
    consumes it) is a plain list of header strings.
    """
    names: list[str] = []
    for column in columns or []:
        if isinstance(column, dict):
            name = column.get("name")
        else:
            name = column
        if name:
            names.append(str(name))
    return names


def _to_import_job_dto(job: LeadImportJob) -> ImportJobDTO:
    validation = None
    if job.validation:
        validation = ValidationSummary(**job.validation)
    error_report_url = (
        f"/api/v1/leads/import/{job.id}/errors" if job.error_report_key else None
    )
    return ImportJobDTO(
        id=job.id,
        file_name=job.file_name,
        status=ImportJobStatus(job.status),
        total_rows=job.total_rows,
        imported_rows=job.imported_rows,
        duplicate_rows=job.duplicate_rows,
        suppressed_rows=job.suppressed_rows,
        invalid_rows=job.invalid_rows,
        validation=validation,
        error_report_url=error_report_url,
        campaign_id=job.campaign_id,
        created_by=job.created_by,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _load_lead(
    session: AsyncSession, user: UserContext, lead_id: uuid.UUID
) -> tuple[Lead, str | None]:
    row = await repo.get_lead(session, lead_id, resolve_scope_constraints(user))
    if row is None:
        raise LeadNotFoundError()
    return row


async def _load_job(
    session: AsyncSession, user: UserContext, job_id: uuid.UUID
) -> LeadImportJob:
    job = await repo.get_import_job(session, job_id, resolve_scope_constraints(user))
    if job is None:
        raise ImportJobNotFoundError(job_id)
    return job


def _parse_csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportEmptyError()
    rows = [
        {key: (value or "").strip() for key, value in row.items()} for row in reader
    ]
    return list(reader.fieldnames), rows


def _build_error_report(errors: list[tuple[int, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "reason"])
    for row_no, reason in errors:
        writer.writerow([row_no, reason])
    return buffer.getvalue().encode("utf-8")


def _phone_from_row(row: dict[str, str], mapping: dict[str, str]) -> str | None:
    source_col = mapping.get("phone")
    if not source_col:
        return None
    return normalize_us_phone(str(row.get(source_col) or ""))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
async def list_leads(
    session: AsyncSession, user: UserContext, query: LeadListQuery
) -> PagedResponse[LeadDTO]:
    rows, total = await repo.list_leads(session, query, resolve_scope_constraints(user))
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[LeadDTO](
        data=[_to_dto(row) for row in rows],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            sort=query.sort,
            order=query.order,
        ),
    )


async def get_lead(
    session: AsyncSession, user: UserContext, lead_id: uuid.UUID
) -> DataResponse[LeadDTO]:
    return DataResponse[LeadDTO](data=_to_dto(await _load_lead(session, user, lead_id)))


async def get_import_job(
    session: AsyncSession, user: UserContext, job_id: uuid.UUID
) -> DataResponse[ImportJobDTO]:
    return DataResponse[ImportJobDTO](
        data=_to_import_job_dto(await _load_job(session, user, job_id))
    )


async def list_batches(
    session: AsyncSession, user: UserContext
) -> DataResponse[list[LeadBatchDTO]]:
    _ = user
    rows = await repo.list_import_batches(session)
    dtos = [
        LeadBatchDTO(
            id=job.id,
            file_name=job.file_name,
            status=ImportJobStatus(job.status),
            total_rows=job.total_rows,
            imported_rows=job.imported_rows,
            columns=_column_names(job.columns),
            campaign_id=job.campaign_id,
            campaign_name=campaign_name,
            created_at=job.created_at,
            vicidial_list_id=job.vicidial_list_id,
            vicidial_run_count=job.vicidial_run_count,
            vicidial_status=VicidialRunStatus(job.vicidial_status),
            is_active_for_vicidial=job.is_active_for_vicidial,
            vicidial_started_at=job.vicidial_started_at,
            vicidial_stopped_at=job.vicidial_stopped_at,
        )
        for job, campaign_name in rows
    ]
    return DataResponse[list[LeadBatchDTO]](data=dtos)


async def update_batch_campaign(
    session: AsyncSession,
    user: UserContext,
    job_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
) -> DataResponse[dict[str, Any]]:
    _ = user
    await repo.update_job_campaign(session, job_id, campaign_id)
    await session.commit()
    return DataResponse[dict[str, Any]](
        data={
            "status": "ok",
            "jobId": str(job_id),
            "campaignId": str(campaign_id) if campaign_id else None,
        }
    )


# ---------------------------------------------------------------------------
# VICIdial run control (lead-list registry)
# ---------------------------------------------------------------------------
# Bounds one hopper ingest. A 25k-row batch cannot be pushed in a single
# request without holding the connection open for minutes, so the toggle queues
# at most this many records and reports the rest as not-submitted. The operator
# re-toggles to continue; ``run_count`` only advances on a successful push.
_MAX_HOPPER_INGEST = 500


def _resolve_run_credentials() -> tuple[str, str, str]:
    """Return ``(list_id, campaign_id, source)`` for the hopper ingest.

    Raises :class:`VicidialNotConfiguredError` when the dialer has no API user
    configured - a silent no-op here would show a green "running" tick in the
    dashboard for a list that is in fact sitting in TalkFlow only.
    """
    creds = get_vicidial_credentials()
    if not creds.user or not creds.password or not creds.url:
        raise VicidialNotConfiguredError()
    return creds.default_list_id, creds.default_campaign_id, creds.source


async def set_vicidial_run(
    session: AsyncSession,
    user: UserContext,
    job_id: uuid.UUID,
    *,
    is_active: bool,
    vicidial_list_id: str | None = None,
    campaign_id: uuid.UUID | None = None,
) -> DataResponse[VicidialRunResultDTO]:
    """Start or stop the VICIdial run for one imported lead list.

    Starting pushes the batch's committed leads into the dialer hopper with
    ``add_to_hopper`` set and increments ``vicidial_run_count``.  Stopping only
    records ``interrupted`` in TalkFlow: the non-agent API exposes no
    list/hopper pause, so records already queued may still be dialed.
    """
    job = await repo.get_import_job(session, job_id, resolve_scope_constraints(user))
    if job is None:
        raise ImportJobNotFoundError(job_id)

    now = datetime.now(UTC)

    # Persist an explicit list/campaign override before acting on it so the
    # registry shows the same mapping the ingest actually used.
    if campaign_id is not None and job.campaign_id != campaign_id:
        job.campaign_id = campaign_id
    if vicidial_list_id:
        job.vicidial_list_id = str(vicidial_list_id)

    if not is_active:
        job.vicidial_status = VicidialRunStatus.INTERRUPTED.value
        job.is_active_for_vicidial = False
        job.vicidial_stopped_at = now
        await write_audit(
            session,
            actor_id=user.user_id,
            actor_role=user.role,
            action="lead.vicidial_run.stop",
            resource_type="lead_import_job",
            resource_id=str(job.id),
            result=AuditResult.SUCCESS,
            details={"vicidial_list_id": job.vicidial_list_id},
        )
        await publish_lead_event(
            session,
            aggregate_type=IMPORT_JOB_AGGREGATE,
            aggregate_id=job.id,
            event_type=LeadEventType.VICIDIAL_RUN_STOPPED,
            payload={"vicidial_list_id": job.vicidial_list_id},
        )
        await session.commit()
        return DataResponse[VicidialRunResultDTO](
            data=VicidialRunResultDTO(
                batch_id=job.id,
                vicidial_list_id=job.vicidial_list_id,
                vicidial_run_count=job.vicidial_run_count,
                vicidial_status=VicidialRunStatus(job.vicidial_status),
                is_active_for_vicidial=False,
            )
        )

    # --- Start the run -----------------------------------------------------
    default_list_id, default_campaign_id, source = _resolve_run_credentials()
    resolved_list_id = str(job.vicidial_list_id or default_list_id)
    job.vicidial_list_id = resolved_list_id

    dialer_campaign_id = default_campaign_id
    if job.campaign_id is not None:
        name = await repo.campaign_name(session, job.campaign_id)
        if name:
            dialer_campaign_id = name

    # Only leads the dialer has never accepted are eligible, so re-toggling ON
    # continues the ingest instead of re-pushing leads already in the hopper.
    leads = await repo.list_batch_leads(
        session, job, pending_only=True, limit=_MAX_HOPPER_INGEST
    )
    submitted = leads
    errors: list[str] = []
    dialer_lead_ids: list[str] = []
    id_pairs: list[tuple[str, uuid.UUID]] = []

    if submitted:
        phones_to_check = [
            phone for lead in submitted
            if (phone := (lead.phone_normalized or lead.phone_raw)) is not None
        ]
        suppressed_set = await repo.active_suppressed_phones(session, phones_to_check)

        creds = get_vicidial_credentials()
        async with VicidialClient(creds) as client:
            for lead in submitted:
                phone = lead.phone_normalized or lead.phone_raw
                if not phone:
                    errors.append(f"{lead.external_key}: no dialable phone number")
                    continue

                # Real-Time DNC Cross-Check Guard (Anti-Lawsuit Protection)
                is_dnc = (
                    phone in suppressed_set
                    or lead.suppressed
                    or (lead.status and str(lead.status).lower() in ("dnc", "suppressed", "opt-out", "opt_out", "do not call"))
                )

                if is_dnc:
                    lead.suppressed = True
                    lead.suppression_reason = "dnc_guard"
                    try:
                        await client.add_dnc_phone(phone)
                        logger.info("dnc guard blocked lead and registered in vicidial dnc", phone=phone, lead_id=str(lead.id))
                    except Exception as exc:
                        logger.warning("failed to register blocked phone in vicidial dnc", phone=phone, error=str(exc))
                    errors.append(f"{lead.external_key}: blocked by Real-Time DNC Cross-Check Guard & registered in VICIdial DNC")
                    continue

                try:
                    response = await client.add_lead(
                        phone,
                        list_id=resolved_list_id,
                        campaign_id=dialer_campaign_id,
                        add_to_hopper=True,
                        vendor_lead_code=lead.external_key,
                    )
                except httpx.HTTPError as exc:
                    # A transport failure is not a per-lead rejection: the whole
                    # dialer is unreachable, so stop hammering it.
                    logger.warning(
                        "vicidial hopper ingest aborted",
                        batch_id=str(job.id),
                        reason=str(exc),
                    )
                    errors.append(f"dialer unreachable: {exc}")
                    break

                if not response.success:
                    errors.append(
                        f"{lead.external_key}: {response.error or 'rejected by dialer'}"
                    )
                    continue

                dialer_id = extract_added_lead_id(response)
                if dialer_id:
                    dialer_lead_ids.append(dialer_id)
                    id_pairs.append((dialer_id, lead.id))

    if not leads:
        # Every lead in this batch already has a dialer id, so there is nothing
        # left to hand to the hopper.  Do not burn a run count on a no-op.
        raise VicidialNothingToSubmitError(
            details={"batch_id": str(job.id), "vicidial_list_id": resolved_list_id}
        )

    if not dialer_lead_ids:
        # Nothing reached the dialer - leave the list idle rather than claim a
        # run that never happened.
        job.vicidial_status = VicidialRunStatus.IDLE.value
        job.is_active_for_vicidial = False
        await session.commit()
        raise VicidialIngestFailedError(
            details={
                "submitted": len(submitted),
                "accepted": 0,
                "errors": errors[:10],
            }
        )

    await repo.set_vicidial_lead_ids(session, id_pairs)
    job.vicidial_run_count += 1
    job.vicidial_status = VicidialRunStatus.RUNNING.value
    job.is_active_for_vicidial = True
    job.vicidial_started_at = now
    job.vicidial_stopped_at = None

    accepted = len(dialer_lead_ids)
    result = VicidialRunResultDTO(
        batch_id=job.id,
        vicidial_list_id=resolved_list_id,
        vicidial_run_count=job.vicidial_run_count,
        vicidial_status=VicidialRunStatus.RUNNING,
        is_active_for_vicidial=True,
        submitted=len(submitted),
        accepted=accepted,
        rejected=len(errors),
        dialer_lead_ids=dialer_lead_ids,
        errors=errors[:10],
    )

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.vicidial_run.start",
        resource_type="lead_import_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={
            "vicidial_list_id": resolved_list_id,
            "dialer_campaign_id": dialer_campaign_id,
            "source": source,
            "submitted": result.submitted,
            "accepted": accepted,
            "rejected": result.rejected,
        },
    )
    await publish_lead_event(
        session,
        aggregate_type=IMPORT_JOB_AGGREGATE,
        aggregate_id=job.id,
        event_type=LeadEventType.VICIDIAL_RUN_STARTED,
        payload={
            "vicidial_list_id": resolved_list_id,
            "dialer_campaign_id": dialer_campaign_id,
            "run_count": job.vicidial_run_count,
            "accepted": accepted,
        },
    )
    await session.commit()
    return DataResponse[VicidialRunResultDTO](data=result)


async def delete_batch(
    session: AsyncSession,
    user: UserContext,
    job_id: str,
) -> DataResponse[dict[str, Any]]:
    _ = user
    deleted = await repo.delete_import_batch(session, job_id)
    await session.commit()
    return DataResponse[dict[str, Any]](
        data={"deleted": deleted, "batchId": str(job_id)}
    )


async def get_error_report(
    session: AsyncSession, user: UserContext, job_id: uuid.UUID
) -> tuple[bytes, str]:
    """Return (csv_bytes, download_filename) for the skipped-rows report."""
    job = await _load_job(session, user, job_id)
    if not job.error_report_key:
        raise ImportNoErrorsError()

    from app.packages.storage.provider import get_storage_provider

    storage = get_storage_provider()
    data = await storage.read_bytes(job.error_report_key)
    stem = Path(job.file_name).stem or "import"
    return data, f"{stem}_errors.csv"


# ---------------------------------------------------------------------------
# Single-lead writes
# ---------------------------------------------------------------------------
async def create_lead(
    session: AsyncSession, user: UserContext, payload: LeadCreate
) -> DataResponse[LeadDTO]:
    phone = normalize_us_phone(payload.phone)
    if phone is None:
        raise LeadInvalidPhoneError()
    if (
        payload.campaign_id is not None
        and await repo.campaign_name(session, payload.campaign_id) is None
    ):
        raise CampaignNotFoundError(payload.campaign_id)

    lead = Lead(
        external_key=generate_external_key(),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_normalized=phone,
        phone_raw=payload.phone,
        alt_phone=payload.alt_phone,
        email=payload.email,
        state=payload.state,
        zip_code=payload.zip_code,
        date_of_birth=payload.date_of_birth,
        source=payload.source,
        source_batch_id=payload.source_batch_id,
        campaign_id=payload.campaign_id,
        status=payload.status.value,
        assigned_to=payload.assigned_to,
        custom_fields=payload.custom_fields,
    )
    await repo.save_lead(session, lead)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.create",
        resource_type="lead",
        resource_id=str(lead.id),
        result=AuditResult.SUCCESS,
        details={"phone": mask_phone(phone), "source": payload.source},
    )
    await publish_lead_event(
        session,
        aggregate_type=LEAD_AGGREGATE,
        aggregate_id=lead.id,
        event_type=LeadEventType.LEAD_CREATED,
        payload={"phone": mask_phone(phone), "status": lead.status},
    )
    await session.commit()
    row = await repo.get_lead(session, lead.id, resolve_scope_constraints(user))
    assert row is not None
    return DataResponse[LeadDTO](data=_to_dto(row))


async def update_lead(
    session: AsyncSession,
    user: UserContext,
    lead_id: uuid.UUID,
    payload: LeadUpdate,
) -> DataResponse[LeadDTO]:
    lead, _ = await _load_lead(session, user, lead_id)
    data = payload.model_dump(exclude_unset=True)

    for field in _UPDATABLE_LEAD_FIELDS:
        if field in data:
            setattr(lead, field, data[field])
    if "phone" in data:
        normalized = normalize_us_phone(str(data["phone"]))
        if normalized is None:
            raise LeadInvalidPhoneError()
        lead.phone_normalized = normalized
        data.pop("phone")
        data["phone_normalized"] = normalized

    await repo.save_lead(session, lead)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.update",
        resource_type="lead",
        resource_id=str(lead.id),
        result=AuditResult.SUCCESS,
        details={"fields": sorted(data)},
    )
    await publish_lead_event(
        session,
        aggregate_type=LEAD_AGGREGATE,
        aggregate_id=lead.id,
        event_type=LeadEventType.LEAD_UPDATED,
        payload={"status": lead.status},
    )
    await session.commit()
    row = await repo.get_lead(session, lead.id, resolve_scope_constraints(user))
    assert row is not None
    return DataResponse[LeadDTO](data=_to_dto(row))


# ---------------------------------------------------------------------------
# CSV import wizard
# ---------------------------------------------------------------------------
async def upload_import(
    session: AsyncSession, user: UserContext, file: UploadFile
) -> DataResponse[ImportUploadResponse]:
    """STEP 1-2: parse the CSV, infer columns, hold rows for STEP 3.

    No leads are written here; the job parks in ``mapping`` until the caller
    saves a column assignment.
    """
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ImportFileTooLargeError(details={"max_bytes": MAX_UPLOAD_BYTES})
    headers, rows = _parse_csv(payload)
    if not rows:
        raise ImportEmptyError()
    if len(rows) > MAX_IMPORT_ROWS:
        raise ImportFileTooLargeError(
            details={"max_rows": MAX_IMPORT_ROWS, "received": len(rows)}
        )

    job = LeadImportJob(
        file_name=Path(file.filename or "import.csv").name,
        status=ImportJobStatus.MAPPING.value,
        total_rows=len(rows),
        columns=[
            {
                "name": header,
                "sample_values": [
                    row.get(header, "") for row in rows[:PREVIEW_SAMPLE_ROWS]
                ],
            }
            for header in headers
        ],
        rows=rows,
    )
    await repo.save_import_job(session, job)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.import.upload",
        resource_type="lead_import_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={"file_name": job.file_name, "rows": len(rows)},
    )
    await publish_lead_event(
        session,
        aggregate_type=IMPORT_JOB_AGGREGATE,
        aggregate_id=job.id,
        event_type=LeadEventType.IMPORT_UPLOADED,
        payload={"file_name": job.file_name, "rows": len(rows)},
    )
    await session.commit()
    logger.info(
        "import uploaded", job_id=str(job.id), rows=len(rows), actor=str(user.user_id)
    )
    return DataResponse[ImportUploadResponse](
        data=ImportUploadResponse(
            job_id=job.id,
            file_name=job.file_name,
            status=ImportJobStatus(job.status),
            total_rows=len(rows),
            columns=[ColumnPreview(**column) for column in (job.columns or [])],
        )
    )


async def save_mapping(
    session: AsyncSession,
    user: UserContext,
    job_id: uuid.UUID,
    payload: MappingRequest,
) -> DataResponse[ImportJobDTO]:
    """STEP 3-4: validate the mapping, classify every row, write the report.

    Produces the persisted ``rows`` the commit consumes exactly, plus the
    counters the STEP 5 preview surfaces.  Only valid rows survive; the skipped
    rows land in a CSV error report the caller can download.
    """
    job = await _load_job(session, user, job_id)
    if job.status not in (
        ImportJobStatus.MAPPING.value,
        ImportJobStatus.VALIDATING.value,
    ):
        raise ImportInvalidStateError(
            details={
                "status": job.status,
                "reason": "Mapping is only editable before commit.",
            }
        )

    missing = missing_required_fields(payload.mapping)
    if missing:
        raise ImportMappingInvalidError(missing)
    if (
        payload.campaign_id is not None
        and await repo.campaign_name(session, payload.campaign_id) is None
    ):
        raise CampaignNotFoundError(payload.campaign_id)

    job.mapping = payload.mapping
    job.campaign_id = payload.campaign_id
    job.options = {
        "assigned_to": str(payload.assigned_to) if payload.assigned_to else None,
        "initial_status": payload.initial_status.value,
        **payload.options.model_dump(),
    }

    all_phones = [
        phone
        for row in (job.rows or [])
        if (phone := _phone_from_row(row, payload.mapping)) is not None
    ]
    existing_phones = await repo.existing_phone_numbers(session, all_phones)
    suppressed_phones = await repo.active_suppressed_phones(session, all_phones)

    candidates: list[dict[str, Any]] = []
    errors: list[tuple[int, str]] = []
    seen_in_file: set[str] = set()
    counts = {
        "total": len(job.rows or []),
        "valid": 0,
        "invalid": 0,
        "duplicates_file": 0,
        "duplicates_system": 0,
        "suppressed": 0,
    }

    for file_line, row in enumerate(job.rows or [], start=2):  # header is line 1
        prepared, reason = prepare_row(row, payload.mapping)
        if prepared is None:
            counts["invalid"] += 1
            errors.append((file_line, reason or "invalid"))
            continue

        phone = prepared.system["phone"]
        verdict = classify_row(
            phone,
            seen_in_file=seen_in_file,
            existing_phones=existing_phones,
            suppressed_phones=suppressed_phones,
        )
        if verdict.kind == "suppressed":
            counts["suppressed"] += 1
            errors.append((file_line, verdict.reason or "suppressed_dnc"))
            continue
        if verdict.kind == "duplicate":
            duplicate_in_file = verdict.reason == "duplicate_in_file"
            if not duplicate_in_file and payload.options.update_existing:
                candidates.append(
                    {
                        "kind": "update",
                        "system": prepared.system,
                        "custom": prepared.custom,
                    }
                )
                counts["valid"] += 1
                counts["duplicates_system"] += 1
                continue
            if duplicate_in_file:
                counts["duplicates_file"] += 1
            else:
                counts["duplicates_system"] += 1
            errors.append((file_line, verdict.reason or "duplicate"))
            continue

        seen_in_file.add(phone)
        candidates.append(
            {"kind": "insert", "system": prepared.system, "custom": prepared.custom}
        )
        counts["valid"] += 1

    job.rows = [
        {
            "kind": candidate["kind"],
            "system": _json_safe(candidate["system"]),
            "custom": candidate["custom"],
        }
        for candidate in candidates
    ]
    job.imported_rows = counts["valid"]
    job.invalid_rows = counts["invalid"]
    job.duplicate_rows = counts["duplicates_file"] + counts["duplicates_system"]
    job.suppressed_rows = counts["suppressed"]
    job.validation = counts
    job.status = ImportJobStatus.VALIDATING.value

    if errors:
        from app.packages.storage.provider import get_storage_provider

        storage = get_storage_provider()
        key = f"imports/{job.id}_errors.csv"
        await storage.put_bytes(
            key, _build_error_report(errors), content_type="text/csv"
        )
        job.error_report_key = key

    await repo.save_import_job(session, job)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.import.mapping",
        resource_type="lead_import_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={"fields": sorted(payload.mapping.values()), "counts": counts},
    )
    await publish_lead_event(
        session,
        aggregate_type=IMPORT_JOB_AGGREGATE,
        aggregate_id=job.id,
        event_type=LeadEventType.IMPORT_MAPPING_SAVED,
        payload={"counts": counts},
    )
    await session.commit()
    return DataResponse[ImportJobDTO](data=_to_import_job_dto(job))


async def bulk_assign_leads(
    session: AsyncSession, user: UserContext, payload: BulkAssignRequest
) -> DataResponse[dict[str, Any]]:
    """Bulk assign leads to campaign or user (Step 27)."""
    count = await repo.bulk_assign(
        session,
        lead_ids=payload.lead_ids,
        campaign_id=payload.campaign_id,
        assigned_to=payload.assigned_to,
    )
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.bulk_assign",
        resource_type="lead",
        resource_id="bulk",
        result=AuditResult.SUCCESS,
        details={
            "count": count,
            "campaign_id": str(payload.campaign_id) if payload.campaign_id else None,
        },
    )
    await session.commit()
    return DataResponse[dict[str, Any]](
        data={
            "updated_count": count,
            "lead_ids": [str(lid) for lid in payload.lead_ids],
        }
    )


async def commit_import(
    session: AsyncSession,
    user: UserContext,
    job_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> DataResponse[ImportJobDTO]:
    """STEP 5: insert the surviving rows in batches of 1000 and mark the job complete (Step 28).

    Idempotent: committing an already-``completed`` job returns it unchanged so
    a retried request can never double-import.
    """
    _ = idempotency_key
    job = await _load_job(session, user, job_id)

    if job.status == ImportJobStatus.COMPLETED.value:
        return DataResponse[ImportJobDTO](data=_to_import_job_dto(job))
    if job.status != ImportJobStatus.VALIDATING.value:
        raise ImportInvalidStateError(
            details={
                "status": job.status,
                "reason": "Save the column mapping before committing.",
            }
        )
    if not job.mapping:
        raise ImportNoMappingError()

    now = datetime.now(UTC)
    options = job.options or {}
    campaign_id = job.campaign_id
    assigned_to = (
        uuid.UUID(options["assigned_to"]) if options.get("assigned_to") else None
    )
    initial_status = options.get("initial_status", LeadStatus.NEW.value)

    inserts: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    for candidate in job.rows or []:
        system: dict[str, Any] = candidate["system"]
        custom: dict[str, Any] = candidate["custom"]
        if candidate["kind"] == "update":
            updates.append(
                {
                    "phone": system["phone"],
                    "first_name": system.get("first_name"),
                    "last_name": system.get("last_name"),
                    "alt_phone": system.get("alt_phone"),
                    "email": system.get("email"),
                    "state": system.get("state"),
                    "zip_code": system.get("zip_code"),
                    "date_of_birth": _dob_value(system.get("date_of_birth")),
                    "source": system.get("source"),
                    "source_batch_id": system.get("source_batch_id"),
                    "custom_fields": custom or None,
                }
            )
            continue
        inserts.append(
            {
                "id": uuid.uuid4(),
                "external_key": generate_external_key(),
                "first_name": system.get("first_name"),
                "last_name": system.get("last_name"),
                "phone_normalized": system["phone"],
                "phone_raw": system.get("phone"),
                "alt_phone": system.get("alt_phone"),
                "email": system.get("email"),
                "state": system.get("state"),
                "zip_code": system.get("zip_code"),
                "date_of_birth": _dob_value(system.get("date_of_birth")),
                "source": system.get("source"),
                "source_batch_id": system.get("source_batch_id"),
                "campaign_id": campaign_id,
                "status": initial_status,
                "assigned_to": assigned_to,
                "custom_fields": custom or None,
                "imported": True,
                "imported_at": now,
                "import_job_id": job.id,
                "created_at": now,
                "updated_at": now,
            }
        )

    job.status = ImportJobStatus.IMPORTING.value
    await repo.save_import_job(session, job)
    await session.flush()

    # Batch insert in chunks of 1,000 (Step 28)
    for i in range(0, len(inserts), 1000):
        batch = inserts[i : i + 1000]
        await repo.bulk_insert_leads(session, batch)

    await repo.bulk_update_leads_by_phone(session, updates)

    job.imported_rows = len(inserts) + len(updates)
    job.status = ImportJobStatus.COMPLETED.value
    job.committed_at = now
    await repo.save_import_job(session, job)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="lead.import.commit",
        resource_type="lead_import_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={
            "inserted": len(inserts),
            "updated": len(updates),
            "counts": job.validation or {},
        },
    )
    await publish_lead_event(
        session,
        aggregate_type=IMPORT_JOB_AGGREGATE,
        aggregate_id=job.id,
        event_type=LeadEventType.IMPORT_COMMITTED,
        payload={"inserted": len(inserts), "updated": len(updates)},
    )
    await session.commit()
    logger.info(
        "import committed",
        job_id=str(job.id),
        inserted=len(inserts),
        updated=len(updates),
        actor=str(user.user_id),
    )
    return DataResponse[ImportJobDTO](data=_to_import_job_dto(job))
