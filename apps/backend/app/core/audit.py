"""Audit-trail writer (blueprint section 10 / Rule R7).

Defined centrally so every module appends to the same ``audit_log`` contract
that the workers' audit module owns.  Uses the shared read/write projection in
``packages.db.models.audit_log_table``; the physical table is created by that
module's migration.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import trace_id
from app.packages.contracts.enums import AuditResult
from app.packages.db.base import utc_now
from app.packages.db.models import audit_log_table


async def write_audit(
    session: AsyncSession,
    *,
    actor_id: Any,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    result: AuditResult | str,
    details: dict[str, Any] | None = None,
) -> None:
    """Insert one audit row in the caller's (logical) transaction.

    Audited actions - approve / reject / update / delete of user accounts - are
    committed together with their state change so a partial mutation can never
    leave an unrecorded operation behind.
    """
    await session.execute(
        audit_log_table.insert().values(
            id=uuid.uuid4(),
            ts=utc_now(),
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result.value if isinstance(result, AuditResult) else result,
            metadata=details,
            trace_id=trace_id() or uuid.uuid4().hex,
        )
    )