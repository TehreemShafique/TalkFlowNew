"""Transfers service logic - offer reservation, watchdog & lifecycle (Step 34)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.core.outbox import write_outbox
from app.core.redis import get_redis
from app.modules.transfers import repository as repo
from app.modules.transfers.errors import (
    TransferNotFoundError,
)
from app.modules.transfers.schemas import (
    TransferCallbackRequest,
    TransferDTO,
    TransferListQuery,
    TransferRetryRequest,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, TransferStatus
from app.packages.db.models import Transfer

logger = structlog.get_logger("transfers.service")


def _to_dto(t: Transfer) -> TransferDTO:
    return TransferDTO(
        id=t.id,
        call_id=t.call_id,
        lead_id=t.lead_id,
        campaign_id=t.campaign_id,
        from_agent_id=t.from_agent_id,
        verifier_id=t.verifier_id,
        verifier_group_id=t.verifier_group_id,
        status=TransferStatus(t.status),
        ring_timeout_seconds=t.ring_timeout_seconds,
        initiated_at=t.initiated_at,
        bridged_at=t.bridged_at,
        ended_at=t.ended_at,
        failure_reason=t.failure_reason,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


_IN_MEMORY_OFFERS: set[str] = set()


async def reserve_verifier_offer(
    verifier_id: str, transfer_id: uuid.UUID, ring_timeout_seconds: int = 20
) -> bool:
    """Atomic Redis SET NX offer reservation (Step 34).

    Returns True if offer was successfully reserved for this verifier, False if
    already being offered another call.
    """
    key = f"cp:verifier:{verifier_id}:offer"
    try:
        redis_client = get_redis()
        res = await redis_client.set(
            key, str(transfer_id), nx=True, ex=ring_timeout_seconds
        )
        return res is True
    except Exception as exc:  # noqa: BLE001 - in-memory fallback below
        logger.warning(
            "verifier offer reservation failed", verifier_id=verifier_id, error=str(exc)
        )
        if key in _IN_MEMORY_OFFERS:
            return False
        _IN_MEMORY_OFFERS.add(key)
        return True


async def list_transfers(
    session: AsyncSession, user: UserContext, query: TransferListQuery
) -> PagedResponse[TransferDTO]:
    rows, total = await repo.list_transfers(session, query)
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[TransferDTO](
        data=[_to_dto(r) for r in rows],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            sort=query.sort,
            order=query.order,
        ),
    )


async def list_failed_transfers(
    session: AsyncSession, user: UserContext, page: int = 1, page_size: int = 20
) -> PagedResponse[TransferDTO]:
    rows, total = await repo.list_failed_transfers(
        session, page=page, page_size=page_size
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PagedResponse[TransferDTO](
        data=[_to_dto(r) for r in rows],
        meta=PagedMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


async def retry_transfer(
    session: AsyncSession,
    user: UserContext,
    transfer_id: uuid.UUID,
    payload: TransferRetryRequest,
) -> DataResponse[TransferDTO]:
    transfer = await repo.get_transfer(session, transfer_id)
    if not transfer:
        raise TransferNotFoundError()

    transfer.status = TransferStatus.RETRY_SCHEDULED.value
    transfer.updated_at = datetime.now(UTC)
    await repo.save_transfer(session, transfer)

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="transfer.retry",
        resource_type="transfer",
        resource_id=str(transfer.id),
        result=AuditResult.SUCCESS,
        details={"target_group": payload.target_verifier_group},
    )
    await write_outbox(
        session,
        event_type="transfer.retry_scheduled",
        payload={"transferId": str(transfer.id)},
        channel="transfers",
        aggregate_type="transfer",
        aggregate_id=str(transfer.id),
    )
    await session.commit()
    return DataResponse[TransferDTO](data=_to_dto(transfer))


async def create_callback(
    session: AsyncSession,
    user: UserContext,
    transfer_id: uuid.UUID,
    payload: TransferCallbackRequest,
) -> DataResponse[TransferDTO]:
    transfer = await repo.get_transfer(session, transfer_id)
    if not transfer:
        raise TransferNotFoundError()

    transfer.status = TransferStatus.CALLBACK_CREATED.value
    transfer.updated_at = datetime.now(UTC)
    await repo.save_transfer(session, transfer)

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="transfer.callback_created",
        resource_type="transfer",
        resource_id=str(transfer.id),
        result=AuditResult.SUCCESS,
        details={"notes": payload.notes},
    )
    await write_outbox(
        session,
        event_type="transfer.callback_created",
        payload={
            "transferId": str(transfer.id),
            "callbackTime": payload.callback_time.isoformat()
            if payload.callback_time
            else None,
        },
        channel="transfers",
        aggregate_type="transfer",
        aggregate_id=str(transfer.id),
    )
    await session.commit()
    return DataResponse[TransferDTO](data=_to_dto(transfer))


class TransferWatchdog:
    """Watchdog process recovering stuck/timed out ringing transfers (Step 34)."""

    async def tick(self, session: AsyncSession) -> int:
        now = datetime.now(UTC)
        stmt = select(Transfer).where(
            Transfer.status == TransferStatus.RINGING_VERIFIER.value
        )
        transfers = list((await session.execute(stmt)).scalars().all())

        recovered_count = 0
        for t in transfers:
            timeout_at = t.initiated_at + timedelta(seconds=t.ring_timeout_seconds)
            if now >= timeout_at:
                t.status = TransferStatus.FAILED_TIMEOUT.value
                t.failure_reason = "ring_timeout_exceeded"
                t.updated_at = now
                await repo.save_transfer(session, t)

                await write_outbox(
                    session,
                    event_type="transfer.failed_timeout",
                    payload={
                        "transferId": str(t.id),
                        "reason": "ring_timeout_exceeded",
                    },
                    channel="transfers",
                    aggregate_type="transfer",
                    aggregate_id=str(t.id),
                )
                recovered_count += 1

        if recovered_count > 0:
            await session.commit()
        return recovered_count


watchdog = TransferWatchdog()
