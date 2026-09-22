"""Suppression authorization + CSV parsing policies (ADR-03: zero I/O).

Header resolution and row normalization are pure functions so the DNC import
adapter is testable without a database.  ``add`` requires ``suppression.add``
(CAMPAIGN_MANAGER and up); ``remove`` requires ``suppression.remove`` which
only the ADMIN roles hold (spec: removal is MASTER ADMIN only).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

from app.core.context import UserContext
from app.core.permissions import (
    PERM_LEAD_VIEW,
    PERM_PII_VIEW_FULL,
    PERM_SUPPRESSION_ADD,
    PERM_SUPPRESSION_REMOVE,
    PERM_SUPPRESSION_VIEW,
)
from app.packages.contracts.enums import SuppressionReason
from app.packages.phone import normalize_us_phone

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _key(header: str) -> str:
    """Canonicalize a CSV header to an alias key (letters/digits only)."""
    return "".join(char for char in header.lower() if char.isalnum())


_PHONE_ALIASES = {"phone", "phonenumber", "number", "phonenum", "dial", "callnumber"}
_REASON_ALIASES = {"reason", "dncreason", "reasoncode", "dncreasoncode"}
_SOURCE_ALIASES = {"source", "sourceid"}
_EXPIRES_ALIASES = {
    "expiresat",
    "expiration",
    "expirationdate",
    "validuntil",
    "validthrough",
}
_EVIDENCE_ALIASES = {"evidence", "evidencereference", "reference"}


def resolve_header_map(fieldnames: list[str]) -> dict[str, str]:
    """Map target field -> matching CSV column name (only present headers)."""
    resolved: dict[str, str] = {}
    for fieldname in fieldnames:
        key = _key(fieldname)
        if key in _REASON_ALIASES:
            resolved["reason"] = fieldname
        elif key in _PHONE_ALIASES:
            resolved["phone"] = fieldname
        elif key in _SOURCE_ALIASES:
            resolved["source"] = fieldname
        elif key in _EXPIRES_ALIASES:
            resolved["expires_at"] = fieldname
        elif key in _EVIDENCE_ALIASES:
            resolved["evidence_reference"] = fieldname
    return resolved


def parse_reason(value: str | None) -> tuple[str | None, str | None]:
    """Return (reason_value_or_None, error_or_None); blank defaults to internal."""
    candidate = (value or "").strip().lower()
    if not candidate:
        return SuppressionReason.INTERNAL_DNC.value, None
    if candidate in SuppressionReason._value2member_map_:
        return candidate, None
    normalized = candidate.replace("_", "-")
    if normalized in SuppressionReason._value2member_map_:
        return normalized, None
    return None, "invalid_reason"


def parse_expires_at(value: str | None) -> datetime | None:
    """ISO date or datetime -> tz-aware UTC datetime; None when blank/invalid."""
    if not value:
        return None
    candidate = value.strip()
    try:
        if _ISO_DATE_RE.match(candidate):
            return datetime.combine(
                date.fromisoformat(candidate), datetime.min.time(), tzinfo=UTC
            )
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


class SuppressionPolicy:
    """Permission helpers for the suppression module (Rule R4)."""

    @staticmethod
    def can_view(user: UserContext) -> bool:
        return PERM_SUPPRESSION_VIEW in user.permissions

    @staticmethod
    def can_add(user: UserContext) -> bool:
        return PERM_SUPPRESSION_ADD in user.permissions

    @staticmethod
    def can_remove(user: UserContext) -> bool:
        return PERM_SUPPRESSION_REMOVE in user.permissions

    @staticmethod
    def can_see_full_phone(user: UserContext) -> bool:
        return (
            PERM_PII_VIEW_FULL in user.permissions or PERM_LEAD_VIEW in user.permissions
        )


def resolve_scope_constraints(user: UserContext) -> dict:
    """Explicit scope filter hook (Rule R5) - the register is global today."""
    _ = user
    return {}


def normalize_entry_phone(raw: str) -> str | None:
    return normalize_us_phone(raw)
