"""Export policies (ADR-03: zero I/O).

Maps report types to their column schema and builds the CSV representation; the
caller decides whether phone numbers are masked (via the pure helper below)
before invoking it.  No SQL, no session, no storage.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.core.context import UserContext
from app.core.permissions import (
    PERM_EXPORT_CREATE,
    PERM_EXPORT_DOWNLOAD,
    PERM_EXPORT_VIEW,
    PERM_LEAD_VIEW,
    PERM_PII_VIEW_FULL,
)

# Report types the export pipeline can render today (spec 28.8).  The scripts /
# bot / compliance / performance reports land with their owning tables.
SUPPORTED_REPORTS: frozenset[str] = frozenset({"leads", "campaigns", "calls"})

REPORT_HEADERS: dict[str, list[str]] = {
    "leads": [
        "id",
        "first_name",
        "last_name",
        "phone",
        "alt_phone",
        "email",
        "state",
        "zip_code",
        "date_of_birth",
        "age",
        "source",
        "source_batch_id",
        "campaign_id",
        "status",
        "attempts",
        "last_attempt_at",
        "next_attempt_at",
        "assigned_to",
        "suppressed",
        "suppression_reason",
        "created_at",
        "updated_at",
    ],
    "campaigns": ["id", "name", "status", "created_at", "updated_at"],
    "calls": [
        "id",
        "started_at",
        "duration_seconds",
        "disposition",
        "qualification_status",
        "disqualification_reason",
        "lead_id",
        "campaign_id",
        "verifier_id",
    ],
}


def is_supported_report(report: str) -> bool:
    return report in SUPPORTED_REPORTS


def headers_for(report: str) -> list[str]:
    return list(REPORT_HEADERS.get(report, []))


class ExportPolicy:
    """Permission helpers for the export pipeline (Rule R4)."""

    @staticmethod
    def can_create(user: UserContext) -> bool:
        return PERM_EXPORT_CREATE in user.permissions

    @staticmethod
    def can_view(user: UserContext) -> bool:
        return PERM_EXPORT_VIEW in user.permissions

    @staticmethod
    def can_download(user: UserContext) -> bool:
        return PERM_EXPORT_DOWNLOAD in user.permissions

    @staticmethod
    def mask_phone_numbers(user: UserContext) -> bool:
        """True when the caller must see masked numbers in report output.

        Only tenants holding ``pii.view_full`` or ``lead.view`` get full phone
        numbers in export files; everyone else (e.g. REPORTING_USER) receives
        a masked column.
        """
        return not (
            PERM_PII_VIEW_FULL in user.permissions or PERM_LEAD_VIEW in user.permissions
        )


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_csv(
    rows: list[dict[str, Any]],
    *,
    headers: list[str],
    mask_phone: bool,
) -> bytes:
    """Serialize the row dicts into CSV bytes (RFC 4180 line endings).

    Ordering follows ``headers``; only the ``phone`` column is subject to
    masking for non-PII tenants.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        if mask_phone and "phone" in headers and row.get("phone"):
            row = {**row, "phone": masked_phone(str(row["phone"]))}
        writer.writerow({header: _cell(row.get(header)) for header in headers})
    return buffer.getvalue().encode("utf-8")


def masked_phone(phone: str) -> str:
    """Mask a phone keeping the area code + last four (mirrors core mask)."""
    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) < 10:
        return "(XXX) ***-XXXX"
    return f"({digits[-10:-7]}) ***-{digits[-4:]}"


def resolve_scope_constraints(user: UserContext) -> dict:
    _ = user
    return {}