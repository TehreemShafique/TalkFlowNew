"""Lead authorization + CSV import classification policies (ADR-03: zero I/O).

Everything here is pure: normalizing a row, mapping source columns onto
TalkFlow fields, and classifying a phone against precomputed sets (suppression
register, existing leads, this file's own duplicates).  The service fetches
those sets once and hands them in, so the hottest logic - deciding whether a
row imports, is skipped, or is suppressed - is unit-testable with no DB.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.context import UserContext
from app.core.permissions import (
    PERM_LEAD_EDIT,
    PERM_LEAD_IMPORT,
    PERM_LEAD_VIEW,
    PERM_PII_VIEW_FULL,
)
from app.packages.phone import normalize_us_phone

# Target fields a CSV column may map onto.  Anything else is treated as a
# custom field and stored inside ``custom_fields`` (free-form, no schema).
SYSTEM_FIELDS: frozenset[str] = frozenset(
    {
        "phone",
        "first_name",
        "last_name",
        "alt_phone",
        "email",
        "state",
        "zip_code",
        "date_of_birth",
        "source",
        "source_batch_id",
    }
)

# Required target fields for a mapping to be committable (section 14 LEADS).
REQUIRED_FIELDS: tuple[str, ...] = ("phone",)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LEAD_STATUS_TRANSITIONS: set[tuple[str, str]] = {
    ("new", "assigned"),
    ("new", "queued"),
    ("new", "suppressed"),
    ("assigned", "queued"),
    ("assigned", "in_call"),
    ("queued", "in_call"),
    ("queued", "suppressed"),
    ("in_call", "completed"),
    ("in_call", "disqualified"),
    ("in_call", "queued"),
    ("in_call", "suppressed"),
    ("completed", "queued"),
    ("disqualified", "new"),
    ("suppressed", "new"),
}


def generate_external_key() -> str:
    """Generate a <=20 char base32 external_key from 12 random bytes (Step 27)."""
    raw = os.urandom(12)
    key = base64.b32encode(raw).decode("ascii").rstrip("=").lower()
    return key[:20]


def can_transition_lead_status(frm: str, to: str) -> bool:
    if frm == to:
        return True
    return (frm, to) in LEAD_STATUS_TRANSITIONS


@dataclass(frozen=True, slots=True)
class PreparedRow:
    """One source row mapped + normalized, ready to classify/insert."""

    system: dict[str, Any]
    custom: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RowVerdict:
    """Pure classification of a prepared row."""

    kind: str  # "valid" | "invalid" | "duplicate" | "suppressed"
    reason: str | None = None


def missing_required_fields(mapping: dict[str, str]) -> list[str]:
    targets = set(mapping.values())
    return [field for field in REQUIRED_FIELDS if field not in targets]


def apply_mapping(
    row: dict[str, str], mapping: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a raw CSV row into (system fields, custom fields).

    Unmapped source columns and blank values are dropped; only mapped targets
    survive, so a mapping change never carries stale columns forward.
    """
    system: dict[str, Any] = {}
    custom: dict[str, Any] = {}
    for source_col, target_field in mapping.items():
        value = (row.get(source_col) or "").strip()
        if not value:
            continue
        if target_field in SYSTEM_FIELDS:
            system[target_field] = value
        else:
            custom[target_field] = value
    return system, custom


def parse_date_of_birth(value: str | None) -> tuple[date | None, str | None]:
    """Return (parsed_date_or_None, error_reason_or_None)."""
    if not value:
        return None, None
    candidate = value.strip()
    if not _ISO_DATE.match(candidate):
        return None, "invalid_date_of_birth"
    try:
        return date.fromisoformat(candidate), None
    except ValueError:
        return None, "invalid_date_of_birth"


def prepare_row(
    row: dict[str, str], mapping: dict[str, str]
) -> tuple[PreparedRow | None, str | None]:
    """Normalize one mapped row; ``(None, reason)`` when it cannot import.

    Enforces the only mandatory column (phone) in E.164 form and rejects rows
    whose optional date-of-birth is malformed before they reach commitment.
    """
    system, custom = apply_mapping(row, mapping)
    phone = normalize_us_phone(str(system.get("phone") or ""))
    if phone is None:
        return None, "invalid_phone"
    system["phone"] = phone
    dob, dob_reason = parse_date_of_birth(str(system.get("date_of_birth") or ""))
    if dob_reason is not None:
        return None, dob_reason
    if dob is not None:
        system["date_of_birth"] = dob
    return PreparedRow(system=system, custom=custom), None


def classify_row(
    phone: str,
    *,
    seen_in_file: set[str],
    existing_phones: set[str],
    suppressed_phones: set[str],
) -> RowVerdict:
    """Pure verdict for one already-normalized phone (assumes valid phone)."""
    if phone in suppressed_phones:
        return RowVerdict("suppressed", "suppressed_dnc")
    if phone in seen_in_file:
        return RowVerdict("duplicate", "duplicate_in_file")
    if phone in existing_phones:
        return RowVerdict("duplicate", "duplicate_in_system")
    return RowVerdict("valid", None)


class LeadPolicy:
    """Permission helpers for the leads module (Rule R4)."""

    @staticmethod
    def can_view(user: UserContext) -> bool:
        return PERM_LEAD_VIEW in user.permissions

    @staticmethod
    def can_edit(user: UserContext) -> bool:
        return PERM_LEAD_EDIT in user.permissions

    @staticmethod
    def can_import(user: UserContext) -> bool:
        return PERM_LEAD_IMPORT in user.permissions

    @staticmethod
    def can_see_full_phone(user: UserContext) -> bool:
        """Leads are the control plane's PII surface; viewing them grants it.

        Consumers that only read aggregates (e.g. exports) must mask the phone
        unless they hold ``pii.view_full``.
        """
        return (
            PERM_PII_VIEW_FULL in user.permissions or PERM_LEAD_VIEW in user.permissions
        )


def resolve_scope_constraints(user: UserContext) -> dict:
    """Explicit scope filter hook (Rule R5) - leads are global today.

    Campaign-scoped viewership arrives with field-level access; the hook keeps
    every repository call already threading a constraint dict.
    """
    _ = user
    return {}
