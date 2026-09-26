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

    Each signal is sourced from the table that actually owns it: QA state and
    transfer status live on ``calls``, the recording pipeline status on
    ``call_recordings.status``, and ASR confidence is per-turn on
    ``transcript_turns.confidence`` (averaged per call here).
    """
    conditions = ["1=1"]
    params: dict[str, Any] = {"sample_size": size}

    if sample_date:
        conditions.append("date(c.started_at) = :sdate")
        params["sdate"] = sample_date
    if campaign_id:
        conditions.append("c.campaign_id = :cid")
        params["cid"] = campaign_id

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT
            c.id,
            c.campaign_id,
            c.started_at,
            c.duration_seconds,
            c.transfer_status,
            r.status AS recording_status,
            CASE
                WHEN c.qa_status IS NOT NULL AND c.qa_status <> ''
                    THEN ARRAY[c.qa_status]::text[]
                ELSE ARRAY[]::text[]
            END AS qa_flags,
            (
                (CASE WHEN c.qa_status IS NOT NULL AND c.qa_status <> ''
                      THEN 1 ELSE 0 END) * 100
                + (CASE WHEN c.transfer_status LIKE 'failed%' THEN 1 ELSE 0 END) * 80
                + (CASE WHEN r.status IS NULL OR r.status <> 'ready'
                        THEN 1 ELSE 0 END) * 60
                + (1 - COALESCE(t.mean_confidence, 1.0)) * 40
                + random() * 10
            ) AS risk_score
        FROM calls c
        LEFT JOIN call_recordings r ON r.call_id = c.id
        LEFT JOIN (
            SELECT call_id, AVG(confidence) AS mean_confidence
            FROM transcript_turns
            GROUP BY call_id
        ) t ON t.call_id = c.id
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
