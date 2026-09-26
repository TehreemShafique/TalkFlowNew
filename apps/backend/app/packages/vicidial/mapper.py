"""VICIdial status disposition mapping (BACKEND-8a).

Maps TalkFlow call outcomes to the VICIdial statuses Asterisk / VICIdial
assigns on the lead row so dashboard dispositions reconcile with the dialer's
``vicidial_list`` statuses.  VICIdial ships many statuses; TalkFlow deliberately
drives a small, auditable subset so QA and compliance reporting never need to
re-learn a new code per month.
"""

from __future__ import annotations

# TalkFlow outcome -> VICIdial status code.
#
#   AIQUAL  AI Qualified                Transfered to a verifier.
#   AINQ    AI Not Qualified            Failed qualification rules.
#   AICB    AI Callback Requested       Lead asked the bot for a call back.
#   DNC     Do Not Call                 Opt-out / suppression (system DNC).
#   NA      No Answer                   Dialer answered, no one picked up.
#   B       Busy                        Line busy on this attempt.
#   DC      Disconnected                The number is disconnected/dead.
OUTCOME_TO_VICIDIAL_STATUS: dict[str, str] = {
    "qualified": "AIQUAL",
    "not_qualified": "AINQ",
    "callback": "AICB",
    "opt_out": "DNC",
    "suppressed": "DNC",
    "no_answer": "NA",
    "busy": "B",
    "disconnected": "DC",
}


def map_talkflow_to_vicidial_status(outcome: str) -> str:
    """Map a TalkFlow call outcome to the matching VICIdial status code.

    Raises :class:`KeyError` for outcomes the control plane does not map - a
    caller must never silently persist an unmapped disposition into VICIdial.
    """
    try:
        return OUTCOME_TO_VICIDIAL_STATUS[outcome]
    except KeyError:
        raise KeyError(
            f"Unmapped TalkFlow outcome {outcome!r}; expected one of "
            f"{sorted(OUTCOME_TO_VICIDIAL_STATUS)}"
        ) from None


def map_outcome_safe(outcome: str | None) -> str | None:
    """Best-effort variant that returns ``None`` for unknown outcomes.

    Used on ingest paths where an unmapped value should not abort the whole
    record (the raw value is still preserved on ``calls.disposition``).
    """
    if outcome is None:
        return None
    return OUTCOME_TO_VICIDIAL_STATUS.get(outcome)


def all_outcomes() -> list[str]:
    return sorted(OUTCOME_TO_VICIDIAL_STATUS)
