"""Shared fixtures for the recordings module integration suite.

Runs the FastAPI app in-process via httpx ``ASGITransport`` against a
dedicated ``talkflow_test`` database, with ``get_db`` overridden to the test
engine.  RBAC + recording data is seeded per test (TRUNCATE + reseed) so the
suite is fully self-contained and does not touch the live ``talkflow`` DB.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

# -- Environment MUST be configured before any `app.*` import ----------------
_STORAGE_ROOT = Path(tempfile.mkdtemp(prefix="tf_recordings_test_"))
os.environ["DATABASE_URL"] = "postgresql+asyncpg://talkflow:admin@localhost:5432/talkflow_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/9"
os.environ["STORAGE_LOCAL_ROOT"] = str(_STORAGE_ROOT)
os.environ["STORAGE_PUBLIC_BASE_URL"] = "http://testserver"

from datetime import UTC, datetime

import httpx
import pytest_asyncio
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import create_access_token
from app.modules.users_rbac import repository as users_repo
from app.modules.users_rbac.service import seed_roles
from app.packages.contracts.enums import RecordingStatus, UserStatus
from app.packages.db.base import Base
from app.packages.db.models import (
    CallRecording,
    Script,
    ScriptActivation,
    ScriptVersion,
    User,
    _shared,
    call_transcripts_table,
    calls_table,
    campaigns_table,
    leads_table,
    retention_policies_table,
)

TEST_DB_URL = "postgresql+asyncpg://talkflow:admin@localhost:5432/talkflow_test"
ADMIN_EMAIL = "qa-test-admin@phonova.io"
VIEWER_EMAIL = "qa-test-viewer@phonova.io"

# Register the shared projections on Base.metadata so CallRecording's FKs
# (calls / leads / campaigns / retention_policies) resolve within one metadata
# for create_all / drop_all.  Test-process only; the app is unaffected.
for _shared_table in list(_shared.tables.values()):
    if _shared_table.name not in Base.metadata.tables:
        Base.metadata._add_table(_shared_table.name, _shared_table.schema, _shared_table)

_TRUNCATE = text(
    "TRUNCATE TABLE outbox, audit_log, qa_reviews, call_transcripts, call_recordings, "
    "call_qualification_fields, call_performance, call_node_path, call_events, "
    "transcript_turns, calls, leads, lead_import_jobs, suppression_entries, exports, "
    "campaigns, script_activations, script_versions, scripts, retention_policies, user_sessions, user_roles, users, roles "
    "RESTART IDENTITY CASCADE"
)


async def _ensure_test_database() -> None:
    """Create `talkflow_test` if missing (connect to the admin `talkflow` DB)."""
    engine = create_async_engine(
        "postgresql+asyncpg://talkflow:admin@localhost:5432/talkflow",
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'talkflow_test'")
            )
            if exists.first() is None:
                await conn.execute(text("CREATE DATABASE talkflow_test"))
        await engine.dispose()
    finally:
        await engine.dispose()


def _combined_metadata() -> MetaData:
    """Base.metadata now also hosts the shared projections (see above)."""
    return Base.metadata


@pytest_asyncio.fixture(scope="session")
async def engine():
    await _ensure_test_database()
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    metadata = _combined_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    await get_redis().flushdb()
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(engine):
    """Clean DB + seed a MASTER_ADMIN and a VIEWER, plus one ready recording."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(_TRUNCATE)
        await seed_roles(db)

        master = await users_repo.find_role_by_name(db, "MASTER_ADMIN")
        viewer_role = await users_repo.find_role_by_name(db, "VIEWER")

        admin_id = uuid.uuid4()
        admin = User(
            id=admin_id,
            email=ADMIN_EMAIL,
            username="qa_admin",
            # Auth never verifies passwords in this suite; a placeholder keeps
            # the heavy Argon2id hashing (and its 64 MB allocation) out of tests.
            hashed_password="$argon2id$placeholder",
            full_name="QA Test Admin",
            extension="000",
            is_active=True,
            status=UserStatus.APPROVED.value,
        )
        db.add(admin)
        await db.flush()
        await users_repo.replace_user_roles(db, admin_id, [master.id])

        viewer_id = uuid.uuid4()
        viewer = User(
            id=viewer_id,
            email=VIEWER_EMAIL,
            username="qa_viewer",
            hashed_password="$argon2id$placeholder",
            full_name="QA Test Viewer",
            extension="001",
            is_active=True,
            status=UserStatus.APPROVED.value,
        )
        db.add(viewer)
        await db.flush()
        await users_repo.replace_user_roles(db, viewer_id, [viewer_role.id])

        campaign_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        call_id = uuid.uuid4()
        rp_id = uuid.uuid4()
        recording_id = uuid.uuid4()
        storage_key = f"rec/{call_id}.wav"

        await db.execute(
            campaigns_table.insert().values(
                id=campaign_id, name="Medicare Advantage 2026"
            )
        )
        await db.execute(
            leads_table.insert().values(
                id=lead_id,
                first_name="Jane",
                last_name="Doe",
                phone_normalized="18505554586",
            )
        )
        await db.execute(
            retention_policies_table.insert().values(
                id=rp_id, name="Standard", audio_days=90
            )
        )
        await db.execute(
            calls_table.insert().values(
                id=call_id,
                tenant_id=None,
                started_at=datetime(2026, 9, 16, 14, 30, tzinfo=UTC),
                duration_seconds=42,
                disposition="IQA-8000-007",
                qualification_status="PASSED",
                disqualification_reason=None,
                lead_id=lead_id,
                campaign_id=campaign_id,
                verifier_id=None,
            )
        )
        recording = CallRecording(
            id=recording_id,
            call_id=call_id,
            vicidial_recording_id="VICI-0001",
            lead_id=lead_id,
            campaign_id=campaign_id,
            status=RecordingStatus.READY.value,
            storage_provider="local",
            storage_key=storage_key,
            mime_type="audio/wav",
            duration_seconds=42,
            retention_policy_id=rp_id,
            expires_at=None,
            consent_offset_ms=1000,
            audio_purged_at=None,
        )
        db.add(recording)
        await db.flush()
        await db.execute(
            call_transcripts_table.insert().values(
                [
                    {
                        "id": uuid.uuid4(),
                        "call_id": call_id,
                        "seq": 1,
                        "speaker": "Agent",
                        "time": "00:05",
                        "text": "Hello, thank you for calling.",
                    },
                    {
                        "id": uuid.uuid4(),
                        "call_id": call_id,
                        "seq": 2,
                        "speaker": "Bot",
                        "time": "00:12",
                        "text": "I can help with Medicare plan options.",
                    },
                ]
            )
        )
        await db.commit()

        # Physical audio file backing the local provider.
        from app.packages.storage.provider import LocalStorageProvider

        audio_path = LocalStorageProvider(root=_STORAGE_ROOT)._path(storage_key)
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake-audio-bytes")

        admin_token, _ = create_access_token({"sub": ADMIN_EMAIL})
        viewer_token, _ = create_access_token({"sub": VIEWER_EMAIL})

    return {
        "factory": factory,
        "admin_id": admin_id,
        "viewer_id": viewer_id,
        "headers": {"Authorization": f"Bearer {admin_token}"},
        "viewer_headers": {"Authorization": f"Bearer {viewer_token}"},
        "recording_id": recording_id,
        "call_id": call_id,
        "lead_id": lead_id,
        "storage_key": storage_key,
        "audio_path": LocalStorageProvider(root=_STORAGE_ROOT)._path(storage_key),
        "audio_bytes": b"RIFF\x00\x00\x00\x00WAVEfake-audio-bytes",
    }


@pytest_asyncio.fixture
async def client(engine):
    from app.main import app

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver/api/v1"
    ) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)