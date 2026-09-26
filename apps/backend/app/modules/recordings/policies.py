"""Authorization policies for recording actions.

Rule R4 - an explicit permission gate lives next to the data it guards, so the
route declaration reads as a flat checklist.  When the requested action needs
*auditable* authorization, pass the trace element into the audit writer
(service.audit) rather than logging a soft event here.
"""

from __future__ import annotations

from app.core.context import UserContext
from app.core.permissions import (
    has_permission,
    sees_full_phi,
)
from app.core.security import mask_phone

# ---------------------------------------------------------------------------
# Permission strings (single source of truth for the wire/role matrix).
# ---------------------------------------------------------------------------
PERM_RECORDING_VIEW = "recording.view"
PERM_RECORDING_PLAY = "recording.play"
PERM_RECORDING_DOWNLOAD = "recording.download"
PERM_RECORDING_PURGE = "recording.purge"
PERM_VIEW_ALL = "recording.view_all"
PERM_RECORDING_VIEW_ALL = PERM_VIEW_ALL
PERM_QA_AUDIT = "qa.audit"
PERM_PII_VIEW_FULL = "pii.view_full"

# RP-27: RBAC gates for audio.  The legacy singular spellings stay accepted as
# aliases (see app.core.permissions.LEGACY_PERMISSION_ALIASES).
PERM_RECORDING_READ = "recordings:read"
PERM_RECORDING_DOWNLOAD_FILE = "recordings:download"


class RecordingPolicy:
    @staticmethod
    def can_list(user: UserContext) -> bool:
        return has_permission(user.permissions, PERM_RECORDING_READ)

    @staticmethod
    def can_play(user: UserContext) -> bool:
        return has_permission(user.permissions, PERM_RECORDING_READ)

    @staticmethod
    def can_download(user: UserContext) -> bool:
        return has_permission(user.permissions, PERM_RECORDING_DOWNLOAD_FILE)

    @staticmethod
    def can_purge(user: UserContext) -> bool:
        return has_permission(user.permissions, PERM_RECORDING_PURGE)

    @staticmethod
    def sees_full_pii(user: UserContext) -> bool:
        return sees_full_phi(user.role, user.permissions)

    @staticmethod
    def scope_unlimited(user: UserContext) -> bool:
        """True when the principal may see recordings of any campaign/tenant."""
        return (
            has_permission(user.permissions, PERM_VIEW_ALL)
            or user.role == "MASTER_ADMIN"
        )

    @staticmethod
    def masked_phone(phone: str, user: UserContext) -> str | None:
        if not phone:
            return None
        return phone if RecordingPolicy.sees_full_pii(user) else mask_phone(phone)


def resolve_scope_constraints(user: UserContext) -> dict:
    """Return the explicit scope filter to enforce (Rule R5).

    * Unrestricted principals get no narrowing (full dataset).
    * Everyone else is filtered by their assigned tenant (all rows share the
      tenant id) so cross-tenant reads are structurally impossible here.
    """
    constraints: dict[str, object] = {}
    if not RecordingPolicy.scope_unlimited(user) and user.scope.tenant_id:
        constraints["tenant_id"] = user.scope.tenant_id
    return constraints


class CannedQualificationPolicy:
    """Single documented qualification decision for the recordings module."""

    PASS = "PASSED"
    FAIL = "FAILED"

    @staticmethod
    def resolve(qual_status: str | None, details: str | None) -> str | None:
        if qual_status:
            return qual_status
        if details and "disqualified" in details.lower():
            return CannedQualificationPolicy.FAIL
        return CannedQualificationPolicy.PASS if not details else None
