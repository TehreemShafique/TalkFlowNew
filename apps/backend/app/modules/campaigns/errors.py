"""Campaigns module error codes (registered into the central registry).

The start guard reports **every** unmet prerequisite at once: the individual
``CAMPAIGN_NO_*`` codes are carried in the ``details.problems`` list of a
single ``campaign.start_failed`` envelope rather than raised one at a time.
"""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    register_error,
)

# Start-guard problem codes (single source of truth, consumed by policies.py).
CAMPAIGN_NO_ACTIVE_SCRIPT = "campaign.no_active_script"
CAMPAIGN_NO_RULE_SET = "campaign.no_rule_set"
CAMPAIGN_NO_COMPLIANCE_PROFILE = "campaign.no_compliance_profile"
CAMPAIGN_NO_VERIFIER_GROUP = "campaign.no_verifier_group"
CAMPAIGN_NO_LIST_MAPPING = "campaign.no_list_mapping"
CAMPAIGN_NO_CALLER_IDS = "campaign.no_caller_ids"

# Domain errors raised by the router/service.
register_error("campaign.not_found", 404, "Campaign not found.")
register_error(
    "campaign.start_failed",
    409,
    "Campaign cannot be started; one or more prerequisites are missing.",
)
register_error(
    "campaign.invalid_state",
    409,
    "Campaign is not in a state that permits this action.",
)
register_error(
    "campaign.version_conflict", 409, "Campaign was modified by another user."
)

# Individual start-guard problem codes (returned in details.problems).
register_error(CAMPAIGN_NO_ACTIVE_SCRIPT, 409, "No active script version is bound.")
register_error(CAMPAIGN_NO_RULE_SET, 409, "No rule set version is bound.")
register_error(CAMPAIGN_NO_COMPLIANCE_PROFILE, 409, "No compliance profile is bound.")
register_error(
    CAMPAIGN_NO_VERIFIER_GROUP, 409, "No verifier in-group (closer) is bound."
)
register_error(
    CAMPAIGN_NO_LIST_MAPPING, 409, "No VICIdial campaign/list mapping exists."
)


class CampaignNotFoundError(NotFoundError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__("campaign.not_found", message=message)


class CampaignStartFailedError(ConflictError):
    """409 carrying the full ``problems`` list from the pure start guard."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__(
            "campaign.start_failed",
            details={"problems": sorted(problems)},
        )
        self.problems = problems


class CampaignInvalidStateError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("campaign.invalid_state", details=details)


class CampaignVersionConflictError(ConflictError):
    def __init__(self) -> None:
        super().__init__("campaign.version_conflict")
