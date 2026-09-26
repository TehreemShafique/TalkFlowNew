"""Shared database package: base classes, models and table projections."""

from app.packages.db.base import Base, utc_now, uuid7
from app.packages.db.models import (
    CallRecording,
    Role,
    User,
    UserSession,
    audit_log_table,
    calls_table,
    campaigns_table,
    leads_table,
    merge_shared_metadata,
    outbox_table,
    qa_reviews_table,
    retention_policies_table,
    user_roles,
)

__all__ = [
    "Base",
    "CallRecording",
    "Role",
    "User",
    "UserSession",
    "audit_log_table",
    "calls_table",
    "campaigns_table",
    "leads_table",
    "merge_shared_metadata",
    "outbox_table",
    "qa_reviews_table",
    "retention_policies_table",
    "user_roles",
    "utc_now",
    "uuid7",
]
