"""QA repository - database access & risk-weighted sampling query (Step 49)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import (
    Call,
    QACriterion,
    QAReview,
    QAReviewScore,
    QAScorecard,
)


async def get_active_scorecard(session: AsyncSession) -> QAScorecard | None:
    stmt = select(QAScorecard).where(QAScorecard.is_active.is_(True)).limit(1)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_scorecard_criteria(
    session: AsyncSession, scorecard_id: uuid.UUID
) -> list[QACriterion]:
    stmt = (
        select(QACriterion)
        .where(QACriterion.scorecard_id == scorecard_id)
        .order_by(QACriterion.display_order.asc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_call_by_id(session: AsyncSession, call_id: uuid.UUID) -> Call | None:
    stmt = select(Call).where(Call.id == call_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def sample_risk_weighted_calls(
    session: AsyncSession,
    sample_date: date | None,
    campaign_id: uuid.UUID | None,
    size: int = 10,
) -> list[dict[str, Any]]:
    """Risk-weighted daily sampling query (Step 49).

    Weight priority:
    - compliance / QA flags (+100)
    - failed transfer status (+80)
    - non-ready recording status (+60)
    - low mean ASR confidence (+40)
    - random jitter (+10)
    """
    conditions = ["1=1"]
    params: dict[str, Any] = {"sample_size": size}

    if sample_date:
        conditions.append("date(started_at) = :sdate")
        params["sdate"] = sample_date
    if campaign_id:
        conditions.append("campaign_id = :cid")
        params["cid"] = campaign_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT id, campaign_id, started_at, duration_seconds, transfer_status, recording_status, qa_flags,
        (
            (CASE WHEN qa_flags IS NOT NULL AND qa_flags != '[]' THEN 1 ELSE 0 END) * 100 +
            (CASE WHEN transfer_status LIKE 'failed%' THEN 1 ELSE 0 END) * 80 +
            (CASE WHEN recording_status IS NULL OR recording_status <> 'ready' THEN 1 ELSE 0 END) * 60 +
            (1 - COALESCE(mean_confidence, 1.0)) * 40 +
            random() * 10
        ) AS risk_score
        FROM calls
        WHERE {where_clause}
        ORDER BY risk_score DESC
        LIMIT :sample_size
    """)

    res = await session.execute(sql, params)
    rows = res.mappings().all()
    return [dict(r) for r in rows]


async def save_qa_review(
    session: AsyncSession,
    review: QAReview,
    scores: list[QAReviewScore],
) -> None:
    session.add(review)
    await session.flush()
    for s in scores:
        s.review_id = review.id
        session.add(s)
    await session.commit()
