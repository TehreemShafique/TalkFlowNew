"""User-management event types + outbox writer (Rule R8)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import outbox_table


class UserManagementEventType(StrEnum):
    USER_APPROVED = "user.approved"
    USER_REJECTED = "user.rejected"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"


async def publish_user_event(
    session: AsyncSession,
    *,
    user_id,
    event_type: UserManagementEventType,
    metadata: dict | None = None,
) -> None:
    """Append a user-management event to the outbox (same tx as the change)."""
    await session.execute(
        outbox_table.insert().values(
            aggregate_type="user",
            aggregate_id=str(user_id),
            channel="auth",
            event_type=event_type.value,
            payload=metadata or {},
        )
    )
