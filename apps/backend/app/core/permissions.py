"""Role-to-permission matrix for the control plane (Rule R4).

Every module that gates an endpoint registers its permission strings here so
authentication (core.dependencies.require_permissions) and serialization
(users_rbac RolePublic) agree on one matrix.  Permissions are *derived* from a
user's role names - they are never stored in the DB.
"""

from __future__ import annotations

# User administration (users_rbac).
PERM_USER_VIEW = "user.view"
PERM_USER_APPROVE = "user.approve"
PERM_USER_EDIT = "user.edit"
PERM_USER_DELETE = "user.delete"

# Role management.
PERM_ROLE_VIEW = "role.view"

# Recordings (kept in sync with modules/recordings/policies.py).
PERM_RECORDING_VIEW = "recording.view"
PERM_RECORDING_PLAY = "recording.play"
PERM_RECORDING_DOWNLOAD = "recording.download"
PERM_RECORDING_PURGE = "recording.purge"
PERM_RECORDING_VIEW_ALL = "recording.view_all"

# Campaigns.
PERM_CAMPAIGN_VIEW = "campaign.view"
PERM_CAMPAIGN_START = "campaign.start"

# Calls.
PERM_CALL_VIEW = "call.view"
PERM_CALL_DISPOSITION = "call.disposition"

# PII.
PERM_PII_VIEW_FULL = "pii.view_full"

# QA / compliance audits (recordings.qa-audit).
PERM_QA_AUDIT = "qa.audit"

# Leads (modules/leads).
PERM_LEAD_VIEW = "lead.view"
PERM_LEAD_EDIT = "lead.edit"
PERM_LEAD_IMPORT = "lead.import"

# Suppression / DNC register (modules/suppression).
PERM_SUPPRESSION_VIEW = "suppression.view"
PERM_SUPPRESSION_ADD = "suppression.add"
PERM_SUPPRESSION_REMOVE = "suppression.remove"

# Export pipeline (modules/exports).
PERM_EXPORT_CREATE = "export.create"
PERM_EXPORT_VIEW = "export.view"
PERM_EXPORT_DOWNLOAD = "export.download"

# Scripts (modules/scripts).
PERM_SCRIPT_VIEW = "script.view"
PERM_SCRIPT_EDIT = "script.edit"
PERM_SCRIPT_APPROVE = "script.approve"

# Verifier workspace & transfers.
PERM_VERIFIER_WORKSPACE = "verifier.workspace"
PERM_TRANSFER_VIEW = "transfer.view"

# Analytics (modules/analytics; Reporting User lands here per TalkFlow.md §16).
PERM_ANALYTICS_VIEW = "analytics.view"
PERM_REPORTING_VIEW = PERM_ANALYTICS_VIEW

_ALL_PERMISSIONS: tuple[str, ...] = (
    PERM_USER_VIEW,
    PERM_USER_APPROVE,
    PERM_USER_EDIT,
    PERM_USER_DELETE,
    PERM_ROLE_VIEW,
    PERM_RECORDING_VIEW,
    PERM_RECORDING_PLAY,
    PERM_RECORDING_DOWNLOAD,
    PERM_RECORDING_PURGE,
    PERM_RECORDING_VIEW_ALL,
    PERM_CAMPAIGN_VIEW,
    PERM_CAMPAIGN_START,
    PERM_CALL_VIEW,
    PERM_CALL_DISPOSITION,
    PERM_PII_VIEW_FULL,
    PERM_QA_AUDIT,
    PERM_LEAD_VIEW,
    PERM_LEAD_EDIT,
    PERM_LEAD_IMPORT,
    PERM_SUPPRESSION_VIEW,
    PERM_SUPPRESSION_ADD,
    PERM_SUPPRESSION_REMOVE,
    PERM_EXPORT_CREATE,
    PERM_EXPORT_VIEW,
    PERM_EXPORT_DOWNLOAD,
    PERM_SCRIPT_VIEW,
    PERM_SCRIPT_EDIT,
    PERM_SCRIPT_APPROVE,
    PERM_VERIFIER_WORKSPACE,
    PERM_TRANSFER_VIEW,
    PERM_ANALYTICS_VIEW,
)

ADMIN_ROLE_NAMES: tuple[str, ...] = ("MASTER_ADMIN", "DEVOPS_IT")

# Roles that may be granted during public user approval (approval endpoint).
APPROVABLE_ROLE_NAMES: tuple[str, ...] = (
    "DEVOPS_IT",
    "CAMPAIGN_MANAGER",
    "QA",
    "VERIFIER",
    "VIEWER",
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "MASTER_ADMIN": _ALL_PERMISSIONS,
    "DEVOPS_IT": (
        PERM_USER_VIEW,
        PERM_USER_APPROVE,
        PERM_USER_EDIT,
        PERM_USER_DELETE,
        PERM_ROLE_VIEW,
        PERM_RECORDING_VIEW,
        PERM_RECORDING_VIEW_ALL,
        PERM_RECORDING_PLAY,
        PERM_RECORDING_DOWNLOAD,
        PERM_RECORDING_PURGE,
        PERM_CAMPAIGN_VIEW,
        PERM_CAMPAIGN_START,
        PERM_CALL_VIEW,
        PERM_CALL_DISPOSITION,
        PERM_PII_VIEW_FULL,
        PERM_QA_AUDIT,
        PERM_LEAD_VIEW,
        PERM_LEAD_EDIT,
        PERM_LEAD_IMPORT,
        PERM_SUPPRESSION_VIEW,
        PERM_SUPPRESSION_ADD,
        PERM_SUPPRESSION_REMOVE,
        PERM_EXPORT_CREATE,
        PERM_EXPORT_VIEW,
        PERM_EXPORT_DOWNLOAD,
        PERM_SCRIPT_VIEW,
        PERM_SCRIPT_EDIT,
        PERM_SCRIPT_APPROVE,
        PERM_VERIFIER_WORKSPACE,
        PERM_TRANSFER_VIEW,
        PERM_ANALYTICS_VIEW,
    ),
    "CAMPAIGN_MANAGER": (
        PERM_RECORDING_VIEW,
        PERM_RECORDING_PLAY,
        PERM_RECORDING_DOWNLOAD,
        PERM_CAMPAIGN_VIEW,
        PERM_CAMPAIGN_START,
        PERM_CALL_VIEW,
        PERM_CALL_DISPOSITION,
        PERM_LEAD_VIEW,
        PERM_LEAD_EDIT,
        PERM_LEAD_IMPORT,
        PERM_SUPPRESSION_VIEW,
        PERM_SUPPRESSION_ADD,
        PERM_EXPORT_CREATE,
        PERM_EXPORT_VIEW,
        PERM_EXPORT_DOWNLOAD,
        PERM_SCRIPT_VIEW,
        PERM_SCRIPT_EDIT,
        PERM_SCRIPT_APPROVE,
        PERM_TRANSFER_VIEW,
        PERM_ANALYTICS_VIEW,
    ),
    "VERIFIER": (
        PERM_VERIFIER_WORKSPACE,
        PERM_CALL_VIEW,
        PERM_CALL_DISPOSITION,
        PERM_RECORDING_VIEW,
        PERM_RECORDING_PLAY,
    ),
    "QA": (
        PERM_RECORDING_VIEW,
        PERM_RECORDING_PLAY,
        PERM_RECORDING_DOWNLOAD,
        PERM_QA_AUDIT,
        PERM_CAMPAIGN_VIEW,
        PERM_CALL_VIEW,
        PERM_SUPPRESSION_VIEW,
        PERM_SCRIPT_VIEW,
        PERM_ANALYTICS_VIEW,
    ),
    "VIEWER": (
        PERM_RECORDING_VIEW,
        PERM_RECORDING_PLAY,
        PERM_CAMPAIGN_VIEW,
        PERM_CALL_VIEW,
        PERM_SCRIPT_VIEW,
    ),
    "REPORTING_USER": (
        PERM_RECORDING_VIEW,
        PERM_CAMPAIGN_VIEW,
        PERM_CALL_VIEW,
        PERM_EXPORT_CREATE,
        PERM_EXPORT_VIEW,
        PERM_EXPORT_DOWNLOAD,
        PERM_SCRIPT_VIEW,
        PERM_ANALYTICS_VIEW,
    ),
}


def permissions_for_roles(role_names: list[str] | None) -> set[str]:
    """Union of permissions granted by the given role names."""
    if not role_names:
        return set()
    perms: set[str] = set()
    for name in role_names:
        perms.update(ROLE_PERMISSIONS.get(name, ()))
    return perms
