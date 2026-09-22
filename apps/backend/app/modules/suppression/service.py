"""Suppression service - add / bulk-import / check / remove (soft delete).

Every mutation is one transaction that also: reflects the change onto the
``leads`` master registry through the shared projection, appends its audit row,
and enqueues the ``talkflow.vicidial.sync.v1`` outbox event so dialers drop the
number (Rule R8 - nothing is published fire-and-forget).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.core.security import mask_phone
from app.modules.suppression import repository as repo
from app.modules.suppression.errors import (
    SuppressionDuplicateError,
    SuppressionFileTooLargeError,
    SuppressionImportEmptyError,
    SuppressionInvalidPhoneError,
    SuppressionMissingPhoneColumnError,
    SuppressionNotFoundError,
)
from app.modules.suppression.events import (
    SuppressionEventType,
    publish_suppression_event,
)
from app.modules.suppression.policies import (
    SuppressionPolicy,
    parse_expires_at,
    parse_reason,
    resolve_header_map,
)
from app.modules.suppression.schemas import (
    MAX_UPLOAD_BYTES,
    SuppressionCheckDTO,
    SuppressionEntryCreate,
    SuppressionEntryDTO,
    SuppressionImportResult,
    SuppressionListQuery,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, SuppressionReason
from app.packages.db.base import uuid7
from app.packages.db.models import SuppressionEntry

logger = structlog.get_logger("suppression.service")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _to_dto(entry: SuppressionEntry, *, mask: bool) -> SuppressionEntryDTO:
    return SuppressionEntryDTO(
        id=entry.id,
        phone=mask_phone(entry.phone_normalized) if mask else entry.phone_normalized,
        reason=SuppressionReason(entry.reason),
        source=entry.source,
        added_by=entry.added_by,
        added_at=entry.added_at,
        expires_at=entry.expires_at,
        evidence_reference=entry.evidence_reference,
        removed_at=entry.removed_at,
        removed_by=entry.removed_by,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def _load_entry(
    session: AsyncSession, user: UserContext, entry_id: uuid.UUID
) -> SuppressionEntry:
    entry = await repo.get_entry(session, entry_id, {})
    if entry is None:
        raise SuppressionNotFoundError()
    if entry.removed_at is not None:
        raise SuppressionNotFoundError()
    return entry


def _parse_csv_rows(
    data: bytes,
) -> tuple[list[dict[str, Any]], int, list[tuple[int, str]]]:
    """Return (valid_rows, invalid_count, errors_by_file_line).

    Raises when the file is empty or has no phone-bearing header.
    """
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise SuppressionImportEmptyError(details={"reason": "csv_empty"})

    field_map = resolve_header_map(list(reader.fieldnames))
    phone_column = field_map.get("phone")
    if phone_column is None:
        raise SuppressionMissingPhoneColumnError()

    valid: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    invalid = 0
    errors: list[tuple[int, str]] = []
    for file_line, row in enumerate(reader, start=2):
        from app.packages.phone import normalize_us_phone

        phone = normalize_us_phone(str((row.get(phone_column) or "").strip()))
        if phone is None:
            invalid += 1
            errors.append((file_line, "invalid_phone"))
            continue
        if phone in seen:
            invalid += 1
            errors.append((file_line, "duplicate_in_file"))
            continue
        seen[phone] = file_line

        reason, reason_error = parse_reason(row.get(field_map.get("reason", "")))
        if reason_error is not None:
            invalid += 1
            errors.append((file_line, reason_error))
            continue

        valid.append(
            {
                "phone": phone,
                "reason": reason,
                "source": (row.get(field_map.get("source", "")) or "").strip() or None,
                "expires_at": parse_expires_at(
                    row.get(field_map.get("expires_at", ""))
                ),
                "evidence_reference": (
                    (row.get(field_map.get("evidence_reference", "")) or "").strip()
                    or None
                ),
            }
        )
    return valid, invalid, errors


def _error_report_bytes(errors: list[tuple[int, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row", "reason"])
    writer.writerows(errors)
    return buffer.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
async def list_entries(
    session: AsyncSession, user: UserContext, query: SuppressionListQuery
) -> PagedResponse[SuppressionEntryDTO]:
    rows, total = await repo.list_entries(session, query, {})
    mask = not SuppressionPolicy.can_see_full_phone(user)
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[SuppressionEntryDTO](
        data=[_to_dto(row, mask=mask) for row in rows],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            sort=query.sort,
            order=query.order,
        ),
    )


async def check_phone(
    session: AsyncSession, user: UserContext, phone: str
) -> DataResponse[SuppressionCheckDTO]:
    """Pre-dial lookup: is this number blocked, and why (spec 19.4 acceptance)."""
    from app.core.redis import get_redis
    from app.packages.phone import normalize_us_phone

    normalized = normalize_us_phone(phone)
    if normalized is None:
        raise SuppressionInvalidPhoneError(details={"phone": mask_phone(phone)})

    cache_key = f"cp:suppression:{normalized}"
    try:
        redis_client = get_redis()
        cached = await redis_client.get(cache_key)
        if cached:
            cached_text = cached.decode() if isinstance(cached, bytes) else cached
            if cached_text == "clear":
                return DataResponse[SuppressionCheckDTO](
                    data=SuppressionCheckDTO(suppressed=False)
                )
            parts = cached_text.split(":", 2)
            if len(parts) >= 3 and parts[0] == "suppressed":
                return DataResponse[SuppressionCheckDTO](
                    data=SuppressionCheckDTO(
                        suppressed=True,
                        reason=SuppressionReason(parts[1]),
                        entry_id=uuid.UUID(parts[2]),
                    )
                )
    except Exception:  # noqa: BLE001, S110 - cache is best-effort
        pass

    entry = await repo.get_active_entry_by_phone(session, normalized)
    if entry is None:
        try:
            redis_client = get_redis()
            await redis_client.setex(cache_key, 300, "clear")
        except Exception:  # noqa: BLE001, S110 - cache is best-effort
            pass
        return DataResponse[SuppressionCheckDTO](
            data=SuppressionCheckDTO(suppressed=False)
        )

    try:
        redis_client = get_redis()
        await redis_client.setex(
            cache_key, 300, f"suppressed:{entry.reason}:{entry.id}"
        )
    except Exception:  # noqa: BLE001, S110 - cache is best-effort
        pass

    return DataResponse[SuppressionCheckDTO](
        data=SuppressionCheckDTO(
            suppressed=True,
            reason=SuppressionReason(entry.reason),
            entry_id=entry.id,
            expires_at=entry.expires_at,
        )
    )


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
async def add_entry(
    session: AsyncSession, user: UserContext, payload: SuppressionEntryCreate
) -> DataResponse[SuppressionEntryDTO]:
    from app.core.redis import get_redis
    from app.packages.phone import normalize_us_phone

    phone = normalize_us_phone(payload.phone)
    if phone is None:
        raise SuppressionInvalidPhoneError(details={"phone": mask_phone(payload.phone)})

    existing = await repo.get_active_entry_by_phone(session, phone)
    if existing is not None:
        raise SuppressionDuplicateError(phone)

    entry = SuppressionEntry(
        id=uuid7(),
        phone_normalized=phone,
        reason=payload.reason.value,
        source=payload.source,
        added_by=user.user_id,
        expires_at=payload.expires_at,
        evidence_reference=payload.evidence_reference,
    )
    await repo.save_entry(session, entry)
    await repo.mark_leads_suppressed(session, [phone], payload.reason.value)

    try:
        redis_client = get_redis()
        await redis_client.setex(
            f"cp:suppression:{phone}",
            300,
            f"suppressed:{payload.reason.value}:{entry.id}",
        )
    except Exception:  # noqa: BLE001, S110 - cache is best-effort
        pass

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="suppression.add",
        resource_type="suppression_entry",
        resource_id=str(entry.id),
        result=AuditResult.SUCCESS,
        details={"phone": mask_phone(phone), "reason": payload.reason.value},
    )
    await publish_suppression_event(
        session,
        entry_id=entry.id,
        event_type=SuppressionEventType.ADDED,
        payload={"phone": phone, "reason": payload.reason.value},
    )
    await session.commit()
    logger.info("suppression added", entry_id=str(entry.id), actor=str(user.user_id))
    return DataResponse[SuppressionEntryDTO](data=_to_dto(entry, mask=False))


async def remove_entry(
    session: AsyncSession, user: UserContext, entry_id: uuid.UUID
) -> DataResponse[SuppressionEntryDTO]:
    """Soft-delete an ACTIVE entry (removal is Master Admin only - R4 gate)."""
    from app.core.redis import get_redis

    entry = await _load_entry(session, user, entry_id)
    now = datetime.now(UTC)
    await repo.touch_entry(session, entry, removed_at=now, removed_by=user.user_id)
    await repo.clear_leads_suppressed(session, [entry.phone_normalized])

    try:
        redis_client = get_redis()
        await redis_client.delete(f"cp:suppression:{entry.phone_normalized}")
    except Exception:  # noqa: BLE001, S110 - cache is best-effort
        pass

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="suppression.remove",
        resource_type="suppression_entry",
        resource_id=str(entry.id),
        result=AuditResult.SUCCESS,
        details={"phone": mask_phone(entry.phone_normalized)},
    )
    await publish_suppression_event(
        session,
        entry_id=entry.id,
        event_type=SuppressionEventType.REMOVED,
        payload={"phone": entry.phone_normalized},
    )
    await session.commit()
    logger.info("suppression removed", entry_id=str(entry.id), actor=str(user.user_id))
    return DataResponse[SuppressionEntryDTO](data=_to_dto(entry, mask=False))


async def import_csv(
    session: AsyncSession, user: UserContext, file: UploadFile
) -> DataResponse[SuppressionImportResult]:
    """Bulk DNC load: one row per number, conflicts skipped, leads flagged.

    Returns the added / duplicate / invalid tallies; duplicates against the
    register are skipped rather than updated, so re-importing a batch is safe.
    """
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise SuppressionFileTooLargeError(details={"max_bytes": MAX_UPLOAD_BYTES})

    valid, invalid, errors = _parse_csv_rows(payload)
    total = len(valid) + invalid
    if not valid and not invalid:
        raise SuppressionImportEmptyError(details={"reason": "csv_empty"})

    values: list[dict[str, Any]] = [
        {
            "id": uuid7(),
            "phone_normalized": row["phone"],
            "reason": row["reason"],
            "source": row["source"],
            "expires_at": row["expires_at"],
            "evidence_reference": row["evidence_reference"],
            "added_by": user.user_id,
        }
        for row in valid
    ]
    added = await repo.bulk_add_entries(session, values)
    duplicate = len(valid) - added
    duplicate = max(duplicate, 0)

    if valid:
        reasons = {row["reason"] for row in valid}
        primary_reason = (
            reasons.pop() if reasons else SuppressionReason.INTERNAL_DNC.value
        )
        await repo.mark_leads_suppressed(
            session, [row["phone"] for row in valid], primary_reason
        )

    if errors:
        from app.packages.storage.provider import get_storage_provider

        storage = get_storage_provider()
        key = f"imports/suppression_{job_suffix()}_errors.csv"
        await storage.put_bytes(
            key, _error_report_bytes(errors), content_type="text/csv"
        )

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="suppression.import",
        resource_type="suppression_entries",
        resource_id=str(uuid.uuid4()),
        result=AuditResult.SUCCESS,
        details={
            "total": total,
            "added": added,
            "duplicate": duplicate,
            "invalid": invalid,
        },
    )
    await publish_suppression_event(
        session,
        entry_id=str(uuid.uuid4()),
        event_type=SuppressionEventType.IMPORTED,
        payload={"total": total, "added": added},
    )
    await session.commit()
    logger.info("suppression import", added=added, duplicate=duplicate, invalid=invalid)
    return DataResponse[SuppressionImportResult](
        data=SuppressionImportResult(
            total=total, added=added, duplicate=duplicate, invalid=invalid
        )
    )


def job_suffix() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
