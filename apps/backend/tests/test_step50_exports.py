"""Tests for STEP 50 — Async Scope-Inherited PII-Masked Exports."""

from __future__ import annotations

import pytest

from app.core.context import UserContext
from app.modules.exports.policies import ExportPolicy, build_csv


def test_export_omits_pii_for_reporting_user():
    """Step 50 requirement: export omits caller_number PII for reporting user."""
    reporting_user = UserContext(
        user_id="usr_reporting",
        tenant_id=None,
        permissions={"export.create", "export.view", "export.download"},
        role="REPORTING_USER",
    )

    mask_phone = ExportPolicy.mask_phone_numbers(reporting_user)
    assert mask_phone is True

    rows = [
        {
            "id": "c_123",
            "started_at": "2026-09-22T00:00:00Z",
            "duration_seconds": 120,
            "disposition": "qualified",
            "caller_number": "+15551234567",
        }
    ]

    headers = [
        "id",
        "started_at",
        "duration_seconds",
        "disposition",
        "caller_number",
    ]

    csv_bytes = build_csv(rows, headers=headers, mask_phone=mask_phone)
    csv_str = csv_bytes.decode("utf-8")
    header_line = csv_str.split("\n")[0]

    # caller_number must NOT be in header or output for non-PII tenant
    assert "caller_number" not in header_line
    assert "+15551234567" not in csv_str


def test_export_includes_pii_for_admin_user():
    admin_user = UserContext(
        user_id="usr_admin",
        tenant_id=None,
        permissions={"export.create", "export.view", "export.download", "pii.view_full"},
        role="SUPER_ADMIN",
    )

    mask_phone = ExportPolicy.mask_phone_numbers(admin_user)
    assert mask_phone is False

    rows = [
        {
            "id": "c_123",
            "started_at": "2026-09-22T00:00:00Z",
            "duration_seconds": 120,
            "disposition": "qualified",
            "caller_number": "+15551234567",
        }
    ]

    headers = [
        "id",
        "started_at",
        "duration_seconds",
        "disposition",
        "caller_number",
    ]

    csv_bytes = build_csv(rows, headers=headers, mask_phone=mask_phone)
    csv_str = csv_bytes.decode("utf-8")
    header_line = csv_str.split("\n")[0]

    assert "caller_number" in header_line
    assert "+15551234567" in csv_str
