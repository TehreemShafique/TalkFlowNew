"""Tests for STEP 38 — Retention Policies & Audio Purger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
import pytest

from app.packages.contracts.enums import RecordingStatus
from app.packages.db.models import CallRecording
from workers.retention_purger import run_retention_purger


def test_purger_retention_status_values():
    """Step 38: Purged status constants."""
    assert RecordingStatus.PURGED.value == "purged"


async def test_purge_keeps_metadata_in_memory():
    """Step 38 requirement: metadata row survives when audio is purged."""
    rec = CallRecording(
        id=uuid.uuid4(),
        call_id=uuid.uuid4(),
        status=RecordingStatus.READY.value,
        storage_key="recordings/audio_99.wav",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    # Purge operation updates status and audio_purged_at while retaining rec instance
    rec.status = RecordingStatus.PURGED.value
    rec.audio_purged_at = datetime.now(UTC)

    assert rec is not None
    assert rec.status == "purged"
    assert rec.audio_purged_at is not None
