"""Auth event types + outbox writer (Rule R8 - event in the same transaction)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import outbox_table


class AuthEventType(StrEnum):
    SESSION_CREATED = "auth.session.created"
    SESSION_REVOKED = "auth.session.revoked"
    SIGNUP_REQUESTED = "auth.signup.requested"


async def publish_auth_event(
    session: AsyncSession,
    *,
    user_id,
    event_type: AuthEventType,
    metadata: dict | None = None,
) -> None:
    """Append an auth event to the outbox within the caller's transaction."""
    await session.execute(
        outbox_table.insert().values(
            aggregate_type="user",
            aggregate_id=str(user_id),
            channel="auth",
            event_type=event_type.value,
            payload=metadata or {},
        )
    )
