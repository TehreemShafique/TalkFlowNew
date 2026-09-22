"""Data access repository for transfers (Step 34)."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transfers.schemas import TransferListQuery
from app.packages.contracts.enums import TransferStatus
from app.packages.db.models import Transfer


async def get_transfer(
    session: AsyncSession, transfer_id: uuid.UUID
) -> Transfer | None:
    stmt = select(Transfer).where(Transfer.id == transfer_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_transfers(
    session: AsyncSession, query: TransferListQuery
) -> tuple[list[Transfer], int]:
    filters = []
    if query.status:
        filters.append(Transfer.status == query.status.value)
    if query.verifier_id:
        filters.append(Transfer.verifier_id == query.verifier_id)
    if query.campaign_id:
        filters.append(Transfer.campaign_id == query.campaign_id)

    total = (
        await session.execute(
            select(func.count(Transfer.id)).where(and_(True, *filters))
        )
    ).scalar_one()

    stmt = (
        select(Transfer)
        .where(and_(True, *filters))
        .order_by(Transfer.initiated_at.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def list_failed_transfers(
    session: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[Transfer], int]:
    failed_statuses = [
        TransferStatus.FAILED_NO_VERIFIER.value,
        TransferStatus.FAILED_TIMEOUT.value,
        TransferStatus.FAILED_REJECTED.value,
        TransferStatus.FAILED_TECHNICAL.value,
    ]
    filters = [Transfer.status.in_(failed_statuses)]

    total = (
        await session.execute(
            select(func.count(Transfer.id)).where(and_(True, *filters))
        )
    ).scalar_one()

    stmt = (
        select(Transfer)
        .where(and_(True, *filters))
        .order_by(Transfer.initiated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def save_transfer(session: AsyncSession, transfer: Transfer) -> None:
    session.add(transfer)
    await session.flush()
