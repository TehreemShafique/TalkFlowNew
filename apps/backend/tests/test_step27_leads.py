"""Tests for STEP 27 — Lead master data, external_key, and system field rejection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.leads.policies import generate_external_key
from app.modules.leads.schemas import LeadPatch, LeadUpdate


def test_system_fields_are_rejected_not_ignored():
    """System-written fields (attempts, last_attempt_at) MUST be rejected with ValidationError (Step 27)."""
    with pytest.raises(ValidationError):
        LeadUpdate(attempts=0)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        LeadPatch(last_attempt_at="2026-09-20T00:00:00Z")  # type: ignore[call-arg]


def test_external_key_fits_vendor_lead_code():
    """generated external_key is <=20 characters and unique (Step 27)."""
    keys = [generate_external_key() for _ in range(100)]
    assert all(len(k) <= 20 for k in keys)
    assert len(set(keys)) == 100
