"""QA policies - pure governance, score calculation & self-review checks (Step 49)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from app.core.context import UserContext


@dataclass(frozen=True)
class CriterionInput:
    criterion_id: uuid.UUID
    weight: float
    auto_fail: bool
    score_value: float  # 0.0 to 100.0 or binary 0/1


def calculate_qa_score(criteria: list[CriterionInput]) -> tuple[float, bool, bool]:
    """Calculate total QA score for a review.

    Rules (Step 49):
    1. If any criterion with `auto_fail=True` has `score_value == 0`, total score is FORCED TO 0.
    2. Otherwise, total score is the weighted average score.

    Returns (total_score, passed, auto_failed).
    """
    if not criteria:
        return 100.0, True, False

    total_weight = 0.0
    weighted_sum = 0.0
    auto_failed = False

    for c in criteria:
        if c.auto_fail and c.score_value == 0:
            auto_failed = True

        total_weight += c.weight
        weighted_sum += (c.score_value * c.weight)

    if auto_failed:
        return 0.0, False, True

    final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
    passed = final_score >= 70.0  # Default passing threshold 70%
    return round(final_score, 2), passed, False


def can_review_call(
    user: UserContext,
    call_verifier_id: str | uuid.UUID | None,
    call_agent_id: str | uuid.UUID | None,
) -> bool:
    """Governance check (Step 49): A reviewer CANNOT review their own verified/handled call."""
    user_id_str = str(user.user_id)
    if call_verifier_id and str(call_verifier_id) == user_id_str:
        return False
    if call_agent_id and str(call_agent_id) == user_id_str:
        return False
    return True
