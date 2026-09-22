"""Tests for STEP 22 — Immutability and single-active versioning constraints."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError


@pytest.mark.asyncio
async def test_approved_version_cannot_be_mutated(engine):
    """An approved script version cannot be mutated via SQL update (Step 22)."""
    try:
        async with engine.connect():
            pass
    except Exception:  # noqa: BLE001 - DB availability probe
        pytest.skip("Database connection unavailable")

    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with sessionmaker() as db_session:
        script_id = uuid.uuid4()
        version_id = uuid.uuid4()

        await db_session.execute(
            text(
                "INSERT INTO scripts (id, name, status) VALUES (:id, 'Test Script', 'approved')"
            ),
            {"id": script_id},
        )
        await db_session.execute(
            text(
                """
                INSERT INTO script_versions (id, script_id, version, status, nodes)
                VALUES (:id, :sid, 1, 'approved', '[]'::jsonb)
                """
            ),
            {"id": version_id, "sid": script_id},
        )
        await db_session.commit()

        with pytest.raises((DBAPIError, IntegrityError), match="immutable"):
            await db_session.execute(
                text(
                    'UPDATE script_versions SET nodes=\'[{"id":"n1"}]\'::jsonb WHERE id=:i'
                ),
                {"i": version_id},
            )
            await db_session.commit()


@pytest.mark.asyncio
async def test_concurrent_activation_yields_exactly_one(engine):
    """Two concurrent sessions activating two versions for the same campaign yield exactly one success (Step 22)."""
    try:
        async with engine.connect():
            pass
    except Exception:  # noqa: BLE001 - DB availability probe
        pytest.skip("Database connection unavailable")

    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    script_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    campaign_id = uuid.uuid4()

    async with sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO scripts (id, name, status) VALUES (:id, 'Campaign Script', 'approved')"
            ),
            {"id": script_id},
        )
        await session.execute(
            text(
                "INSERT INTO campaigns (id, name, status) VALUES (:id, 'Test Campaign', 'draft')"
            ),
            {"id": campaign_id},
        )
        await session.execute(
            text(
                "INSERT INTO script_versions (id, script_id, version, status) VALUES (:id, :sid, 1, 'approved')"
            ),
            {"id": v1_id, "sid": script_id},
        )
        await session.execute(
            text(
                "INSERT INTO script_versions (id, script_id, version, status) VALUES (:id, :sid, 2, 'approved')"
            ),
            {"id": v2_id, "sid": script_id},
        )
        await session.commit()

    async def act(ver_id: uuid.UUID) -> str:
        async with sessionmaker() as s:
            try:
                act_id = uuid.uuid4()
                await s.execute(
                    text(
                        """
                        INSERT INTO script_activations (id, script_id, script_version_id, campaign_id, activated_at)
                        VALUES (:id, :sid, :vid, :cid, clock_timestamp())
                        """
                    ),
                    {"id": act_id, "sid": script_id, "vid": ver_id, "cid": campaign_id},
                )
                await s.commit()
                return "ok"
            except (IntegrityError, AppError, Exception):  # noqa: BLE001 - concurrency loser path
                await s.rollback()
                return "rejected"

    results = await asyncio.gather(act(v1_id), act(v2_id))
    assert sorted(results) == ["ok", "rejected"]
