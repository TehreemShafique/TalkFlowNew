"""Offline unit tests for the analytics service layer, rate math and DTOs.

These run without a database: the pure KPI definitions (policies.py), Rule R5 scope
resolution, and the camelCase envelope are all exercised here.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

from app.core.context import UserContext
from app.modules.analytics import policies
from app.modules.analytics.policies import (
    contact_rate,
    qualification_rate,
    transfer_success,
    verifier_close_rate,
)
from app.modules.analytics.schemas import (
    AnalyticsDateQuery,
    AnalyticsSummaryDTO,
    CampaignAggDTO,
)
from app.packages.contracts.base import DataResponse


def _actor(role: str, tenant_id: str | None) -> UserContext:
    return UserContext.from_principal(
        user_id=uuid.uuid4(),
        role=role,
        permissions=set(),
        tenant_id=tenant_id,
    )


# ---------------------------------------------------------------------------
# KPI definitions (policies.py - pure functions)
# ---------------------------------------------------------------------------


class TestRateMath:
    def test_contact_rate(self) -> None:
        assert contact_rate(8, 10) == 0.8

    def test_qualification_rate(self) -> None:
        assert qualification_rate(4, 8) == 0.5

    def test_transfer_success(self) -> None:
        assert transfer_success(3, 4) == 0.75

    def test_verifier_close_rate(self) -> None:
        assert verifier_close_rate(2, 4) == 0.5

    def test_zero_denominator_is_zero_not_nan(self) -> None:
        assert contact_rate(5, 0) == 0.0
        assert qualification_rate(0, 0) == 0.0
        assert transfer_success(0, 0) == 0.0
        assert verifier_close_rate(0, 0) == 0.0

    def test_rounding_is_stable(self) -> None:
        assert contact_rate(1, 3) == 0.3333


# ---------------------------------------------------------------------------
# Rule R5 scope resolution (policies.resolve_scope_constraints)
# ---------------------------------------------------------------------------


class TestScopeResolution:
    def test_master_admin_is_unrestricted(self) -> None:
        assert policies.resolve_scope_constraints(_actor("MASTER_ADMIN", "t-ten")) == {}

    def test_devops_is_unrestricted(self) -> None:
        assert policies.resolve_scope_constraints(_actor("DEVOPS_IT", "t-ten")) == {}

    def test_campaign_manager_is_scoped_to_tenant(self) -> None:
        assert policies.resolve_scope_constraints(
            _actor("CAMPAIGN_MANAGER", "t-42")
        ) == {"tenant_id": "t-42"}

    def test_tenantless_limited_user_is_unrestricted(self) -> None:
        assert (
            policies.resolve_scope_constraints(_actor("CAMPAIGN_MANAGER", None)) == {}
        )


# ---------------------------------------------------------------------------
# Wire contract: camelCase envelope
# ---------------------------------------------------------------------------


class TestEnvelope:
    def test_campaign_dto_serializes_to_camel_case(self) -> None:
        row = CampaignAggDTO(
            date=date(2026, 9, 1),
            campaign_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            total_calls=10,
            answered=8,
            contacted=7,
            qualified=3,
            transferred=2,
            verifier_accepted=1,
            disqualified=1,
            answer_rate="80.0%",
            qual_rate="42.9%",
            transfer_rate="66.7%",
            avg_duration=42.5,
        )
        payload = json.loads(DataResponse(data=row).model_dump_json(by_alias=True))
        assert payload == {
            "data": {
                "date": "2026-09-01",
                "campaignId": "11111111-1111-1111-1111-111111111111",
                "campaignName": None,
                "totalCalls": 10,
                "answered": 8,
                "contacted": 7,
                "qualified": 3,
                "transferred": 2,
                "verifierAccepted": 1,
                "disqualified": 1,
                "answerRate": "80.0%",
                "qualRate": "42.9%",
                "transferRate": "66.7%",
                "avgDuration": 42.5,
            }
        }

    def test_summary_dto_serializes_to_camel_case(self) -> None:
        summary = AnalyticsSummaryDTO(
            total_calls=100,
            answered_calls=80,
            contacted_calls=60,
            qualified_calls=30,
            transferred_calls=12,
            verifier_accepted=6,
            disqualified_calls=10,
            answer_rate="80.0%",
            qual_rate="50.0%",
            transfer_rate="40.0%",
            avg_duration_sec=30.0,
        )
        payload = json.loads(summary.model_dump_json(by_alias=True))
        assert payload["totalCalls"] == 100
        assert payload["answeredCalls"] == 80
        assert payload["contactedCalls"] == 60
        assert payload["qualifiedCalls"] == 30
        assert payload["transferredCalls"] == 12
        assert payload["verifierAccepted"] == 6
        assert payload["disqualifiedCalls"] == 10
        assert payload["answerRate"] == "80.0%"
        assert payload["qualRate"] == "50.0%"
        assert payload["transferRate"] == "40.0%"
        assert payload["avgDurationSec"] == 30.0
