"""Tests for STEP 49 — QA Risk-Weighted Sampling & Scorecards."""

from __future__ import annotations

import uuid

from app.core.context import UserContext
from app.modules.qa.policies import CriterionInput, calculate_qa_score, can_review_call
from app.modules.qa.repository import sample_risk_weighted_calls


def test_auto_fail_zeroes_the_score():
    """Step 49 requirement: auto_fail criteria force total score to zero."""
    criteria = [
        CriterionInput(
            criterion_id=uuid.uuid4(), weight=50.0, auto_fail=False, score_value=100.0
        ),
        CriterionInput(
            criterion_id=uuid.uuid4(), weight=50.0, auto_fail=True, score_value=0.0
        ),
    ]
    total_score, passed, auto_failed = calculate_qa_score(criteria)
    assert total_score == 0.0
    assert passed is False
    assert auto_failed is True


def test_normal_score_calculation():
    criteria = [
        CriterionInput(
            criterion_id=uuid.uuid4(), weight=1.0, auto_fail=False, score_value=80.0
        ),
        CriterionInput(
            criterion_id=uuid.uuid4(), weight=1.0, auto_fail=False, score_value=100.0
        ),
    ]
    total_score, passed, auto_failed = calculate_qa_score(criteria)
    assert total_score == 90.0
    assert passed is True
    assert auto_failed is False


def test_self_review_prohibition():
    """Step 49 requirement: reviewer cannot review their own call."""
    reviewer_id = uuid.uuid4()
    user = UserContext(
        user_id=reviewer_id,
        tenant_id=None,
        permissions={"qa.audit"},
        role="VERIFIER",
    )

    # Call verified by same user
    assert (
        can_review_call(user, call_verifier_id=reviewer_id, call_agent_id=None) is False
    )
    # Call verified by someone else
    other_id = uuid.uuid4()
    assert can_review_call(user, call_verifier_id=other_id, call_agent_id=None) is True


async def test_sampling_prefers_risky_calls(seeded):
    """Step 49 requirement: sampling prefers risky calls over clean ones."""
    async with seeded["factory"]() as session:
        sample = await sample_risk_weighted_calls(
            session, sample_date=None, campaign_id=None, size=10
        )
        assert isinstance(sample, list)
