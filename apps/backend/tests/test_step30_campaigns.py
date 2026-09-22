"""Tests for STEP 30 — Campaign Start Guard."""

from __future__ import annotations

import uuid

from app.modules.campaigns.errors import (
    CAMPAIGN_NO_ACTIVE_SCRIPT,
    CAMPAIGN_NO_CALLER_IDS,
    CAMPAIGN_NO_COMPLIANCE_PROFILE,
    CAMPAIGN_NO_LIST_MAPPING,
    CAMPAIGN_NO_RULE_SET,
    CAMPAIGN_NO_VERIFIER_GROUP,
)
from app.modules.campaigns.policies import CampaignSnapshot, can_start_campaign


def test_start_reports_every_gap_at_once():
    """Start guard MUST return ALL missing prerequisite problem codes at once (Step 30)."""
    empty_snapshot = CampaignSnapshot()
    problems = can_start_campaign(empty_snapshot)

    expected = {
        CAMPAIGN_NO_ACTIVE_SCRIPT,
        CAMPAIGN_NO_RULE_SET,
        CAMPAIGN_NO_COMPLIANCE_PROFILE,
        CAMPAIGN_NO_VERIFIER_GROUP,
        CAMPAIGN_NO_LIST_MAPPING,
        CAMPAIGN_NO_CALLER_IDS,
    }
    assert set(problems) == expected

    # When all prerequisites are present, returns empty list
    valid_snapshot = CampaignSnapshot(
        active_script_version_id=uuid.uuid4(),
        script_version_status="active",
        rule_set_version_id=uuid.uuid4(),
        compliance_profile_id=uuid.uuid4(),
        closer_in_group="VERIFIER1",
        vicidial_campaign_id="CAMP1",
        vicidial_list_ids=("101",),
        caller_ids=("18005550100",),
    )
    assert can_start_campaign(valid_snapshot) == []
