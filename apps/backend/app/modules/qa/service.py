"""QA service - risk-weighted sampling, review submission & audit logging (Step 49)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.core.outbox import write_outbox
from app.modules.calls.errors import CallNotFoundError
from app.modules.qa import repository as repo
from app.modules.qa.errors import QASelfReviewProhibitedError
from app.modules.qa.policies import CriterionInput, calculate_qa_score, can_review_call
from app.modules.qa.schemas import (
    QACriterionDTO,
    QAReviewCreateRequest,
    QAReviewDTO,
    QASampleCallDTO,
    QASampleQuery,
    QAScorecardDTO,
)
from app.packages.contracts.base import DataResponse
from app.packages.contracts.enums import AuditResult
from app.packages.db.models import QAReview, QAReviewScore


async def get_active_scorecard(session: AsyncSession) -> DataResponse[QAScorecardDTO]:
    card = await repo.get_active_scorecard(session)
    if not card:
        # Provide default system scorecard if not seeded in DB
        default_id = uuid.uuid4()
        return DataResponse(
            data=QAScorecardDTO(
                id=default_id,
                name="Default QA Scorecard",
                version="v1.0",
                is_active=True,
                criteria=[
                    QACriterionDTO(
                        id=uuid.uuid4(),
                        scorecard_id=default_id,
                        category="Compliance",
                        title="TCPA Recorded Disclosure Read",
                        weight=2.0,
                        auto_fail=True,
                        display_order=1,
                    ),
                    QACriterionDTO(
                        id=uuid.uuid4(),
                        scorecard_id=default_id,
                        category="Verification",
                        title="Medicare Part A & B Verified Active",
                        weight=1.5,
                        auto_fail=False,
                        display_order=2,
                    ),
                    QACriterionDTO(
                        id=uuid.uuid4(),
                        scorecard_id=default_id,
                        category="Professionalism",
                        title="Clear & Professional Tone",
                        weight=1.0,
                        auto_fail=False,
                        display_order=3,
                    ),
                ],
                created_at=datetime.now(UTC),
            )
        )

    criteria = await repo.get_scorecard_criteria(session, card.id)
    criteria_dtos = [
        QACriterionDTO(
            id=c.id,
            scorecard_id=c.scorecard_id,
            category=c.category,
            title=c.title,
            weight=c.weight,
            auto_fail=c.auto_fail,
            display_order=c.display_order,
        )
        for c in criteria
    ]

    return DataResponse(
        data=QAScorecardDTO(
            id=card.id,
            name=card.name,
            version=card.version,
            is_active=card.is_active,
            criteria=criteria_dtos,
            created_at=card.created_at,
        )
    )


async def sample_calls(
    session: AsyncSession, query: QASampleQuery
) -> DataResponse[list[QASampleCallDTO]]:
    rows = await repo.sample_risk_weighted_calls(
        session, sample_date=query.date, campaign_id=query.campaign_id, size=query.size
    )
    dtos = [
        QASampleCallDTO(
            call_id=r["id"],
            campaign_id=r["campaign_id"],
            started_at=r["started_at"],
            duration_seconds=r["duration_seconds"],
            transfer_status=r["transfer_status"],
            recording_status=r["recording_status"],
            qa_flags=r["qa_flags"] if isinstance(r["qa_flags"], list) else None,
            risk_score=round(float(r["risk_score"]), 2),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def submit_qa_review(
    session: AsyncSession,
    user: UserContext,
    payload: QAReviewCreateRequest,
) -> DataResponse[QAReviewDTO]:
    # 1. Fetch Call & Check Self-Review Prohibition (Step 49)
    call = await repo.get_call_by_id(session, payload.call_id)
    if not call:
        raise CallNotFoundError()

    # Self-review check: Reviewer cannot review call if they were the verifier
    if not can_review_call(user, getattr(call, "verifier_id", None), None):
        raise QASelfReviewProhibitedError()

    # 2. Fetch Scorecard Criteria & Calculate Score
    db_criteria = await repo.get_scorecard_criteria(session, payload.scorecard_id)
    criteria_map = {c.id: c for c in db_criteria}

    c_inputs: list[CriterionInput] = []
    score_rows: list[QAReviewScore] = []

    for item in payload.scores:
        crit = criteria_map.get(item.criterion_id)
        auto_fail_flag = crit.auto_fail if crit else False
        weight = crit.weight if crit else 1.0

        c_inputs.append(
            CriterionInput(
                criterion_id=item.criterion_id,
                weight=weight,
                auto_fail=auto_fail_flag,
                score_value=item.score_value,
            )
        )

        score_rows.append(
            QAReviewScore(
                id=uuid.uuid4(),
                criterion_id=item.criterion_id,
                score_value=item.score_value,
                auto_failed=(auto_fail_flag and item.score_value == 0),
            )
        )

    total_score, passed, auto_failed = calculate_qa_score(c_inputs)

    # 3. Create & Save Review
    review_id = uuid.uuid4()
    review = QAReview(
        id=review_id,
        call_id=payload.call_id,
        recording_id=payload.recording_id,
        scorecard_id=payload.scorecard_id,
        reviewer_id=user.user_id,
        total_score=total_score,
        passed=passed,
        auto_failed=auto_failed,
        notes=payload.notes,
        created_at=datetime.now(UTC),
    )

    await repo.save_qa_review(session, review, score_rows)

    # 4. Audit Log & Outbox Event
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="qa.reviewed",
        resource_type="call",
        resource_id=str(payload.call_id),
        result=AuditResult.SUCCESS,
        details={
            "scorecard_id": str(payload.scorecard_id),
            "total_score": total_score,
            "passed": passed,
            "auto_failed": auto_failed,
        },
    )

    await write_outbox(
        session,
        event_type="qa.review.submitted",
        aggregate_id=str(review_id),
        payload={
            "call_id": str(payload.call_id),
            "total_score": total_score,
            "passed": passed,
            "auto_failed": auto_failed,
            "reviewer_id": str(user.user_id),
        },
    )

    dto = QAReviewDTO(
        id=review_id,
        call_id=payload.call_id,
        recording_id=payload.recording_id,
        scorecard_id=payload.scorecard_id,
        reviewer_id=user.user_id,
        total_score=total_score,
        passed=passed,
        auto_failed=auto_failed,
        notes=payload.notes,
        created_at=review.created_at,
    )

    return DataResponse(data=dto)
