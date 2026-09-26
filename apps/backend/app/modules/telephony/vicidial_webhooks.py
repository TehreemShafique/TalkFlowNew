"""VICIdial authenticated webhook endpoints (BACKEND-8a).

- ``POST /api/v1/telephony/vicidial/start-call``
- ``POST /api/v1/telephony/vicidial/dispo-call``

Authentication is B2-A header-token (not the RBAC JWT): VICIdial signs every
webhook with ``X-TalkFlow-Telephony-Token`` equal to ``telephony_webhook_token``.
Requests without a matching token get HTTP 401 before any idempotency work.

Idempotency (replay protection) is implemented per-handler in ``service`` via
``app.core.idempotency`` - the Redis key ``idempotency:vicidial_webhook:{lead_id}:{call_id}``
is acquired atomically, and every replayed request returns ``ignored_duplicate``
without touching the database.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.telephony import service
from app.modules.telephony.errors import TelephonyUnauthorizedError
from app.modules.telephony.schemas import (
    DispoCallPayload,
    StartCallPayload,
    WebhookResult,
)

router = APIRouter(prefix="/telephony/vicidial", tags=["telephony"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_idempotency_client() -> Any:
    """Shared Redis client used by the idempotency guard.

    Exposed as a named dependency so tests can override just this client with
    an in-memory double while keeping the rest of the app intact.
    """
    return get_redis()


IdempotencyClient = Annotated[Any, Depends(get_idempotency_client)]


async def require_telephony_token(request: Request) -> None:
    """B2-A header-token gate: 401 on missing/mismatched webhook token."""
    token = request.headers.get("X-TalkFlow-Telephony-Token")
    if not token or token != settings.telephony_webhook_token:
        raise TelephonyUnauthorizedError(
            "telephony.unauthorized",
            message="Missing or invalid telephony webhook token.",
        )


@router.post(
    "/start-call",
    response_model=WebhookResult,
    dependencies=[Depends(require_telephony_token)],
)
async def start_call(
    payload: StartCallPayload,
    db: DbSession,
    idempotency_client: IdempotencyClient,
) -> WebhookResult:
    """Register a dialer-side call open (idempotent on lead+call id)."""
    return await service.process_start_call(db, payload, idempotency_client)


@router.post(
    "/dispo-call",
    response_model=WebhookResult,
    dependencies=[Depends(require_telephony_token)],
)
async def dispo_call(
    payload: DispoCallPayload,
    db: DbSession,
    idempotency_client: IdempotencyClient,
) -> WebhookResult:
    """Stamp a dialer-side disposition (idempotent on lead+call id)."""
    return await service.process_dispo_call(db, payload, idempotency_client)
