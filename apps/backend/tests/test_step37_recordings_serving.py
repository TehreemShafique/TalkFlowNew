"""Tests for STEP 37 — Recording Serving & Status Alignment."""

from __future__ import annotations

import uuid
from app.core.context import UserContext
from app.core.security import create_signed_grant, decode_signed_grant
from app.packages.contracts.enums import RecordingStatus


def test_recording_status_enum_alignment():
    """Worker status strings match frontend enum (Step 37)."""
    assert RecordingStatus.PENDING == "pending"
    assert RecordingStatus.WAITING_FOR_SOURCE == "waiting_for_source"
    assert RecordingStatus.FETCHING == "fetching"
    assert RecordingStatus.VALIDATING == "validating"
    assert RecordingStatus.STORING == "storing"
    assert RecordingStatus.READY == "ready"
    assert RecordingStatus.FAILED == "failed"
    assert RecordingStatus.PURGED == "purged"


def test_playback_url_token_generation():
    """Step 37: 5-minute presigned playback URL token validation."""
    storage_key = "recordings/rec_123.wav"
    token, jti = create_signed_grant(storage_key, purpose="stream", ttl_seconds=300)

    payload = decode_signed_grant(token)
    assert payload["sub"] == storage_key
    assert payload["purpose"] == "stream"


def test_download_token_generation():
    """Step 37: Single-use download token validation."""
    storage_key = "recordings/rec_123.wav"
    token, jti = create_signed_grant(storage_key, purpose="download", ttl_seconds=300)

    payload = decode_signed_grant(token)
    assert payload["sub"] == storage_key
    assert payload["purpose"] == "download"
