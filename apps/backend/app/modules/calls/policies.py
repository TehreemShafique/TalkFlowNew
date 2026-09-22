"""Call authorization + qualification/disposition policies (ADR-03: zero I/O).

Everything here is a pure function over a plain snapshot, so the highest-risk
logic - deciding whether a caller is qualified and which VICIdial status a
result maps to - is exhaustively testable without a database or an HTTP client.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.context import UserContext
from app.core.permissions import (
    PERM_CALL_DISPOSITION,
    PERM_CALL_VIEW,
    PERM_PII_VIEW_FULL,
)
from app.core.security import mask_phone
from app.packages.contracts.enums import CallStatus, QualificationStatus

# ---------------------------------------------------------------------------
# The four-layer disposition taxonomy (TalkFlow.md sections 11.3 / 14.2).
# One call reports exactly one disposition; layers answer different questions.
# ---------------------------------------------------------------------------
TELEPHONY_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "no_answer",
        "busy",
        "rejected",
        "voicemail_detected",
        "amd_machine",
        "amd_uncertain",
        "invalid_number",
        "network_failure",
        "abandoned",
    }
)

CONVERSATION_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "caller_hung_up_early",
        "consent_refused",
        "opted_out",
        "language_barrier",
        "silence_no_response",
        "script_completed",
    }
)

QUALIFICATION_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "qualified_transferred",
        "qualified_transfer_failed",
        "disqualified_age",
        "disqualified_no_part_a",
        "disqualified_no_part_b",
        "disqualified_coverage",
        "disqualified_state",
        "disqualified_other",
        "incomplete",
        "callback_requested",
    }
)

VERIFIER_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "verified_accepted",
        "verified_rejected",
        "verifier_no_contact",
    }
)

# Disposition -> taxonomy layer, precomputed once so a lookup is O(1).
_DISPOSITION_LAYER: dict[str, str] = {
    **{d: "telephony" for d in TELEPHONY_DISPOSITIONS},
    **{d: "conversation" for d in CONVERSATION_DISPOSITIONS},
    **{d: "qualification" for d in QUALIFICATION_DISPOSITIONS},
    **{d: "verifier" for d in VERIFIER_DISPOSITIONS},
}

# Qualification-status consequences of each qualification-layer disposition.
# (status, disqualification_reason)
_QUALIFICATION_RESULTS: dict[str, tuple[str, str | None]] = {
    "qualified_transferred": (QualificationStatus.QUALIFIED.value, None),
    "qualified_transfer_failed": (QualificationStatus.QUALIFIED.value, None),
    "disqualified_age": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_age_range",
    ),
    "disqualified_no_part_a": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_no_part_a",
    ),
    "disqualified_no_part_b": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_no_part_b",
    ),
    "disqualified_coverage": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_coverage",
    ),
    "disqualified_state": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_state",
    ),
    "disqualified_other": (
        QualificationStatus.DISQUALIFIED.value,
        "disqualified_other",
    ),
    "incomplete": (QualificationStatus.INCOMPLETE.value, None),
    "callback_requested": (QualificationStatus.INCOMPLETE.value, "callback_requested"),
}

# Seed for `dispositions.vicidial_status` (talkflow_backend.md section 14.3).
# Config, not fact - confirmed against the live `vicidial_statuses` table and
# the campaign's own status list before go-live.
_VICIDIAL_MAP: dict[str, str] = {
    "qualified_transferred": "RAXFER",
    "qualified_transfer_failed": "DNQ",
    "disqualified_age": "DNQ",
    "disqualified_no_part_a": "DNQ",
    "disqualified_no_part_b": "DNQ",
    "disqualified_coverage": "DNQ",
    "disqualified_state": "DNQ",
    "disqualified_other": "DNQ",
    "opted_out": "DNC",
    "callback_requested": "CLBK",
    "dead_air": "DAIR",
    "no_answer": "NP",
    "amd_machine": "A",
    "caller_hung_up_early": "HP",
    "verified_rejected": "RJ",
    "verified_accepted": "SALE",
}

# A disposition may only be changed while the call is still active in the
# dialer loop; once a call has closed (transferred / failed / completed) it is
# immutable except by the verifier pipeline, which has its own endpoints.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        CallStatus.TRANSFERRED.value,
        CallStatus.COMPLETED.value,
        CallStatus.FAILED.value,
    }
)

# "Live" statuses surfaced by GET /calls/live (matches the partial index).
LIVE_STATUSES: frozenset[str] = frozenset(
    {
        CallStatus.IN_PROGRESS.value,
        CallStatus.TRANSFERRING.value,
    }
)

# Best-effort live-state mapping until `call.state_changed` events drive it
# (TalkFlow.md section 22.2 - the frontend must never infer state itself).
_LIVE_STATE_BY_STATUS: dict[str, str] = {
    CallStatus.DIALING.value: "connecting",
    CallStatus.RINGING.value: "connecting",
    CallStatus.ANSWERED.value: "greeting",
    CallStatus.IN_PROGRESS.value: "listening",
    CallStatus.TRANSFERRING.value: "transferring",
    CallStatus.TRANSFERRED.value: "ending",
    CallStatus.COMPLETED.value: "ending",
    CallStatus.FAILED.value: "ending",
}


def _coerce_bool(value: Any) -> bool | None:
    """Coerce a captured qualification field to True/False/None (stays pure)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value) if value in (0, 1) else None
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "y", "1"}:
        return True
    if normalized in {"false", "no", "n", "0"}:
        return False
    return None


# Medicare eligibility truth table keyed on ``(part_ab, age_in_range)``.
# Part A/B enrollment is the hard gate: a stated "no" disqualifies even when the
# age evidence is missing; anything undecided leaves the call ``incomplete``.
_QUALIFICATION_TABLE: dict[
    tuple[bool | None, bool | None], tuple[QualificationStatus, str | None]
] = {
    (False, False): (QualificationStatus.DISQUALIFIED, "disqualified_no_part_ab"),
    (False, True): (QualificationStatus.DISQUALIFIED, "disqualified_no_part_ab"),
    (False, None): (QualificationStatus.DISQUALIFIED, "disqualified_no_part_ab"),
    (True, False): (QualificationStatus.DISQUALIFIED, "disqualified_age_range"),
    (None, False): (QualificationStatus.DISQUALIFIED, "disqualified_age_range"),
    (True, True): (QualificationStatus.QUALIFIED, None),
    (True, None): (QualificationStatus.INCOMPLETE, None),
    (None, True): (QualificationStatus.INCOMPLETE, None),
    (None, None): (QualificationStatus.INCOMPLETE, None),
}


def evaluate_qualification(
    fields: Mapping[str, Any],
) -> tuple[QualificationStatus, str | None]:
    """Pure Medicare qualification decision from captured evidence.

    Returns ``(status, disqualification_reason)``.  Part A/B enrollment is the
    hard gate: a stated "no" disqualifies even when the age evidence is missing.
    A capture that never happens leaves the call ``incomplete`` so a queue can
    surface it for a callback - never silently ``qualified``.

    .. note:: This is the eligibility *policy* the rule engine module will own;
              the calls module keeps a pure, testable shape so the live call
              card and the CDR column render the same answer.
    """
    part_ab = _coerce_bool(fields.get("medicare_part_ab"))
    age_in_range = _coerce_bool(fields.get("age_in_range"))
    return _QUALIFICATION_TABLE[(part_ab, age_in_range)]


def map_disposition_layer(disposition: str | None) -> str:
    """Return which of the four taxonomy layers a disposition belongs to."""
    if not disposition:
        return "unknown"
    return _DISPOSITION_LAYER.get(disposition, "unknown")


def qualification_result(disposition: str | None) -> tuple[str | None, str | None]:
    """The ``(qualification_status, disqualification_reason)`` a disposition implies.

    Qualification-layer dispositions drive the CDR qualification column; the
    other layers do not change qualification evidence, so callers receive
    ``(None, None)`` and leave the stored value untouched.
    """
    if not disposition:
        return None, None
    result = _QUALIFICATION_RESULTS.get(disposition)
    if result is None:
        return None, None
    return result


def to_vicidial_status(disposition: str | None) -> str | None:
    """Map a TalkFlow disposition to the seeded VICIdial status (section 14.3)."""
    if not disposition:
        return None
    return _VICIDIAL_MAP.get(disposition)


def can_update_disposition(status: str) -> bool:
    """Disposition is only writable while the call is still in the dialer loop."""
    return status not in TERMINAL_STATUSES


def live_state(status: str) -> str:
    """Best-effort LiveCallState for a call status (events drive the real one)."""
    return _LIVE_STATE_BY_STATUS.get(status, "connecting")


# Timeline event prefix -> category bucket (TalkFlow.md section 26.6).
_EVENT_CATEGORY_MAP: dict[str, str] = {
    "CALL": "CALL",
    "VAD": "VAD",
    "ASR": "ASR",
    "STT": "ASR",
    "SCRIPT": "SCRIPT",
    "RULES": "RULES",
    "RULE": "RULES",
    "LLM": "LLM",
    "TTS": "TTS",
    "INTERRUPT": "INTERRUPTION",
    "INTERRUPTION": "INTERRUPTION",
    "TRANSFER": "TRANSFER",
    "RECORDING": "RECORDING",
    "SYSTEM": "SYSTEM",
}


def event_category(event_type: str) -> str:
    """Bucket an event type into a timeline category (TalkFlow.md section 26.6)."""
    if not event_type:
        return "SYSTEM"
    return _EVENT_CATEGORY_MAP.get(event_type.split(".")[0].upper(), "GENERAL")


class CallPolicy:
    """Permission helpers for the calls module (Rule R4)."""

    @staticmethod
    def can_view(user: UserContext) -> bool:
        return PERM_CALL_VIEW in user.permissions

    @staticmethod
    def can_dispose(user: UserContext) -> bool:
        return PERM_CALL_DISPOSITION in user.permissions

    @staticmethod
    def scope_unlimited(user: UserContext) -> bool:
        return user.role == "MASTER_ADMIN"

    @staticmethod
    def sees_full_pii(user: UserContext) -> bool:
        return user.permissions is not None and PERM_PII_VIEW_FULL in user.permissions

    @staticmethod
    def masked_phone(phone: str | None, user: UserContext) -> str | None:
        if not phone:
            return None
        return phone if CallPolicy.sees_full_pii(user) else mask_phone(phone)


def resolve_scope_constraints(user: UserContext) -> dict:
    """Return the explicit scope filter to enforce (Rule R5).

    Every call row carries the tenant it was dialed for.  Unrestricted
    principals (MASTER_ADMIN / DEVOPS_IT) see all tenants; everyone else is
    narrowed to their assigned tenant id so cross-tenant reads are structurally
    impossible here.
    """
    constraints: dict[str, object] = {}
    if not CallPolicy.scope_unlimited(user) and user.scope.tenant_id:
        constraints["tenant_id"] = user.scope.tenant_id
    return constraints
