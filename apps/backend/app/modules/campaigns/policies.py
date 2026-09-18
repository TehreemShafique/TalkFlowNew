"""Campaign authorization + start-guard policies (ADR-03: zero I/O).

Everything here is a pure function over a plain snapshot, so the highest-risk
logic - deciding whether a campaign may go live - is exhaustively testable in
milliseconds without a database or an HTTP client.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.context import UserContext
from app.core.permissions import PERM_CAMPAIGN_START, PERM_CAMPAIGN_VIEW
from app.modules.campaigns.errors import (
    CAMPAIGN_NO_ACTIVE_SCRIPT,
    CAMPAIGN_NO_COMPLIANCE_PROFILE,
    CAMPAIGN_NO_LIST_MAPPING,
    CAMPAIGN_NO_RULE_SET,
    CAMPAIGN_NO_VERIFIER_GROUP,
)
from app.packages.contracts.enums import CampaignStatus

# A campaign may be (re)started from any non-running, non-archived state.
STARTABLE_STATUSES: frozenset[str] = frozenset(
    {
        CampaignStatus.DRAFT.value,
        CampaignStatus.PAUSED.value,
        CampaignStatus.STOPPED.value,
    }
)


@dataclass(frozen=True, slots=True)
class CampaignSnapshot:
    """Plain-value view of a campaign consumed by the pure start guard."""

    active_script_version_id: uuid.UUID | None = None
    script_version_status: str | None = None
    rule_set_version_id: uuid.UUID | None = None
    compliance_profile_id: uuid.UUID | None = None
    closer_in_group: str | None = None
    vicidial_campaign_id: str | None = None
    vicidial_list_ids: tuple[str, ...] = ()


def can_start_campaign(c: CampaignSnapshot) -> list[str]:
    """Return **every** unmet prerequisite code (empty list == dialable)."""
    problems: list[str] = []
    if not c.active_script_version_id:
        problems.append(CAMPAIGN_NO_ACTIVE_SCRIPT)
    elif c.script_version_status is not None and c.script_version_status not in ("approved", "active"):
        problems.append(CAMPAIGN_NO_ACTIVE_SCRIPT)
    if not c.rule_set_version_id:
        problems.append(CAMPAIGN_NO_RULE_SET)
    if not c.compliance_profile_id:
        problems.append(CAMPAIGN_NO_COMPLIANCE_PROFILE)
    if not c.closer_in_group:
        problems.append(CAMPAIGN_NO_VERIFIER_GROUP)
    if not c.vicidial_campaign_id or not c.vicidial_list_ids:
        problems.append(CAMPAIGN_NO_LIST_MAPPING)
    return problems


def can_transition_to_start(status: str) -> bool:
    return status in STARTABLE_STATUSES


def can_pause(status: str) -> bool:
    return status == CampaignStatus.ACTIVE.value


def can_stop(status: str) -> bool:
    """A stop is valid from any running state (active or paused)."""
    return status in {
        CampaignStatus.ACTIVE.value,
        CampaignStatus.PAUSED.value,
    }


class CampaignPolicy:
    """Permission helpers for the campaigns control plane (Rule R4)."""

    @staticmethod
    def can_view(user: UserContext) -> bool:
        return PERM_CAMPAIGN_VIEW in user.permissions

    @staticmethod
    def can_start(user: UserContext) -> bool:
        return PERM_CAMPAIGN_START in user.permissions

    @staticmethod
    def scope_unlimited(user: UserContext) -> bool:
        return user.role == "MASTER_ADMIN"


def resolve_scope_constraints(user: UserContext) -> dict:
    """Return the explicit scope filter to enforce (Rule R5).

    Campaigns are currently global governance objects; fine-grained scoping
    (campaign assignments / verifier groups) arrives with those modules.  The
    hook is kept so every repository call already threads a constraint dict and
    nothing widens silently when scoping is introduced.
    """
    _ = user
    return {}
