"""Export service - request -> process -> store -> download.

Processing runs synchronously inside the request (a background task would race
the test engine's per-request session); every stage transition is persisted on
the ``exports`` row so the history the dashboard renders is trustworthy and
download URLs only exist for ``ready`` jobs.

Phone numbers in lead exports are masked for tenants without ``pii.view_full``
/ ``lead.view`` (REPORTING_USER) - masking happens at CSV build time.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.modules.exports import repository as repo
from app.modules.exports.errors import (
    ExportFiltersInvalidError,
    ExportNotFoundError,
    ExportNotReadyError,
    ExportUnsupportedReportError,
)
from app.modules.exports.events import (
    ExportEventType,
    publish_export_event,
)
from app.modules.exports.policies import (
    SUPPORTED_REPORTS,
    ExportPolicy,
    build_csv,
    headers_for,
    is_supported_report,
)
from app.modules.exports.schemas import (
    ExportFilters,
    ExportJobDTO,
    ExportListQuery,
    ExportRequest,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, ExportFormat, ExportStatus
from app.packages.db.base import uuid7
from app.packages.db.models import ExportJob

logger = structlog.get_logger("exports.service")

_MAX_ROWS = 100_000


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _filter_dict(filters: ExportFilters | None) -> dict | None:
    if filters is None:
        return None
    return filters.model_dump(exclude_none=True) or None


def _to_dto(job: ExportJob) -> ExportJobDTO:
    download_url = None
    if job.status == ExportStatus.READY.value and job.storage_key:
        download_url = f"/api/v1/exports/{job.id}/download"
    return ExportJobDTO(
        id=job.id,
        report=job.report,
        format=ExportFormat(job.format),
        filters=job.filters,
        status=ExportStatus(job.status),
        row_count=job.row_count,
        error=job.error,
        download_url=download_url,
        created_by=job.created_by,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
async def list_exports(
    session: AsyncSession, user: UserContext, query: ExportListQuery
) -> PagedResponse[ExportJobDTO]:
    rows, total = await repo.list_exports(session, query)
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[ExportJobDTO](
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


async def get_export(
    session: AsyncSession, user: UserContext, job_id: uuid.UUID
) -> DataResponse[ExportJobDTO]:
    job = await repo.get_export(session, job_id)
    if job is None:
        raise ExportNotFoundError()
    return DataResponse[ExportJobDTO](data=_to_dto(job))


async def download_export(
    session: AsyncSession, user: UserContext, job_id: uuid.UUID
) -> tuple[bytes, str]:
    """Stream the artifact; only ``ready`` jobs have one (audit logged)."""
    job = await repo.get_export(session, job_id)
    if job is None:
        raise ExportNotFoundError()
    if job.status != ExportStatus.READY.value or not job.storage_key:
        raise ExportNotReadyError(details={"status": job.status})

    from app.packages.storage.provider import get_storage_provider

    storage = get_storage_provider()
    data = await storage.read_bytes(job.storage_key)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="export.download",
        resource_type="export_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={"report": job.report, "rows": job.row_count},
    )
    await session.commit()
    logger.info(
        "export downloaded", job_id=str(job.id), actor=str(user.user_id)
    )
    filename = f"{job.report}_{job.id.hex[:8]}.csv"
    return data, filename


# ---------------------------------------------------------------------------
# Create + process
# ---------------------------------------------------------------------------
async def create_export(
    session: AsyncSession, user: UserContext, payload: ExportRequest
) -> DataResponse[ExportJobDTO]:
    """Create, then synchronously process the export.

    Failures are captured on the job (``status=failed`` + ``error``) rather than
    surfaced as HTTP 500s so the export history stays complete.
    """
    if not is_supported_report(payload.report):
        raise ExportUnsupportedReportError(payload.report, sorted(SUPPORTED_REPORTS))

    filters = payload.filters or ExportFilters()
    if filters.campaign_id is not None and payload.report in ("campaigns",):
        raise ExportFiltersInvalidError(
            details={"reason": "campaign filter does not apply to campaign reports"}
        )

    job = ExportJob(
        id=uuid7(),
        report=payload.report,
        format="csv",
        filters=_filter_dict(filters),
        status=ExportStatus.QUEUED.value,
        created_by=user.user_id,
    )
    await repo.save_export(session, job)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="export.requested",
        resource_type="export_job",
        resource_id=str(job.id),
        result=AuditResult.SUCCESS,
        details={"report": payload.report, "filters": _filter_dict(filters) or {}},
    )
    await publish_export_event(
        session,
        job_id=job.id,
        event_type=ExportEventType.REQUESTED,
        payload={"report": payload.report},
    )
    await session.flush()

    job.status = ExportStatus.PROCESSING.value
    await repo.save_export(session, job)
    await session.flush()

    try:
        rows = await repo.fetch_report_rows(session, payload.report, filters, _MAX_ROWS)
        mask_phone = ExportPolicy.mask_phone_numbers(user)
        content = build_csv(
            rows,
            headers=headers_for(payload.report),
            mask_phone=mask_phone,
        )

        from app.packages.storage.provider import get_storage_provider

        storage = get_storage_provider()
        key = f"exports/{job.id}.csv"
        await storage.put_bytes(key, content, content_type="text/csv")

        job.storage_key = key
        job.row_count = len(rows)
        job.status = ExportStatus.READY.value
        job.error = None
        result = AuditResult.SUCCESS
        outcome_event = ExportEventType.COMPLETED
        outcome_details: dict[str, Any] = {"rows": len(rows)}
    except Exception as exc:
        logger.exception("export failed", job_id=str(job.id), report=payload.report)
        job.status = ExportStatus.FAILED.value
        job.error = str(exc)[:512]
        result = AuditResult.FAILED
        outcome_event = ExportEventType.FAILED
        outcome_details = {"error": job.error}

    await repo.save_export(session, job)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="export.completed",
        resource_type="export_job",
        resource_id=str(job.id),
        result=result,
        details={"report": payload.report, **outcome_details},
    )
    await publish_export_event(
        session,
        job_id=job.id,
        event_type=outcome_event,
        payload={"report": payload.report, **outcome_details},
    )
    await session.commit()
    logger.info(
        "export created", job_id=str(job.id), report=payload.report, status=job.status
    )
    return DataResponse[ExportJobDTO](data=_to_dto(job))