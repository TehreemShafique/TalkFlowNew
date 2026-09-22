"""Tests for STEP 35 — Verifier Workspace & Single-Payload Accept Context."""

from __future__ import annotations

import time
import uuid

import pytest

from app.modules.verifier import service
from app.modules.verifier.schemas import VerifierAcceptContextDTO


@pytest.mark.asyncio
async def test_accept_returns_full_context_in_one_call(seeded):
    """Accept returns everything in ONE payload in under 300ms (Step 35)."""
    call_id = uuid.uuid4()
    admin_user = seeded["admin"]

    start_time = time.perf_counter()

    async with seeded["factory"]() as session:
        resp = await service.accept_call(session, admin_user, call_id)

    elapsed = time.perf_counter() - start_time

    assert elapsed < 0.3  # Target latency < 300ms
    assert isinstance(resp.data, VerifierAcceptContextDTO)

    data = resp.data
    assert data.call_id == call_id
    assert data.qualification_status is not None
    assert len(data.qualification_fields) > 0
    assert data.consent_evidence is not None
    assert data.recording_ref is not None
    assert data.lead_history is not None
    assert data.prospect_details is not None
    assert data.script_context is not None
